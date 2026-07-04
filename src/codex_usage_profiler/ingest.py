from __future__ import annotations

import json
import re
import glob
from collections import Counter
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Tuple

from .models import SessionRecord, empty_usage
from .util import bounded_snippet, first_text, iter_json_objects, scalar_to_string, stable_hash


DEFAULT_SESSION_ROOTS = [
    "~/.codex/sessions",
    "~/.codex/archived_sessions",
    "~/.paperclip/instances/default/companies/*/codex-home/sessions",
    "~/.paperclip/instances/default/companies/*/codex-home/archived_sessions",
    "~/.paperclip/instances/default/companies/*/agents/*/codex-home/sessions",
    "~/.paperclip/instances/default/companies/*/agents/*/codex-home/archived_sessions",
]


def discover_logs(paths: Optional[List[str]] = None) -> List[Path]:
    roots = paths or DEFAULT_SESSION_ROOTS
    found: List[Path] = []
    for raw in roots:
        for path in _expand_log_root(raw):
            if path.is_file() and path.suffix == ".jsonl":
                found.append(path)
            elif path.is_dir():
                found.extend(sorted(path.rglob("*.jsonl")))
    return sorted(dict.fromkeys(found))


def parse_logs(paths: Optional[List[str]] = None, since: Optional[str] = None) -> Tuple[List[SessionRecord], List[str]]:
    warnings: List[str] = []
    records: List[SessionRecord] = []
    for path in discover_logs(paths):
        record = parse_log(path)
        if since and record.start_time and record.start_time[:10] < since:
            continue
        if record.warning_markers:
            warnings.extend([f"{path}: {w}" for w in record.warning_markers])
        records.append(record)
    return records, warnings


def parse_log(path: Path) -> SessionRecord:
    record = SessionRecord(session_id=path.stem, path=str(path))
    _apply_collector_sidecar(record, path)
    current_usage = empty_usage()
    event_counts: Counter[str] = Counter()
    tool_counts: Counter[str] = Counter()
    tool_sequence: List[str] = []
    command_signatures: List[str] = []
    command_labels: List[str] = []

    try:
        lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
    except OSError as exc:
        record.warning_markers.append(f"read_failed:{type(exc).__name__}")
        return record

    for lineno, line in enumerate(lines, start=1):
        if not line.strip():
            continue
        try:
            event = json.loads(line)
        except json.JSONDecodeError:
            record.warning_markers.append(f"json_decode_error:{lineno}")
            continue
        if not isinstance(event, dict):
            continue

        timestamp = scalar_to_string(event.get("timestamp") or event.get("ts"))
        if timestamp:
            if not record.start_time or timestamp < record.start_time:
                record.start_time = timestamp
            if not record.end_time or timestamp > record.end_time:
                record.end_time = timestamp

        event_type = scalar_to_string(event.get("type")) or "unknown"
        event_counts[event_type] += 1

        payload = event.get("payload")
        if isinstance(payload, dict):
            if event_type == "session_meta":
                _apply_session_meta(record, payload)
            elif event_type == "turn_context":
                _apply_turn_context(record, payload)

            usage = _extract_usage(payload)
            if usage:
                usage_total = usage.get("total_tokens", 0)
                if usage_total >= current_usage.get("total_tokens", 0):
                    current_usage = usage
                    record.usage_known = True

        _apply_generic_metadata(record, event)
        usage = _extract_usage(event)
        if usage:
            usage_total = usage.get("total_tokens", 0)
            if usage_total >= current_usage.get("total_tokens", 0):
                current_usage = usage
                record.usage_known = True

        request_text = _find_user_text(event)
        if request_text and not record.first_request_hash:
            record.first_request_hash = stable_hash(request_text)
            record.first_request_snippet = bounded_snippet(request_text)
            for key, value in _extract_request_features(request_text).items():
                record.first_request_features.setdefault(key, value)

        tool_name, arguments = _find_tool_call(event)
        if tool_name:
            tool_counts[tool_name] += 1
            if len(tool_sequence) < 40:
                tool_sequence.append(tool_name)
            if _is_edit_tool(tool_name, arguments):
                record.file_edit_markers += 1
            command_sig = _command_signature(tool_name, arguments)
            if command_sig:
                command_signatures.append(command_sig)
                command_label = _command_label(tool_name, arguments)
                if command_label:
                    command_labels.append(command_label)
                if _looks_like_test_command(arguments):
                    record.test_markers += 1

        if _looks_like_error(event):
            record.error_markers += 1

    record.usage = current_usage
    record.event_counts = dict(event_counts)
    record.tool_counts = dict(tool_counts)
    record.tool_sequence = tool_sequence
    record.command_signatures = command_signatures[:80]
    record.command_labels = command_labels[:80]
    if not record.session_id or record.session_id == path.stem:
        record.session_id = _infer_session_id(path, record)
    return record


def _expand_log_root(raw: str) -> List[Path]:
    expanded = Path(raw).expanduser()
    if any(char in str(expanded) for char in "*?["):
        return [Path(path) for path in sorted(glob.glob(str(expanded))) if Path(path).exists()]
    return [expanded]


def _apply_session_meta(record: SessionRecord, payload: Dict[str, Any]) -> None:
    record.session_id = scalar_to_string(payload.get("session_id") or payload.get("id")) or record.session_id
    record.cwd = scalar_to_string(payload.get("cwd")) or record.cwd
    record.source = scalar_to_string(payload.get("source")) or record.source
    record.originator = scalar_to_string(payload.get("originator")) or record.originator
    record.thread_source = scalar_to_string(payload.get("thread_source")) or record.thread_source
    record.cli_version = scalar_to_string(payload.get("cli_version")) or record.cli_version
    record.model_provider = scalar_to_string(payload.get("model_provider")) or record.model_provider
    roots = payload.get("workspace_roots")
    if isinstance(roots, list):
        record.workspace_roots = [r for r in (scalar_to_string(item) for item in roots) if r]


def _apply_turn_context(record: SessionRecord, payload: Dict[str, Any]) -> None:
    record.cwd = scalar_to_string(payload.get("cwd")) or record.cwd
    record.model = scalar_to_string(payload.get("model")) or record.model
    roots = payload.get("workspace_roots")
    if isinstance(roots, list):
        record.workspace_roots = [r for r in (scalar_to_string(item) for item in roots) if r]


def _apply_generic_metadata(record: SessionRecord, event: Dict[str, Any]) -> None:
    record.cwd = scalar_to_string(event.get("cwd") or event.get("working_dir") or event.get("workingDirectory")) or record.cwd
    record.model = scalar_to_string(event.get("model") or event.get("model_name")) or record.model
    record.source = scalar_to_string(event.get("source") or event.get("client") or event.get("app")) or record.source
    record.originator = scalar_to_string(event.get("originator") or event.get("tool")) or record.originator
    roots = event.get("workspace_roots") or event.get("workspaceRoots")
    if isinstance(roots, list):
        record.workspace_roots = [r for r in (scalar_to_string(item) for item in roots) if r] or record.workspace_roots
    _apply_paperclip_metadata(record, event)
    payload = event.get("payload")
    if isinstance(payload, dict):
        _apply_paperclip_metadata(record, payload)


def _apply_collector_sidecar(record: SessionRecord, path: Path) -> None:
    meta = _read_json(path.with_suffix(path.suffix + ".meta.json"))
    if not isinstance(meta, dict):
        return
    record.source_path = scalar_to_string(meta.get("source_path")) or record.source_path
    record.collector = scalar_to_string(meta.get("collector")) or record.collector
    record.collector_tool = scalar_to_string(meta.get("tool")) or record.collector_tool
    if record.collector_tool and not record.source:
        record.source = record.collector_tool
    if record.source_path and record.source_path not in record.workspace_roots:
        record.workspace_roots.append(record.source_path)
    _apply_paperclip_metadata(record, meta)


def _apply_paperclip_metadata(record: SessionRecord, event: Dict[str, Any]) -> None:
    candidates: List[Dict[str, Any]] = [event]
    paperclip = event.get("paperclip") or event.get("paperclip_metadata") or event.get("paperclipMetadata")
    if isinstance(paperclip, dict):
        candidates.append(paperclip)
    mappings = {
        "company": ["paperclip_company", "paperclipCompany", "company", "company_name", "companyName"],
        "company_id": ["paperclip_company_id", "paperclipCompanyId", "company_id", "companyId"],
        "project": ["paperclip_project", "paperclipProject", "project", "project_name", "projectName"],
        "project_id": ["paperclip_project_id", "paperclipProjectId", "project_id", "projectId"],
        "agent": ["paperclip_agent", "paperclipAgent", "agent", "agent_name", "agentName"],
        "agent_id": ["paperclip_agent_id", "paperclipAgentId", "agent_id", "agentId", "staff_id", "staffId"],
        "workspace_id": ["paperclip_workspace_id", "paperclipWorkspaceId", "workspace_id", "workspaceId"],
        "staff": ["paperclip_staff", "paperclipStaff", "staff", "staff_name", "staffName"],
        "task": ["paperclip_task", "paperclipTask", "task", "task_title", "taskTitle"],
        "issue": ["paperclip_issue", "paperclipIssue", "issue", "issue_key", "issueKey"],
        "queue": ["paperclip_queue", "paperclipQueue", "queue"],
    }
    for source in candidates:
        for feature_key, field_names in mappings.items():
            if record.first_request_features.get(feature_key):
                continue
            for field_name in field_names:
                value = scalar_to_string(source.get(field_name))
                if value:
                    record.first_request_features[feature_key] = bounded_snippet(value, 120)
                    break


def _extract_usage(payload: Dict[str, Any]) -> Optional[Dict[str, int]]:
    info = payload.get("info")
    usage = None
    if isinstance(info, dict):
        usage = info.get("total_token_usage")
    if usage is None:
        usage = payload.get("total_token_usage") or payload.get("usage")
    if not isinstance(usage, dict):
        return None
    result = empty_usage()
    for key in result:
        value = usage.get(key)
        if isinstance(value, (int, float)):
            result[key] = int(value)
    cache_creation = usage.get("cache_creation_input_tokens")
    cache_read = usage.get("cache_read_input_tokens")
    if isinstance(cache_creation, (int, float)):
        result["cached_input_tokens"] += int(cache_creation)
    if isinstance(cache_read, (int, float)):
        result["cached_input_tokens"] += int(cache_read)
    if result["input_tokens"] == 0 and isinstance(usage.get("prompt_tokens"), (int, float)):
        result["input_tokens"] = int(usage.get("prompt_tokens") or 0)
    if result["output_tokens"] == 0 and isinstance(usage.get("completion_tokens"), (int, float)):
        result["output_tokens"] = int(usage.get("completion_tokens") or 0)
    if result["total_tokens"] == 0:
        result["total_tokens"] = result["input_tokens"] + result["cached_input_tokens"] + result["output_tokens"]
    return result


def _find_user_text(event: Dict[str, Any]) -> Optional[str]:
    for obj in iter_json_objects(event):
        role = obj.get("role")
        if role == "user":
            text = first_text(obj.get("content"))
            if text:
                return text
    return None


def _find_tool_call(event: Dict[str, Any]) -> Tuple[Optional[str], Optional[Any]]:
    best_name: Optional[str] = None
    best_args: Optional[Any] = None
    for obj in iter_json_objects(event):
        item_type = scalar_to_string(obj.get("type")) or ""
        name = scalar_to_string(obj.get("name") or obj.get("tool_name"))
        if name and ("function_call" in item_type or item_type.endswith("_call") or obj.get("arguments") is not None):
            best_name = name
            best_args = obj.get("arguments")
    return best_name, best_args


def _decode_arguments(arguments: Any) -> Any:
    if isinstance(arguments, str):
        try:
            return json.loads(arguments)
        except json.JSONDecodeError:
            return arguments
    return arguments


def _command_signature(tool_name: str, arguments: Any) -> Optional[str]:
    args = _decode_arguments(arguments)
    cmd: Optional[str] = None
    if isinstance(args, dict):
        cmd = scalar_to_string(args.get("cmd") or args.get("command"))
    elif isinstance(args, str):
        cmd = args
    if not cmd:
        return None
    class_name = _command_class(cmd)
    return f"{tool_name}:{class_name}:{stable_hash(cmd)}"


def _command_label(tool_name: str, arguments: Any) -> Optional[str]:
    args = _decode_arguments(arguments)
    cmd: Optional[str] = None
    if isinstance(args, dict):
        cmd = scalar_to_string(args.get("cmd") or args.get("command"))
    elif isinstance(args, str):
        cmd = args
    if not cmd:
        return None
    text = cmd.strip()
    if "127.0.0.1:3100/api/health" in text:
        return "paperclip:api_health"
    if "com.paperclipai.paperclip.plist" in text:
        return "paperclip:launchagent_plist"
    if "launchctl print" in text and "com.paperclipai.paperclip" in text:
        return "paperclip:launchctl_service"
    if "paperclipai agent runtime-state" in text:
        return "paperclip:agent_runtime_state"
    if "paperclipai agent list" in text:
        return "paperclip:agent_list"
    if "paperclipai activity" in text and "--help" in text:
        return "paperclip:activity_help"
    if "live-runs" in text and "127.0.0.1:3100" in text:
        return "paperclip:live_runs"
    if "launchd.err.log" in text and ("tail " in text or "rg " in text or "grep " in text):
        return "paperclip:launchd_error_log"
    if "paperclipai" in text and "readlink" in text:
        return "paperclip:install_readlink"
    return _command_class(text)


def _command_class(cmd: str) -> str:
    text = cmd.strip()
    if re.search(r"\b(pytest|unittest|npm test|pnpm test|yarn test|xcodebuild test|swift test|cargo test|go test)\b", text):
        return "test"
    if re.search(r"\b(rg|grep|find|ls|sed|cat|jq)\b", text):
        return "read"
    if re.search(r"\b(git commit|git push|gh pr|git status|git diff)\b", text):
        return "git"
    if re.search(r"\b(npm|pnpm|yarn|pip|uv|cargo|go)\b", text):
        return "build"
    return "shell"


def _looks_like_test_command(arguments: Any) -> bool:
    args = _decode_arguments(arguments)
    text = json.dumps(args, sort_keys=True) if not isinstance(args, str) else args
    return bool(re.search(r"\b(pytest|unittest|npm test|pnpm test|yarn test|xcodebuild test|swift test|cargo test|go test)\b", text))


def _is_edit_tool(tool_name: str, arguments: Any) -> bool:
    lowered = tool_name.lower()
    if "apply_patch" in lowered or "edit" in lowered or "write" in lowered:
        return True
    args = _decode_arguments(arguments)
    text = json.dumps(args, sort_keys=True) if not isinstance(args, str) else args
    return bool(re.search(r"\b(git commit|tee |cat >|python .*write|sed -i)\b", text))


def _looks_like_error(event: Dict[str, Any]) -> bool:
    level = scalar_to_string(event.get("level"))
    if level and level.lower() in {"error", "critical"}:
        return True
    event_type = scalar_to_string(event.get("type")) or ""
    if "error" in event_type.lower():
        return True
    return False


def _infer_session_id(path: Path, record: SessionRecord) -> str:
    if record.first_request_hash:
        return f"{path.stem}:{record.first_request_hash}"
    return path.stem


def _extract_request_features(text: str) -> Dict[str, str]:
    features: Dict[str, str] = {}
    patterns = {
        "company": r"(?im)^\s*(?:Paperclip\s+Company|Company)\s*:\s*(.+)$",
        "company_id": r"(?im)^\s*(?:Paperclip[- ]?Company[- ]?ID|Company\s+ID)\s*:\s*([0-9a-f-]{16,})\s*$",
        "project": r"(?im)^\s*(?:Paperclip\s+Project|Project)\s*:\s*(.+)$",
        "project_id": r"(?im)^\s*(?:Paperclip[- ]?Project[- ]?ID|Project\s+ID)\s*:\s*([0-9a-f-]{16,})\s*$",
        "queue": r"(?im)^\s*Queue\s*:\s*(.+)$",
        "task": r"(?im)^\s*(?:Paperclip\s+Task|Task|Title)\s*:\s*(.+)$",
        "submitted_by": r"(?im)^\s*Submitted by\s*:\s*(.+)$",
        "agent": r"(?im)^\s*(?:Paperclip\s+Agent|Agent)\s*:\s*(.+)$",
        "agent_id": r"(?im)^\s*(?:Paperclip[- ]?Agent[- ]?ID|Agent\s+ID|Staff\s+ID)\s*:\s*([0-9a-f-]{16,})\s*$",
        "staff": r"(?im)^\s*(?:Paperclip\s+Staff|Staff|Role)\s*:\s*(.+)$",
        "issue": r"(?im)^\s*(?:Paperclip\s+Issue|Issue|Issue\s+Key)\s*:\s*([A-Z]{2,10}-\d+).*$",
    }
    for key, pattern in patterns.items():
        match = re.search(pattern, text)
        if match:
            features[key] = bounded_snippet(match.group(1), 80)
    issue = re.search(r"\b([A-Z]{2,10}-\d+)\b", text)
    if issue:
        features["issue"] = issue.group(1)
    return features


def _read_json(path: Path) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
