from __future__ import annotations

import argparse
import fnmatch
import glob
import hashlib
import json
import os
import re
import shutil
import socket
import subprocess
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Tuple

from .syslog_util import emit_loki_json, emit_syslog_json


DEFAULT_TOOL_GLOBS: Dict[str, List[str]] = {
    "codex": [
        "~/.codex/sessions/**/*.jsonl",
        "~/.codex/archived_sessions/**/*.jsonl",
        "~/.paperclip/instances/default/companies/*/codex-home/sessions/**/*.jsonl",
        "~/.paperclip/instances/default/companies/*/codex-home/archived_sessions/**/*.jsonl",
        "~/.paperclip/instances/default/companies/*/agents/*/codex-home/sessions/**/*.jsonl",
        "~/.paperclip/instances/default/companies/*/agents/*/codex-home/archived_sessions/**/*.jsonl",
    ],
    "claude": [
        "~/.claude/projects/**/*.jsonl",
        "~/.claude/sessions/**/*.jsonl",
        "~/.claude/**/sessions/**/*.jsonl",
    ],
    "pi": [
        "~/.pi/agent/sessions/**/*.jsonl",
        "~/.pi/agent/**/sessions/**/*.jsonl",
        "~/.pi/agent/projects/**/*.jsonl",
        "~/.pi/agent/history/**/*.jsonl",
        "~/.pi/agent/runs/**/*.jsonl",
    ],
    "t3chat": [
        "~/.t3chat/**/*.jsonl",
        "~/.config/t3chat/**/*.jsonl",
        "~/.local/share/t3chat/**/*.jsonl",
        "~/Library/Application Support/T3 Chat/**/*.jsonl",
    ],
    "kimi": [
        "~/.kimi/**/*.jsonl",
        "~/.config/kimi/**/*.jsonl",
        "~/.local/share/kimi/**/*.jsonl",
    ],
    "droid": [
        "~/.droid/**/*.jsonl",
        "~/.config/droid/**/*.jsonl",
        "~/.local/share/droid/**/*.jsonl",
        "~/.nursedroid/**/*.jsonl",
    ],
    "cursor": [
        "~/.cursor/**/*.jsonl",
        "~/Library/Application Support/Cursor/User/workspaceStorage/**/*.jsonl",
    ],
    "opencode": [
        "~/.opencode/**/*.jsonl",
        "~/.local/share/opencode/**/*.jsonl",
    ],
    "codexbar": [
        "~/Library/Application Support/com.steipete.codexbar/history/codex.json",
        "~/Library/Caches/CodexBar/cost-usage/*.json",
        "~/Library/Caches/CodexBar/model-pricing/*.json",
        "~/Library/Group Containers/Y5PE65HELJ.com.steipete.codexbar/widget-snapshot.json",
    ],
}

DEFAULT_CONFIG = {
    "collector_name": None,
    "destination": "saphid@lxso1:/home/saphid/.local/share/codex-usage-profiler/collected-sessions",
    "include_defaults": True,
    "tools": {},
    "exclude": [
        "**/node_modules/**",
        "**/.venv/**",
        "**/venv/**",
        "**/auth.json",
        "**/credentials.json",
        "**/models_cache.json",
        "**/cache/**",
        "**/Caches/**",
    ],
    "max_file_bytes": 104857600,
    "state_path": "~/.local/state/codex-usage-collector/state.json",
    "staging_dir": "~/.local/share/codex-usage-collector/staging",
    "log_path": "~/.local/log/codex-usage-collector/collector.jsonl",
    "syslog_host": "192.168.1.30",
    "syslog_port": 514,
    "syslog_protocol": "tcp",
    "loki_url": "http://192.168.1.221:3100/loki/api/v1/push",
    "paperclip_metadata": True,
    "paperclip_root": "~/.paperclip/instances/default",
    "paperclip_context_path": "~/.paperclip/context.json",
    "paperclip_api_base": None,
    "paperclip_api_timeout": 1.5,
}


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(
        prog="codex-usage-collector",
        description="Collect changed AI coding session files and push them to a central Codex Usage Profiler host.",
    )
    parser.add_argument("--config", help="Collector JSON config")
    parser.add_argument("--once", action="store_true", help="Run one collection pass")
    parser.add_argument("--dry-run", action="store_true", help="Scan and log without staging or pushing")
    parser.add_argument("--print-default-config", action="store_true", help="Print a starter config")
    args = parser.parse_args(argv)

    if args.print_default_config:
        print(json.dumps(default_config(), indent=2, sort_keys=True))
        return 0

    config = load_collector_config(args.config)
    result = run_collection(config, dry_run=args.dry_run)
    print(json.dumps(result, sort_keys=True))
    return 0 if not result.get("errors") else 2


def default_config() -> Dict[str, Any]:
    data = dict(DEFAULT_CONFIG)
    data["tools"] = {tool: list(globs) for tool, globs in DEFAULT_TOOL_GLOBS.items()}
    return data


def load_collector_config(path: Optional[str]) -> Dict[str, Any]:
    config = dict(DEFAULT_CONFIG)
    if path:
        loaded = _read_json(Path(path).expanduser())
        if isinstance(loaded, dict):
            config.update(loaded)
    tools: Dict[str, List[str]] = {}
    if config.get("include_defaults", True):
        tools.update({tool: list(globs) for tool, globs in DEFAULT_TOOL_GLOBS.items()})
    for tool, globs_value in dict(config.get("tools") or {}).items():
        if isinstance(globs_value, str):
            tools.setdefault(str(tool), []).append(globs_value)
        elif isinstance(globs_value, list):
            tools.setdefault(str(tool), []).extend(str(item) for item in globs_value)
    config["tools"] = tools
    config["collector_name"] = config.get("collector_name") or socket.gethostname().split(".")[0]
    return config


def run_collection(config: Dict[str, Any], dry_run: bool = False) -> Dict[str, Any]:
    started = time.time()
    collector = str(config.get("collector_name") or socket.gethostname().split(".")[0])
    state_path = Path(str(config.get("state_path"))).expanduser()
    staging_root = Path(str(config.get("staging_dir"))).expanduser()
    log_path = Path(str(config.get("log_path"))).expanduser()
    state = _read_json(state_path)
    if not isinstance(state, dict):
        state = {"files": {}}
    state_files: Dict[str, Any] = dict(state.get("files") or {})
    candidate_rows = discover_candidates(config)
    staged = 0
    skipped = 0
    oversized = 0
    vanished = 0
    errors: List[str] = []
    matched_by_tool: Dict[str, int] = {}
    staged_by_tool: Dict[str, int] = {}

    for tool, path in candidate_rows:
        matched_by_tool[tool] = matched_by_tool.get(tool, 0) + 1
        try:
            stat = path.stat()
        except FileNotFoundError:
            vanished += 1
            continue
        except OSError as exc:
            errors.append(f"stat_failed:{path}:{type(exc).__name__}")
            continue
        max_bytes = int(config.get("max_file_bytes") or 0)
        if max_bytes and stat.st_size > max_bytes:
            oversized += 1
            continue
        state_key = str(path)
        fingerprint = {"size": stat.st_size, "mtime_ns": stat.st_mtime_ns}
        if state_files.get(state_key) == fingerprint:
            skipped += 1
            continue
        if not dry_run:
            try:
                stage_file(staging_root, collector, tool, path, stat)
            except FileNotFoundError:
                vanished += 1
                continue
            except OSError as exc:
                errors.append(f"stage_failed:{path}:{type(exc).__name__}")
                continue
            state_files[state_key] = fingerprint
        staged += 1
        staged_by_tool[tool] = staged_by_tool.get(tool, 0) + 1

    if bool(config.get("paperclip_metadata", False)):
        try:
            metadata_result = stage_paperclip_metadata(staging_root, collector, config, dry_run=dry_run)
        except OSError as exc:
            errors.append(f"paperclip_metadata_failed:{type(exc).__name__}")
        else:
            if metadata_result:
                metadata_key, metadata_fingerprint = metadata_result
                if state_files.get(metadata_key) == metadata_fingerprint:
                    skipped += 1
                else:
                    if not dry_run:
                        state_files[metadata_key] = metadata_fingerprint
                    staged += 1
                    staged_by_tool["paperclip_metadata"] = staged_by_tool.get("paperclip_metadata", 0) + 1

    pushed = 0
    if staged and not dry_run:
        push_error = push_staged(staging_root / collector, str(config.get("destination") or ""))
        if push_error:
            errors.append(push_error)
        else:
            pushed = staged
            state["files"] = state_files
            _write_json(state_path, state)

    event = {
        "event": "collector_run",
        "collector": collector,
        "host": socket.gethostname(),
        "matched_files": len(candidate_rows),
        "matched_by_tool": matched_by_tool,
        "staged_files": staged,
        "staged_by_tool": staged_by_tool,
        "skipped_files": skipped,
        "oversized_files": oversized,
        "vanished_files": vanished,
        "pushed_files": pushed,
        "dry_run": dry_run,
        "duration_seconds": round(time.time() - started, 3),
        "errors": errors,
    }
    write_event(log_path, event)
    emit_syslog_json(
        event,
        host=str(config.get("syslog_host") or "") or None,
        port=int(config.get("syslog_port") or 514),
        tag="codex-usage-collector",
        protocol=str(config.get("syslog_protocol") or "tcp"),
    )
    emit_loki_json(
        event,
        url=str(config.get("loki_url") or "") or None,
        labels={"service": "collector", "host": collector},
    )
    return event


def discover_candidates(config: Dict[str, Any]) -> List[Tuple[str, Path]]:
    rows: List[Tuple[str, Path]] = []
    seen: set[Path] = set()
    excludes = [str(item) for item in config.get("exclude") or []]
    for tool, patterns in dict(config.get("tools") or {}).items():
        for pattern in patterns:
            expanded = os.path.expanduser(os.path.expandvars(str(pattern)))
            for match in glob.glob(expanded, recursive=True):
                path = Path(match)
                if not path.is_file():
                    continue
                if path.suffix.lower() not in {".jsonl", ".json"}:
                    continue
                if should_exclude(path, excludes):
                    continue
                resolved = path.resolve()
                if resolved in seen:
                    continue
                seen.add(resolved)
                rows.append((str(tool), resolved))
    return sorted(rows, key=lambda item: (item[0], str(item[1])))


def should_exclude(path: Path, patterns: Iterable[str]) -> bool:
    text = str(path)
    if "CodexBar" in text or "com.steipete.codexbar" in text:
        return False
    return any(fnmatch.fnmatch(text, os.path.expanduser(pattern)) for pattern in patterns)


def stage_file(staging_root: Path, collector: str, tool: str, path: Path, stat: os.stat_result) -> Path:
    digest = hashlib.sha256(str(path).encode("utf-8")).hexdigest()[:16]
    dest_dir = staging_root / collector / tool / digest
    dest_dir.mkdir(parents=True, exist_ok=True)
    dest = dest_dir / path.name
    shutil.copy2(path, dest)
    meta = {
        "collector": collector,
        "host": socket.gethostname(),
        "tool": tool,
        "source_path": str(path),
        "source_path_sha256": hashlib.sha256(str(path).encode("utf-8")).hexdigest(),
        "size": stat.st_size,
        "mtime": stat.st_mtime,
        "staged_at": int(time.time()),
    }
    paperclip = _paperclip_context_from_path(str(path))
    if paperclip:
        meta["paperclip"] = paperclip
    _write_json(dest.with_suffix(dest.suffix + ".meta.json"), meta)
    return dest


def stage_paperclip_metadata(
    staging_root: Path,
    collector: str,
    config: Dict[str, Any],
    dry_run: bool = False,
) -> Optional[Tuple[str, Dict[str, str]]]:
    snapshot = snapshot_paperclip_metadata(config)
    if not snapshot:
        return None
    encoded = json.dumps(snapshot, sort_keys=True, separators=(",", ":")).encode("utf-8")
    digest = hashlib.sha256(encoded).hexdigest()
    state_key = f"paperclip_metadata:{snapshot.get('root') or collector}"
    fingerprint = {"sha256": digest}
    if not dry_run:
        dest_dir = staging_root / collector / "paperclip_metadata" / digest[:16]
        dest_dir.mkdir(parents=True, exist_ok=True)
        _write_json(dest_dir / "paperclip-metadata.json", snapshot)
    return state_key, fingerprint


def snapshot_paperclip_metadata(config: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    root = Path(str(config.get("paperclip_root") or "~/.paperclip/instances/default")).expanduser()
    context_path = Path(str(config.get("paperclip_context_path") or "~/.paperclip/context.json")).expanduser()
    context = _read_json(context_path)
    if not root.exists() and not isinstance(context, dict):
        return None
    api_base = str(config.get("paperclip_api_base") or _api_base_from_context(context) or "http://127.0.0.1:3100").rstrip("/")
    timeout = float(config.get("paperclip_api_timeout") or 1.5)
    warnings: List[str] = []
    companies = _fetch_json_list(f"{api_base}/api/companies", timeout, warnings, "companies")
    agents: List[Dict[str, Any]] = []
    projects: List[Dict[str, Any]] = []
    for company in companies:
        company_id = str(company.get("id") or "")
        if not company_id:
            continue
        agents.extend(_fetch_json_list(f"{api_base}/api/companies/{company_id}/agents", timeout, warnings, f"agents:{company_id}"))
        projects.extend(_fetch_json_list(f"{api_base}/api/companies/{company_id}/projects", timeout, warnings, f"projects:{company_id}"))
    snapshot = {
        "schema": "codex-usage-profiler.paperclip-metadata.v1",
        "root": str(root),
        "api_base": api_base,
        "captured_at": int(time.time()),
        "context": _sanitize_paperclip_context(context),
        "companies": [_pick_fields(row, ["id", "name", "status", "issuePrefix"]) for row in companies],
        "agents": [_sanitize_agent(row) for row in agents],
        "projects": [_sanitize_project(row) for row in projects],
        "workspaces": _paperclip_workspace_summaries(root, companies),
        "warnings": warnings,
    }
    if not snapshot["companies"] and not snapshot["agents"] and not snapshot["projects"] and not snapshot["workspaces"]:
        return None
    return snapshot


def push_staged(source: Path, destination: str) -> Optional[str]:
    if not destination:
        return "push_failed:missing_destination"
    if not source.exists():
        return None
    if _is_remote_destination(destination):
        dest = destination.rstrip("/") + f"/{source.name}/"
        proc = subprocess.run(["rsync", "-a", str(source) + "/", dest], text=True, capture_output=True, check=False)
        if proc.returncode != 0:
            return f"push_failed:rsync:{proc.stderr.strip() or proc.stdout.strip()}"
        return None
    dest_path = Path(destination).expanduser() / source.name
    shutil.copytree(source, dest_path, dirs_exist_ok=True)
    return None


def _api_base_from_context(context: Any) -> Optional[str]:
    if not isinstance(context, dict):
        return None
    profiles = context.get("profiles")
    current = context.get("currentProfile")
    if isinstance(profiles, dict) and current in profiles and isinstance(profiles[current], dict):
        value = profiles[current].get("apiBase")
        if isinstance(value, str) and value:
            return value
    return None


def _fetch_json_list(url: str, timeout: float, warnings: List[str], label: str) -> List[Dict[str, Any]]:
    try:
        with urllib.request.urlopen(url, timeout=timeout) as response:
            payload = json.loads(response.read().decode("utf-8"))
    except (OSError, urllib.error.URLError, json.JSONDecodeError) as exc:
        warnings.append(f"{label}:{type(exc).__name__}")
        return []
    if not isinstance(payload, list):
        return []
    return [item for item in payload if isinstance(item, dict)]


def _sanitize_paperclip_context(context: Any) -> Dict[str, Any]:
    if not isinstance(context, dict):
        return {}
    return {
        "currentProfile": context.get("currentProfile"),
        "companyId": context.get("companyId"),
        "agentId": context.get("agentId"),
        "persona": context.get("persona"),
    }


def _sanitize_agent(row: Dict[str, Any]) -> Dict[str, Any]:
    adapter = row.get("adapterConfig") if isinstance(row.get("adapterConfig"), dict) else {}
    env = adapter.get("env") if isinstance(adapter.get("env"), dict) else {}
    codex_home = env.get("CODEX_HOME") if isinstance(env.get("CODEX_HOME"), dict) else {}
    return {
        "id": row.get("id"),
        "companyId": row.get("companyId"),
        "name": row.get("name"),
        "title": row.get("title"),
        "role": row.get("role"),
        "status": row.get("status"),
        "reportsTo": row.get("reportsTo"),
        "adapterType": row.get("adapterType"),
        "cwd": adapter.get("cwd"),
        "codexHome": codex_home.get("value"),
        "instructionsFilePath": adapter.get("instructionsFilePath"),
    }


def _sanitize_project(row: Dict[str, Any]) -> Dict[str, Any]:
    codebase = row.get("codebase") if isinstance(row.get("codebase"), dict) else {}
    return {
        "id": row.get("id"),
        "companyId": row.get("companyId"),
        "name": row.get("name"),
        "status": row.get("status"),
        "leadAgentId": row.get("leadAgentId"),
        "urlKey": row.get("urlKey"),
        "workspaceId": codebase.get("workspaceId"),
        "localFolder": codebase.get("localFolder"),
        "managedFolder": codebase.get("managedFolder"),
        "effectiveLocalFolder": codebase.get("effectiveLocalFolder"),
    }


def _pick_fields(row: Dict[str, Any], fields: List[str]) -> Dict[str, Any]:
    return {field: row.get(field) for field in fields if field in row}


def _paperclip_workspace_summaries(root: Path, companies: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    workspaces = root / "workspaces"
    if not workspaces.exists():
        return []
    prefix_company = {
        str(company.get("issuePrefix") or "").upper(): str(company.get("id") or "")
        for company in companies
        if company.get("issuePrefix") and company.get("id")
    }
    rows: List[Dict[str, Any]] = []
    for workspace in sorted(workspaces.iterdir()):
        if not workspace.is_dir():
            continue
        names = [item.name for item in workspace.iterdir() if item.is_file()]
        if not names:
            continue
        staff = _staff_from_workspace_names(names)
        issue_prefixes = sorted(_issue_prefixes_from_names(names, set(prefix_company)))
        company_id = prefix_company.get(issue_prefixes[0]) if issue_prefixes else None
        task_ids = sorted(_task_ids_from_names(names))[:20]
        rows.append(
            {
                "id": workspace.name,
                "path": str(workspace),
                "staffLabel": staff,
                "companyId": company_id,
                "issuePrefixes": issue_prefixes,
                "taskIds": task_ids,
                "fileCount": len(names),
            }
        )
    return rows


def _staff_from_workspace_names(names: List[str]) -> Optional[str]:
    aliases = {
        "ceo": "CEO",
        "cto": "CTO",
        "cmo": "CMO",
        "cfo": "CFO",
        "coo": "COO",
        "sre": "SRE",
        "qa": "QA",
        "devops": "DevOps",
        "security": "Security",
        "growth": "Growth",
    }
    counts: Dict[str, int] = {}
    for name in names:
        match = re.match(r"([a-z][a-z0-9]+)[-_]", name.lower())
        if match:
            counts[match.group(1)] = counts.get(match.group(1), 0) + 1
    if not counts:
        return None
    key = sorted(counts.items(), key=lambda item: (-item[1], item[0]))[0][0]
    return aliases.get(key, key.replace("_", " ").replace("-", " ").title())


def _issue_prefixes_from_names(names: List[str], known_prefixes: set[str]) -> set[str]:
    prefixes = set()
    for name in names:
        for match in re.finditer(r"\b([a-z]{2,10})[-_]?(\d{1,6})\b", name, re.IGNORECASE):
            prefix = match.group(1).upper()
            if not known_prefixes or prefix in known_prefixes:
                prefixes.add(prefix)
    return prefixes


def _task_ids_from_names(names: List[str]) -> set[str]:
    ids = set()
    for name in names:
        for match in re.finditer(r"\b([A-Z]{2,10})[-_]?(\d{1,6})\b", name, re.IGNORECASE):
            ids.add(f"{match.group(1).upper()}-{match.group(2)}")
    return ids


def _paperclip_context_from_path(path: str) -> Dict[str, str]:
    result: Dict[str, str] = {}
    match = re.search(r"/(?:\.paperclip|paperclip)/instances/([^/]+)/companies/([^/]+)(?:/agents/([^/]+))?/codex-home/", path)
    if match:
        result["instance_id"] = match.group(1)
        result["company_id"] = match.group(2)
        if match.group(3):
            result["agent_id"] = match.group(3)
    match = re.search(r"/(?:\.paperclip|paperclip)/instances/([^/]+)/projects/([^/]+)/([^/]+)/", path)
    if match:
        result["instance_id"] = match.group(1)
        result["company_id"] = match.group(2)
        result["project_id"] = match.group(3)
    match = re.search(r"/(?:\.paperclip|paperclip)/instances/([^/]+)/workspaces/([^/]+)(?:/|$)", path)
    if match:
        result["instance_id"] = match.group(1)
        result["workspace_id"] = match.group(2)
    return result


def write_event(log_path: Path, event: Dict[str, Any]) -> None:
    log_path.parent.mkdir(parents=True, exist_ok=True)
    with log_path.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(event, sort_keys=True) + "\n")


def _is_remote_destination(destination: str) -> bool:
    head = destination.split("/", 1)[0]
    return ":" in head


def _read_json(path: Path) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}


def _write_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(data, indent=2, sort_keys=True), encoding="utf-8")
    tmp.replace(path)


if __name__ == "__main__":
    raise SystemExit(main())
