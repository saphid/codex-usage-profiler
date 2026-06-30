from __future__ import annotations

import re
from pathlib import Path
from typing import Optional

from .config import Config
from .models import Attribution, SessionRecord


def attribute_sessions(records: list[SessionRecord], config: Config) -> None:
    for record in records:
        record.client = attribute_client(record, config)
        record.project = attribute_project(record, config)
        record.task = attribute_task(record, config)


def attribute_client(record: SessionRecord, config: Config) -> Attribution:
    haystack = " ".join(
        value or ""
        for value in [record.originator, record.source, record.thread_source, record.cwd, record.path]
    ).lower()
    for pattern, label in config.client_aliases.items():
        if pattern.lower() in haystack:
            return Attribution(label, "high", [f"config.client_alias:{pattern}"])
    if "codex desktop" in haystack:
        return Attribution("Codex Desktop", "high", ["originator=Codex Desktop"])
    if "codex-tui" in haystack or record.source in {"cli", "exec"}:
        return Attribution("Codex CLI", "medium", [f"source={record.source}"])
    if "codex_exec" in haystack:
        return Attribution("Codex exec", "medium", ["originator/source=codex_exec"])
    if "cursor" in haystack:
        return Attribution("Cursor", "medium", ["cursor signal"])
    if "/.pi/" in haystack or "pi coding" in haystack:
        return Attribution("Pi Coding Agent", "medium", ["pi path/signal"])
    return Attribution("unknown", "low", ["no known client signal"])


def attribute_project(record: SessionRecord, config: Config) -> Attribution:
    candidates = [record.cwd] + record.workspace_roots + [record.path]
    for value in candidates:
        if not value:
            continue
        for prefix, label in config.path_aliases.items():
            if str(Path(value).expanduser()).startswith(str(Path(prefix).expanduser())):
                return Attribution(label, "high", [f"config.path_alias:{prefix}"])
        label = _project_from_path(value)
        if label:
            return Attribution(label, "medium", [f"path:{value}"])
    return Attribution("unknown", "low", ["missing cwd/workspace"])


def _project_from_path(value: str) -> Optional[str]:
    expanded = str(Path(value).expanduser())
    match = re.search(r"/\.codex/worktrees/[^/]+/([^/]+)", expanded)
    if match:
        return match.group(1)
    match = re.search(r"/Documents/([^/]+)", expanded)
    if match:
        return match.group(1)
    match = re.search(r"/projects/([^/]+)", expanded)
    if match:
        return match.group(1)
    path = Path(expanded)
    if path.name and path.name not in {".codex", "sessions", "archived_sessions"}:
        return path.name
    return None


def attribute_task(record: SessionRecord, config: Config) -> Attribution:
    source = record.thread_source or ""
    project = record.project.label if record.project else "unknown"
    for pattern, label in config.task_aliases.items():
        blob = " ".join([record.cwd or "", record.path, source, record.first_request_hash or ""])
        if pattern.lower() in blob.lower():
            return Attribution(label, "high", [f"config.task_alias:{pattern}"])
    if source == "automation":
        return Attribution(f"automation:{project}", "medium", ["thread_source=automation"])
    if source == "subagent":
        return Attribution(f"subagent:{project}", "medium", ["thread_source=subagent"])
    if record.first_request_hash:
        return Attribution(f"request:{record.first_request_hash}", "medium", ["first_user_request_hash"])
    if record.path:
        return Attribution(f"session:{Path(record.path).stem}", "low", ["session filename"])
    return Attribution("unknown", "low", ["no task signal"])

