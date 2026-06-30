from __future__ import annotations

import datetime as dt
import hashlib
import json
import os
import re
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional


SECRET_RE = re.compile(r"(?i)(token|secret|cookie|auth|bearer|session|jwt|key|password)")
SECRET_VALUE_RE = re.compile(r"(?i)(bearer\s+[a-z0-9._-]+|api[_-]?key\s*[:=]\s*\S+|token\s*[:=]\s*\S+|password\s*[:=]\s*\S+)")


def home() -> Path:
    return Path.home()


def expand_path(value: str) -> Path:
    return Path(value).expanduser()


def iso_to_datetime(value: Optional[str]) -> Optional[dt.datetime]:
    if not value or not isinstance(value, str):
        return None
    text = value.replace("Z", "+00:00")
    try:
        return dt.datetime.fromisoformat(text)
    except ValueError:
        return None


def day_key(value: Optional[str]) -> str:
    parsed = iso_to_datetime(value)
    return parsed.date().isoformat() if parsed else "unknown"


def hour_key(value: Optional[str]) -> str:
    parsed = iso_to_datetime(value)
    if not parsed:
        return "unknown"
    return parsed.replace(minute=0, second=0, microsecond=0).isoformat().replace("+00:00", "Z")


def stable_hash(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8", errors="ignore")).hexdigest()[:16]


def safe_json_load(path: Path) -> Optional[Any]:
    try:
        with path.open("r", encoding="utf-8") as fh:
            return json.load(fh)
    except (OSError, json.JSONDecodeError):
        return None


def scalar_to_string(value: Any) -> Optional[str]:
    if value is None:
        return None
    if isinstance(value, str):
        return value
    if isinstance(value, (int, float, bool)):
        return str(value)
    try:
        return json.dumps(value, sort_keys=True, separators=(",", ":"))
    except TypeError:
        return repr(value)


def redact_value(key: str, value: Any) -> Any:
    if SECRET_RE.search(key):
        return "<redacted>"
    if isinstance(value, dict):
        return {k: redact_value(k, v) for k, v in value.items()}
    if isinstance(value, list):
        return [redact_value(key, item) for item in value]
    if isinstance(value, str) and SECRET_VALUE_RE.search(value):
        return "<redacted>"
    return value


def redact_dict(data: Any) -> Any:
    if isinstance(data, dict):
        return {k: redact_value(k, v) for k, v in data.items()}
    if isinstance(data, list):
        return [redact_dict(item) for item in data]
    return data


def bounded_snippet(text: str, limit: int = 120) -> str:
    clean = re.sub(r"\s+", " ", text).strip()
    clean = re.sub(r"(?i)(api[_-]?key|token|secret|password|bearer)\s*[:=]\s*\S+", r"\1=<redacted>", clean)
    if len(clean) <= limit:
        return clean
    return clean[: max(0, limit - 1)] + "..."


def iter_json_objects(value: Any) -> Iterable[Dict[str, Any]]:
    if isinstance(value, dict):
        yield value
        for child in value.values():
            yield from iter_json_objects(child)
    elif isinstance(value, list):
        for child in value:
            yield from iter_json_objects(child)


def first_text(value: Any) -> Optional[str]:
    if isinstance(value, str):
        return value
    if isinstance(value, list):
        parts: List[str] = []
        for item in value:
            if isinstance(item, str):
                parts.append(item)
            elif isinstance(item, dict):
                text = item.get("text") or item.get("content")
                if isinstance(text, str):
                    parts.append(text)
        return " ".join(parts).strip() or None
    if isinstance(value, dict):
        text = value.get("text") or value.get("content")
        return first_text(text)
    return None


def common_prefix_path(paths: List[str]) -> Optional[str]:
    clean = [p for p in paths if p]
    if not clean:
        return None
    try:
        return os.path.commonpath(clean)
    except ValueError:
        return clean[0]
