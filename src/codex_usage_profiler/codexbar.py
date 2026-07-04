from __future__ import annotations

import json
import os
import plistlib
import shutil
import subprocess
from pathlib import Path
from typing import Any, Dict, List, Optional

from .models import CodexBarTelemetry
from .util import home, redact_dict, safe_json_load, stable_hash


CODEXBAR_APP = Path("/Applications/CodexBar.app")
CODEXBAR_CONFIG = "~/.config/codexbar/config.json"
CODEXBAR_HISTORY = "~/Library/Application Support/com.steipete.codexbar/history/codex.json"
CODEXBAR_COST_DIR = "~/Library/Caches/CodexBar/cost-usage"
CODEXBAR_PRICING_DIR = "~/Library/Caches/CodexBar/model-pricing"
CODEXBAR_WIDGET = "~/Library/Group Containers/Y5PE65HELJ.com.steipete.codexbar/widget-snapshot.json"


def collect_codexbar(enabled: bool = True, timeout: int = 30) -> CodexBarTelemetry:
    telemetry = CodexBarTelemetry()
    if not enabled:
        telemetry.warnings.append("codexbar_disabled")
        return telemetry

    telemetry.cli_path = shutil.which("codexbar")
    telemetry.app_version = _app_version()
    telemetry.config_path = _existing_path(CODEXBAR_CONFIG)
    telemetry.history_path = _existing_path(CODEXBAR_HISTORY)
    telemetry.cost_cache_paths = _glob_existing(CODEXBAR_COST_DIR, "*.json")
    telemetry.pricing_cache_paths = _glob_existing(CODEXBAR_PRICING_DIR, "*.json")
    _merge_collected_codexbar(telemetry, os.environ.get("CODEXBAR_COLLECTED_ROOT"))
    telemetry.available = bool(telemetry.cli_path or telemetry.cost_cache_paths or telemetry.history_path)

    if telemetry.cli_path:
        usage, warning = _run_json([telemetry.cli_path, "usage", "--provider", "codex", "--source", "auto", "--format", "json"], timeout)
        if warning:
            telemetry.warnings.append(f"usage_cli:{warning}")
        if usage is not None:
            telemetry.live_usage = _normalize_usage_output(usage)
        cost, warning = _run_json([telemetry.cli_path, "cost", "--provider", "codex", "--format", "json"], timeout)
        if warning:
            telemetry.warnings.append(f"cost_cli:{warning}")
        if cost is not None:
            telemetry.cost_usage = _normalize_cost_output(cost)

    telemetry.cost_cache = _read_cost_cache(telemetry.cost_cache_paths)
    telemetry.pi_cache = _read_pi_cache(telemetry.cost_cache_paths)
    telemetry.pricing_cache = _read_pricing_cache(telemetry.pricing_cache_paths)
    telemetry.history = _read_history(telemetry.history_path)
    return telemetry


def _existing_path(path: str) -> Optional[str]:
    expanded = Path(path).expanduser()
    return str(expanded) if expanded.exists() else None


def _glob_existing(root: str, pattern: str) -> List[str]:
    expanded = Path(root).expanduser()
    if not expanded.exists():
        return []
    return [str(path) for path in sorted(expanded.glob(pattern), key=lambda p: p.stat().st_mtime, reverse=True)]


def _merge_collected_codexbar(telemetry: CodexBarTelemetry, root: Optional[str]) -> None:
    if not root:
        return
    expanded = Path(root).expanduser()
    if not expanded.exists():
        return
    paths = [path for path in expanded.rglob("*.json") if "/codexbar/" in str(path)]
    histories = sorted(
        [path for path in paths if path.name == "codex.json"],
        key=lambda p: p.stat().st_mtime,
        reverse=True,
    )
    if histories and not telemetry.history_path:
        telemetry.history_path = str(histories[0])
    cost_paths = [str(path) for path in paths if path.name.startswith(("codex-v", "pi-sessions-v"))]
    pricing_paths = [str(path) for path in paths if path.name.startswith("models-")]
    telemetry.cost_cache_paths = _dedupe_paths(telemetry.cost_cache_paths + sorted(cost_paths, reverse=True))
    telemetry.pricing_cache_paths = _dedupe_paths(telemetry.pricing_cache_paths + sorted(pricing_paths, reverse=True))


def _dedupe_paths(paths: List[str]) -> List[str]:
    seen = set()
    result = []
    for path in paths:
        if path in seen:
            continue
        seen.add(path)
        result.append(path)
    return result


def _app_version() -> Optional[str]:
    info = CODEXBAR_APP / "Contents" / "Info.plist"
    if not info.exists():
        return None
    try:
        with info.open("rb") as fh:
            data = plistlib.load(fh)
    except (OSError, plistlib.InvalidFileException):
        return None
    short = data.get("CFBundleShortVersionString")
    build = data.get("CFBundleVersion")
    commit = data.get("CodexGitCommit")
    bits = [str(part) for part in [short, build, commit] if part]
    return " ".join(bits) if bits else None


def _run_json(cmd: List[str], timeout: int) -> tuple[Optional[Any], Optional[str]]:
    try:
        proc = subprocess.run(cmd, text=True, capture_output=True, timeout=timeout, check=False)
    except (OSError, subprocess.TimeoutExpired) as exc:
        return None, type(exc).__name__
    if proc.returncode != 0:
        return None, f"exit_{proc.returncode}"
    try:
        return json.loads(proc.stdout), None
    except json.JSONDecodeError:
        return None, "invalid_json"


def _single_provider(value: Any) -> Optional[Dict[str, Any]]:
    if isinstance(value, list):
        for item in value:
            if isinstance(item, dict):
                return item
        return None
    if isinstance(value, dict):
        return value
    return None


def _normalize_usage_output(value: Any) -> Optional[Dict[str, Any]]:
    item = _single_provider(value)
    if not item:
        return None
    usage = item.get("usage") if isinstance(item.get("usage"), dict) else item
    primary = usage.get("primary") if isinstance(usage, dict) else None
    secondary = usage.get("secondary") if isinstance(usage, dict) else None
    windows: List[Dict[str, Any]] = []
    if isinstance(primary, dict):
        windows.append({"id": "primary", "title": "Codex 5-hour", **primary})
    if isinstance(secondary, dict):
        windows.append({"id": "secondary", "title": "Codex weekly", **secondary})
    for win in usage.get("extraRateWindows", []) if isinstance(usage, dict) else []:
        if isinstance(win, dict):
            window = win.get("window") if isinstance(win.get("window"), dict) else {}
            windows.append({"id": win.get("id"), "title": win.get("title"), **window})
    return redact_dict(
        {
            "provider": item.get("provider"),
            "source": item.get("source"),
            "updatedAt": usage.get("updatedAt") if isinstance(usage, dict) else item.get("updatedAt"),
            "dataConfidence": usage.get("dataConfidence") if isinstance(usage, dict) else None,
            "loginMethod": usage.get("loginMethod") if isinstance(usage, dict) else None,
            "credits": item.get("credits") if isinstance(item.get("credits"), dict) else None,
            "windows": windows,
        }
    )


def _normalize_cost_output(value: Any) -> Optional[Dict[str, Any]]:
    item = _single_provider(value)
    if not item:
        return None
    daily = []
    for day in item.get("daily", []) if isinstance(item.get("daily"), list) else []:
        if isinstance(day, dict):
            daily.append(
                {
                    "date": day.get("date"),
                    "inputTokens": _int(day.get("inputTokens")),
                    "outputTokens": _int(day.get("outputTokens")),
                    "totalTokens": _int(day.get("totalTokens")),
                    "totalCost": _float(day.get("totalCost")),
                    "modelsUsed": day.get("modelsUsed") if isinstance(day.get("modelsUsed"), list) else [],
                    "modelBreakdowns": day.get("modelBreakdowns") if isinstance(day.get("modelBreakdowns"), list) else [],
                }
            )
    return {
        "provider": item.get("provider"),
        "source": item.get("source"),
        "updatedAt": item.get("updatedAt"),
        "currencyCode": item.get("currencyCode"),
        "last30DaysTokens": _int(item.get("last30DaysTokens")),
        "last30DaysCostUSD": _float(item.get("last30DaysCostUSD")),
        "sessionTokens": _int(item.get("sessionTokens")),
        "sessionCostUSD": _float(item.get("sessionCostUSD")),
        "daily": daily,
    }


def _read_cost_cache(paths: List[str]) -> Optional[Dict[str, Any]]:
    for raw in paths:
        path = Path(raw)
        if not path.name.startswith("codex-v"):
            continue
        data = safe_json_load(path)
        if not isinstance(data, dict):
            continue
        days = []
        raw_days = data.get("days")
        if isinstance(raw_days, dict):
            for date, by_model in sorted(raw_days.items()):
                if not isinstance(by_model, dict):
                    continue
                models = []
                for model, triple in by_model.items():
                    input_tokens = cached_tokens = output_tokens = 0
                    if isinstance(triple, list):
                        input_tokens = _int(triple[0] if len(triple) > 0 else 0)
                        cached_tokens = _int(triple[1] if len(triple) > 1 else 0)
                        output_tokens = _int(triple[2] if len(triple) > 2 else 0)
                    models.append(
                        {
                            "model": model,
                            "inputTokens": input_tokens,
                            "cachedInputTokens": cached_tokens,
                            "outputTokens": output_tokens,
                            "totalTokens": input_tokens + output_tokens,
                        }
                    )
                days.append({"date": date, "models": models})
        return {
            "path": str(path),
            "version": data.get("version"),
            "lastScanUnixMs": data.get("lastScanUnixMs"),
            "roots": data.get("roots") if isinstance(data.get("roots"), dict) else {},
            "producerKeyHash": stable_hash(str(data.get("producerKey"))) if data.get("producerKey") else None,
            "pricingKey": data.get("codexPricingKey"),
            "dayCount": len(days),
            "days": days,
        }
    return None


def _read_pi_cache(paths: List[str]) -> Optional[Dict[str, Any]]:
    for raw in paths:
        path = Path(raw)
        if not path.name.startswith("pi-sessions-v"):
            continue
        data = safe_json_load(path)
        if not isinstance(data, dict):
            continue
        files = data.get("files") if isinstance(data.get("files"), dict) else {}
        by_project: Dict[str, int] = {}
        for file_path in files.keys():
            project = _project_from_pi_path(file_path)
            by_project[project] = by_project.get(project, 0) + 1
        return {
            "path": str(path),
            "version": data.get("version"),
            "lastScanUnixMs": data.get("lastScanUnixMs"),
            "fileCount": len(files),
            "projects": by_project,
        }
    return None


def _project_from_pi_path(path: str) -> str:
    marker = "/sessions/--Users-"
    if marker not in path:
        return "unknown"
    slug = path.split(marker, 1)[1].split("/", 1)[0]
    bits = [part for part in slug.split("-") if part and part not in {"saphid", "Users"}]
    if "Documents" in bits:
        idx = bits.index("Documents")
        return bits[idx + 1] if idx + 1 < len(bits) else "Documents"
    if "projects" in bits:
        idx = bits.index("projects")
        return bits[idx + 1] if idx + 1 < len(bits) else "projects"
    return bits[-1] if bits else "unknown"


def _read_pricing_cache(paths: List[str]) -> Optional[Dict[str, Any]]:
    for raw in paths:
        path = Path(raw)
        data = safe_json_load(path)
        if not isinstance(data, dict):
            continue
        models: Dict[str, Dict[str, Any]] = {}
        providers = data.get("catalog", {}).get("providers") if isinstance(data.get("catalog"), dict) else None
        if isinstance(providers, dict):
            for provider_id, provider in providers.items():
                provider_models = provider.get("models") if isinstance(provider, dict) else None
                if not isinstance(provider_models, dict):
                    continue
                for model_id, model in provider_models.items():
                    if not isinstance(model, dict):
                        continue
                    cost = model.get("cost") if isinstance(model.get("cost"), dict) else None
                    if not cost:
                        continue
                    short_id = model_id.split("/", 1)[-1]
                    record = {
                        "provider": provider_id,
                        "modelId": model_id,
                        "name": model.get("name"),
                        "cost": cost,
                    }
                    models[model_id] = record
                    models[short_id] = record
                    models[str(model.get("id") or model_id)] = record
        return {
            "path": str(path),
            "version": data.get("version"),
            "fetchedAt": data.get("fetchedAt"),
            "modelCount": len(models),
            "models": models,
        }
    return None


def _read_history(path: Optional[str]) -> Optional[Dict[str, Any]]:
    if not path:
        return None
    data = safe_json_load(Path(path))
    if not isinstance(data, dict):
        return None
    snapshots = []
    accounts = data.get("accounts") if isinstance(data.get("accounts"), dict) else {}
    for account_key, windows in accounts.items():
        if not isinstance(windows, list):
            continue
        for window in windows:
            if not isinstance(window, dict):
                continue
            entries = window.get("entries") if isinstance(window.get("entries"), list) else []
            latest = entries[-1] if entries and isinstance(entries[-1], dict) else None
            snapshots.append(
                {
                    "accountHash": stable_hash(account_key),
                    "name": window.get("name"),
                    "windowMinutes": window.get("windowMinutes"),
                    "entryCount": len(entries),
                    "latest": latest,
                    "entries": entries,
                }
            )
    return {
        "path": path,
        "version": data.get("version"),
        "preferredAccountHash": stable_hash(str(data.get("preferredAccountKey"))) if data.get("preferredAccountKey") else None,
        "snapshotCount": sum(len(item.get("entries", [])) for item in snapshots),
        "windows": snapshots,
    }


def _int(value: Any) -> int:
    return int(value) if isinstance(value, (int, float)) else 0


def _float(value: Any) -> Optional[float]:
    return float(value) if isinstance(value, (int, float)) else None
