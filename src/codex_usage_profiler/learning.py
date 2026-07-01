from __future__ import annotations

import argparse
import json
import re
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, Iterable, Iterator, List, Optional, Sequence, Tuple

from .ingest import parse_logs
from .attribution import attribute_sessions
from .config import Config
from .models import Attribution, SessionRecord, empty_usage
from .paperclip import apply_paperclip_attribution, build_paperclip_index
from .util import bounded_snippet, first_text, iter_json_objects, scalar_to_string, stable_hash


PHASE_REQUEST = "request_idea"
PHASE_INVESTIGATION = "investigation_research_discovery"
PHASE_UNDERSTANDING = "understanding"
PHASE_IMPLEMENTATION = "implementation"
PHASE_VALIDATION = "proof_validation"

PHASE_ORDER = [
    PHASE_REQUEST,
    PHASE_INVESTIGATION,
    PHASE_UNDERSTANDING,
    PHASE_IMPLEMENTATION,
    PHASE_VALIDATION,
]

SECRET_TEXT_RE = re.compile(
    r"(?i)(bearer\s+[a-z0-9._~+/=-]+|authorization\s*[:=]\s*(?:bearer\s+)?[a-z0-9._~+/=-]+|api[_-]?key\s*[:=]\s*\S+|token\s*[:=]\s*\S+|password\s*[:=]\s*\S+|cookie\s*[:=]\s*\S+)"
)
SENSITIVE_HEADER_RE = re.compile(r"(?im)\b(authorization|cookie|set-cookie|x-api-key|api-key)\s*:\s*[^\n\r]+")
URL_SECRET_RE = re.compile(r"(?i)([?&](?:access_token|id_token|token|key|signature|sig|auth|session|code|state|expires|policy|x-amz-signature|x-goog-signature)=)[^&\s]+")
COOKIE_RE = re.compile(r"(?i)\b(cookie|set-cookie|authorization)\b\s*[:=]\s*[^\s,;]+")
CLI_COOKIE_RE = re.compile(r"(?i)(--cookie(?:-jar)?\s+)(?:\"[^\"]+\"|'[^']+'|\S+)")
JSON_SECRET_RE = re.compile(r"(?i)(\"?(?:authorization|cookie|set-cookie|x-api-key|api-key)\"?\s*:\s*)\"[^\"]+\"")
JWT_RE = re.compile(r"\beyJ[a-zA-Z0-9_-]+\.[a-zA-Z0-9_-]+\.[a-zA-Z0-9_-]+\b")
BASIC_AUTH_URL_RE = re.compile(r"(?i)\b(https?://)[^/\s:@]+:[^/\s@]+@")
HOME_PATH_RE = re.compile(r"/Users/([^/\s]+)/[^\s,;:)]+")

SOURCE_CODEX = "codex"
SOURCE_CLAUDE = "claude"
SOURCE_PI = "pi"
SOURCE_GENERIC = "generic"
SOURCE_ALL = "all"

DEFAULT_SOURCE_ROOTS = {
    SOURCE_CLAUDE: ["~/.claude/projects"],
    SOURCE_PI: ["~/.pi/agent/sessions"],
    SOURCE_GENERIC: ["~/.hermes/sessions"],
}


@dataclass
class PhaseSpan:
    phase: str
    start_event: int
    end_event: int
    evidence: List[str] = field(default_factory=list)
    confidence: str = "medium"

    def to_dict(self, include_snippets: bool = False) -> Dict[str, Any]:
        data = {
            "phase": self.phase,
            "start_event": self.start_event,
            "end_event": self.end_event,
            "evidence_count": len(self.evidence),
            "confidence": self.confidence,
        }
        if include_snippets:
            data["evidence"] = self.evidence
        return data


@dataclass
class SessionLearning:
    session_id: str
    path: str
    source: str = SOURCE_CODEX
    start_time: Optional[str] = None
    end_time: Optional[str] = None
    project: str = "unknown"
    task: str = "unknown"
    total_tokens: int = 0
    spans: List[PhaseSpan] = field(default_factory=list)
    transitions: Counter[str] = field(default_factory=Counter)
    feature_counts: Counter[str] = field(default_factory=Counter)
    feature_evidence: Dict[str, List[str]] = field(default_factory=lambda: defaultdict(list))
    command_labels: Counter[str] = field(default_factory=Counter)
    evidence_terms: List[str] = field(default_factory=list)

    def to_dict(self, include_snippets: bool = False) -> Dict[str, Any]:
        data = {
            "session_id": self.session_id,
            "source": self.source,
            "start_time": self.start_time,
            "end_time": self.end_time,
            "project": self.project,
            "task": self.task,
            "total_tokens": self.total_tokens,
            "spans": [span.to_dict(include_snippets=include_snippets) for span in self.spans],
            "transitions": dict(self.transitions),
            "feature_counts": dict(self.feature_counts),
            "command_labels": dict(self.command_labels),
        }
        if include_snippets:
            data["path"] = self.path
            data["feature_evidence"] = {key: values[:6] for key, values in self.feature_evidence.items()}
        else:
            data["path_hash"] = stable_hash(self.path)
        return data


@dataclass
class LearningCard:
    title: str
    summary: str
    scope: str
    problem_type: str
    phase_pattern: str
    evidence_sessions: List[str]
    evidence_snippets: List[str]
    source_counts: Dict[str, int]
    phase_counts: Dict[str, int]
    frequency: int
    token_impact: int
    confidence: str
    fixability: str
    recommended_destination: str
    why_not_auto_fix: str

    def to_dict(self) -> Dict[str, Any]:
        return self.__dict__.copy()


@dataclass
class LearningReport:
    sessions: List[SessionLearning]
    cards: List[LearningCard]
    warnings: List[str]
    include_snippets: bool = False

    def to_dict(self) -> Dict[str, Any]:
        source_counts = Counter(session.source for session in self.sessions)
        return {
            "run": {
                "session_count": len(self.sessions),
                "card_count": len(self.cards),
                "warning_count": len(self.warnings),
                "sources": dict(sorted(source_counts.items())),
                "confidence_note": "Learning cards are review candidates from deterministic phase and pattern evidence, not automatic fixes.",
            },
            "cards": [card.to_dict() for card in self.cards],
            "sessions": [session.to_dict(include_snippets=self.include_snippets) for session in self.sessions],
            "warnings": [_safe_evidence(warning) for warning in self.warnings],
        }


def build_learning_report(
    paths: Optional[List[str]] = None,
    since: Optional[str] = None,
    include_snippets: bool = False,
    source: str = SOURCE_CODEX,
) -> LearningReport:
    records, warnings = _load_source_records(paths, since=since, source=source)
    records_by_path = {record.path: record for record in records}
    selected_paths = [Path(record.path) for record in records]
    sessions = [_parse_learning_session(path, records_by_path.get(str(path)), include_snippets) for path in selected_paths]
    sessions = _merge_duplicate_sessions(sessions)
    sessions = [session for session in sessions if session.spans or session.feature_counts]
    cards = mine_learning_cards(sessions, include_snippets=include_snippets)
    return LearningReport(sessions=sessions, cards=cards, warnings=warnings, include_snippets=include_snippets)


def render_learning_json(report: LearningReport) -> str:
    return json.dumps(report.to_dict(), indent=2, sort_keys=True)


def render_learning_markdown(report: LearningReport, top: int = 20) -> str:
    lines: List[str] = []
    lines.append("# Codex Session Learning Miner")
    lines.append("")
    lines.append(f"Sessions analyzed: {len(report.sessions)}")
    lines.append(f"Learning cards: {len(report.cards)}")
    source_counts = Counter(session.source for session in report.sessions)
    if source_counts:
        lines.append("Sources: " + ", ".join(f"{source}={count}" for source, count in sorted(source_counts.items())))
    lines.append("")
    if not report.cards:
        lines.append("No learning cards met the current thresholds.")
        return "\n".join(lines) + "\n"
    by_scope: Dict[str, List[LearningCard]] = defaultdict(list)
    for card in report.cards:
        by_scope[card.scope].append(card)
    for scope in ["global", "project", "language", "infrastructure", "service", "harness-tooling"]:
        cards = by_scope.get(scope, [])
        if not cards:
            continue
        lines.append(f"## {scope}")
        lines.append("")
        for card in cards[:top]:
            lines.append(f"### {card.title}")
            lines.append("")
            lines.append(card.summary)
            lines.append("")
            lines.append(f"- Type: `{card.problem_type}`")
            lines.append(f"- Pattern: `{card.phase_pattern}`")
            lines.append(f"- Sessions: {card.frequency}")
            if card.source_counts:
                lines.append(f"- Sources: {', '.join(f'{source}={count}' for source, count in sorted(card.source_counts.items()))}")
            if card.phase_counts:
                lines.append(f"- Phase evidence: {', '.join(f'{phase}={count}' for phase, count in sorted(card.phase_counts.items()))}")
            lines.append(f"- Matched cumulative tokens: {card.token_impact:,} (deduplicated sessions, includes cache; cards overlap)")
            lines.append(f"- Confidence: `{card.confidence}`")
            lines.append(f"- Fixability: `{card.fixability}`")
            lines.append(f"- Destination: `{card.recommended_destination}`")
            lines.append(f"- Why not auto-fix: {card.why_not_auto_fix}")
            if card.evidence_snippets:
                lines.append("- Evidence:")
                for snippet in card.evidence_snippets[:3]:
                    lines.append(f"  - {snippet}")
            lines.append("")
    if report.warnings:
        lines.append("## Warnings")
        lines.append("")
        for warning in report.warnings[:top]:
            lines.append(f"- {_safe_evidence(warning)}")
    return "\n".join(lines).rstrip() + "\n"


def mine_learning_cards(sessions: Sequence[SessionLearning], include_snippets: bool = False) -> List[LearningCard]:
    cards: List[LearningCard] = []
    cards.extend(_browser_request_replay_cards(sessions, include_snippets))
    cards.extend(_late_pivot_cards(sessions, include_snippets))
    cards.extend(_project_memory_cards(sessions, include_snippets))
    cards.extend(_validation_loop_cards(sessions, include_snippets))
    cards.extend(_missing_validation_cards(sessions, include_snippets))
    cards.extend(_rediscovered_lesson_cards(sessions, include_snippets))
    cards.sort(key=lambda card: (card.token_impact, card.frequency), reverse=True)
    return cards


def _parse_learning_session(path: Path, record: Any, include_snippets: bool) -> SessionLearning:
    session = SessionLearning(
        session_id=getattr(record, "session_id", path.stem),
        path=str(path),
        source=getattr(record, "source", SOURCE_CODEX) or SOURCE_CODEX,
        start_time=getattr(record, "start_time", None),
        end_time=getattr(record, "end_time", None),
        project=getattr(getattr(record, "project", None), "label", "unknown"),
        task=getattr(getattr(record, "task", None), "label", "unknown"),
        total_tokens=getattr(record, "usage", {}).get("total_tokens", 0) if record else 0,
    )
    current: Optional[PhaseSpan] = None
    last_phase: Optional[str] = None
    for index, event in enumerate(_iter_session_events(path), start=1):
        event_features: set[str] = set()
        event_feature_evidence: Dict[str, str] = {}
        for phase, evidence, feature in _classify_event(event):
            if feature:
                event_features.add(feature)
                event_feature_evidence.setdefault(feature, evidence)
            if evidence:
                if len(session.evidence_terms) < 40:
                    session.evidence_terms.append(evidence)
            if phase:
                if current and current.phase == phase:
                    current.end_event = index
                    _append_evidence(current, evidence, include_snippets)
                else:
                    if current:
                        session.spans.append(current)
                    current = PhaseSpan(phase=phase, start_event=index, end_event=index)
                    _append_evidence(current, evidence, include_snippets)
                    if last_phase and last_phase != phase:
                        session.transitions[f"{last_phase}->{phase}"] += 1
                    last_phase = phase
        for label in _command_labels(event):
            session.command_labels[label] += 1
        for feature in event_features:
            session.feature_counts[feature] += 1
            evidence = event_feature_evidence.get(feature)
            if evidence:
                bucket = session.feature_evidence.setdefault(feature, [])
                if evidence not in bucket and len(bucket) < 20:
                    bucket.append(evidence)
    if current:
        session.spans.append(current)
    return session


def _load_source_records(paths: Optional[List[str]], since: Optional[str], source: str) -> Tuple[List[SessionRecord], List[str]]:
    if source == SOURCE_ALL and paths:
        return _load_detected_path_records(paths, since=since)
    requested = _normalize_sources(source)
    records: List[SessionRecord] = []
    warnings: List[str] = []
    if SOURCE_CODEX in requested:
        config = Config()
        codex_paths = paths if source == SOURCE_CODEX else None
        codex_records, codex_warnings = parse_logs(codex_paths, since=since)
        for record in codex_records:
            record.source = SOURCE_CODEX
        attribute_sessions(codex_records, config)
        apply_paperclip_attribution(codex_records, build_paperclip_index(config))
        records.extend(codex_records)
        warnings.extend(codex_warnings)
    for generic_source in [SOURCE_CLAUDE, SOURCE_PI, SOURCE_GENERIC]:
        if generic_source not in requested:
            continue
        roots = paths if paths is not None else DEFAULT_SOURCE_ROOTS.get(generic_source)
        for path in _discover_source_paths(roots):
            record = _parse_generic_record(path, generic_source)
            if since and record.start_time and record.start_time[:10] < since:
                continue
            if record.warning_markers:
                warnings.extend([f"{path}: {warning}" for warning in record.warning_markers])
            records.append(record)
    return records, warnings


def _load_detected_path_records(paths: Sequence[str], since: Optional[str]) -> Tuple[List[SessionRecord], List[str]]:
    buckets: Dict[str, List[str]] = defaultdict(list)
    for path in _discover_source_paths(paths):
        buckets[_detect_source(path)].append(str(path))
    records: List[SessionRecord] = []
    warnings: List[str] = []
    if buckets.get(SOURCE_CODEX):
        codex_records, codex_warnings = parse_logs(buckets[SOURCE_CODEX], since=since)
        for record in codex_records:
            record.source = SOURCE_CODEX
        attribute_sessions(codex_records, Config())
        records.extend(codex_records)
        warnings.extend(codex_warnings)
    for source_name in [SOURCE_CLAUDE, SOURCE_PI, SOURCE_GENERIC]:
        for raw in buckets.get(source_name, []):
            path = Path(raw)
            record = _parse_generic_record(path, source_name)
            if since and record.start_time and record.start_time[:10] < since:
                continue
            records.append(record)
    return records, warnings


def _detect_source(path: Path) -> str:
    text = str(path)
    if "/.claude/projects/" in text:
        return SOURCE_CLAUDE
    if "/.pi/agent/sessions/" in text or "pi-sessions" in text.lower():
        return SOURCE_PI
    if "/.codex/sessions/" in text or "/codex-home/sessions/" in text:
        return SOURCE_CODEX
    return SOURCE_GENERIC


def _normalize_sources(source: str) -> List[str]:
    if source == SOURCE_ALL:
        return [SOURCE_CODEX, SOURCE_CLAUDE, SOURCE_PI, SOURCE_GENERIC]
    if source in {SOURCE_CODEX, SOURCE_CLAUDE, SOURCE_PI, SOURCE_GENERIC}:
        return [source]
    return [SOURCE_GENERIC]


def _discover_source_paths(roots: Optional[Sequence[str]]) -> List[Path]:
    found: List[Path] = []
    for raw in roots or []:
        path = Path(raw).expanduser()
        if path.is_file() and path.suffix in {".jsonl", ".json"}:
            found.append(path)
        elif path.is_dir():
            found.extend(sorted(p for p in path.rglob("*") if p.suffix in {".jsonl", ".json"} and p.is_file()))
    return sorted(dict.fromkeys(found))


def _parse_generic_record(path: Path, source: str) -> SessionRecord:
    record = SessionRecord(session_id=path.stem, path=str(path), source=source)
    usage = empty_usage()
    first_request = None
    for event in _iter_session_events(path):
        if not isinstance(event, dict):
            continue
        timestamp = _timestamp_from_event(event)
        if timestamp:
            record.start_time = min([value for value in [record.start_time, timestamp] if value])
            record.end_time = max([value for value in [record.end_time, timestamp] if value])
        session_id = scalar_to_string(event.get("sessionId") or event.get("session_id"))
        if not session_id and event.get("type") == "session":
            session_id = scalar_to_string(event.get("id"))
        if session_id:
            record.session_id = session_id
        cwd = _find_string_key(event, "cwd")
        if cwd:
            record.cwd = cwd
        model = _find_string_key(event, "model") or _find_string_key(event, "modelId")
        provider = _find_string_key(event, "provider")
        record.model = model or record.model
        record.model_provider = provider or record.model_provider
        event_usage = _extract_generic_usage(event)
        if event_usage:
            record.usage_known = True
            for key, value in event_usage.items():
                usage[key] = usage.get(key, 0) + value
        if not first_request and _is_user_event(event):
            first_request = _signal_text(_event_text(event))
    if first_request:
        record.first_request_hash = stable_hash(first_request)
        record.first_request_snippet = bounded_snippet(first_request)
    record.usage = usage
    if record.cwd:
        record.project = Attribution(Path(record.cwd).name or record.cwd, "medium", ["cwd"])
    else:
        record.project = Attribution(_project_from_source_path(path), "low", ["path"])
    record.task = Attribution("unknown", "low")
    return record


def _iter_session_events(path: Path) -> Iterator[Dict[str, Any]]:
    try:
        text = path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return
    if path.suffix == ".json":
        try:
            data = json.loads(text)
        except json.JSONDecodeError:
            return
        if isinstance(data, list):
            for item in data:
                if isinstance(item, dict):
                    yield item
            return
        if isinstance(data, dict):
            for key in ["events", "messages", "session", "items"]:
                value = data.get(key)
                if isinstance(value, list):
                    for item in value:
                        if isinstance(item, dict):
                            yield item
                    return
            yield data
        return
    for line in text.splitlines():
        if not line.strip():
            continue
        try:
            event = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(event, dict):
            yield event


def _timestamp_from_event(event: Dict[str, Any]) -> Optional[str]:
    timestamp = scalar_to_string(event.get("timestamp") or event.get("ts"))
    if timestamp:
        return timestamp
    for obj in iter_json_objects(event):
        value = obj.get("timestamp")
        if isinstance(value, str):
            return value
    return None


def _find_string_key(event: Dict[str, Any], key: str) -> Optional[str]:
    for obj in iter_json_objects(event):
        value = obj.get(key)
        if isinstance(value, str):
            return value
    return None


def _extract_generic_usage(event: Dict[str, Any]) -> Optional[Dict[str, int]]:
    usage = None
    if isinstance(event.get("usage"), dict):
        usage = event.get("usage")
    message = event.get("message")
    if usage is None and isinstance(message, dict) and isinstance(message.get("usage"), dict):
        usage = message.get("usage")
    payload = event.get("payload")
    if usage is None and isinstance(payload, dict) and isinstance(payload.get("usage"), dict):
        usage = payload.get("usage")
    if not isinstance(usage, dict):
        return None
    result = empty_usage()
    mapping = {
        "input_tokens": ["input_tokens", "input"],
        "cached_input_tokens": ["cached_input_tokens", "cache_read_input_tokens", "cache_creation_input_tokens", "cacheRead", "cacheWrite"],
        "output_tokens": ["output_tokens", "output"],
        "reasoning_output_tokens": ["reasoning_output_tokens", "reasoning"],
        "total_tokens": ["total_tokens", "totalTokens"],
    }
    for target, names in mapping.items():
        result[target] = sum(int(usage.get(name, 0)) for name in names if isinstance(usage.get(name), (int, float)))
    if result["total_tokens"] == 0:
        result["total_tokens"] = result["input_tokens"] + result["cached_input_tokens"] + result["output_tokens"] + result["reasoning_output_tokens"]
    return result if any(result.values()) else None


def _project_from_source_path(path: Path) -> str:
    parent = path.parent.name.strip("-")
    if not parent:
        return "unknown"
    decoded = parent.replace("--", "/").replace("-", "/")
    return Path(decoded).name or parent


def _classify_event(event: Dict[str, Any]) -> List[Tuple[Optional[str], str, Optional[str]]]:
    results: List[Tuple[Optional[str], str, Optional[str]]] = []
    event_type = scalar_to_string(event.get("type")) or ""
    if event_type in {"session_meta", "turn_context"}:
        return results
    payload = event.get("payload")
    text = _signal_text(_event_text(event))
    tool_name, arguments = _tool_call(event)
    cmd_text = _argument_text(arguments)
    feature_text = f"{text} {tool_name or ''} {cmd_text}".lower()
    feature = _feature_from_text(feature_text)
    if feature:
        results.append((None, _safe_evidence(text or cmd_text), feature))
    if _is_tool_result_event(event):
        if text:
            phase = PHASE_VALIDATION if _looks_like_validation_text(text.lower()) or _looks_like_error_text(text.lower()) else PHASE_INVESTIGATION
            results.append((phase, _safe_evidence(text), feature))
        return results
    if _is_user_event(event):
        if text:
            results.append((PHASE_REQUEST, _safe_evidence(text), feature))
        return results
    if tool_name:
        phase = _phase_for_tool(tool_name, cmd_text)
        results.append((phase, _safe_evidence(f"{tool_name} {cmd_text}"), feature))
        return results
    if event_type == "event_msg" and isinstance(payload, dict):
        payload_type = scalar_to_string(payload.get("type")) or ""
        if payload_type in {"patch_apply_end", "file_change"}:
            results.append((PHASE_IMPLEMENTATION, _safe_evidence(text or payload_type), feature))
            return results
        if payload_type in {"task_complete"}:
            results.append((PHASE_VALIDATION, _safe_evidence(text or payload_type), feature))
            return results
    if text:
        lower = text.lower()
        if _looks_like_validation_text(lower):
            results.append((PHASE_VALIDATION, _safe_evidence(text), feature))
        elif _looks_like_understanding_text(lower):
            results.append((PHASE_UNDERSTANDING, _safe_evidence(text), feature))
        elif _looks_like_research_text(lower):
            results.append((PHASE_INVESTIGATION, _safe_evidence(text), feature))
    return results


def _phase_for_tool(tool_name: str, cmd_text: str) -> Optional[str]:
    lower_name = tool_name.lower()
    lower_cmd = cmd_text.lower()
    if "apply_patch" in lower_name or "edit" in lower_name or "write" in lower_name:
        return PHASE_IMPLEMENTATION
    if "screenshot" in lower_name or re.search(r"\b(pytest|unittest|npm test|pnpm test|yarn test|swift test|xcodebuild test|cargo test|go test|ruff|mypy|plutil|shellcheck)\b", lower_cmd):
        return PHASE_VALIDATION
    if re.search(r"\b(rg|grep|sed -n|ls|find|head|tail|sqlite3|git status|git diff|cat|jq|curl -i|curl -v)\b", lower_cmd):
        return PHASE_INVESTIGATION
    if any(name in lower_name for name in ["web_search", "search", "open", "read", "find", "view", "browser", "chrome"]):
        return PHASE_INVESTIGATION
    if re.search(r"\b(mkdir|cp|mv|npm install|python -m pip|git add)\b", lower_cmd):
        return PHASE_IMPLEMENTATION
    return None


def _event_text(event: Dict[str, Any]) -> str:
    parts: List[str] = []
    payload = event.get("payload")
    if isinstance(payload, dict):
        for key in ["message", "last_agent_message", "stdout", "stderr"]:
            value = payload.get(key)
            if isinstance(value, str):
                parts.append(value)
    for obj in iter_json_objects(event):
        role = scalar_to_string(obj.get("role"))
        if role in {"user", "assistant", "toolResult", "tool_result"}:
            text = first_text(obj.get("content"))
            if text:
                parts.append(text)
    return " ".join(parts)


def _is_user_event(event: Dict[str, Any]) -> bool:
    payload = event.get("payload")
    if isinstance(payload, dict) and payload.get("type") == "user_message":
        return True
    return any(scalar_to_string(obj.get("role")) == "user" for obj in iter_json_objects(event)) and not _is_tool_result_event(event)


def _is_tool_result_event(event: Dict[str, Any]) -> bool:
    event_type = scalar_to_string(event.get("type")) or ""
    if event_type in {"toolResult", "tool_result"}:
        return True
    for obj in iter_json_objects(event):
        role = scalar_to_string(obj.get("role")) or ""
        item_type = scalar_to_string(obj.get("type")) or ""
        if role in {"toolResult", "tool_result"} or item_type in {"toolResult", "tool_result"}:
            return True
    return False


def _tool_call(event: Dict[str, Any]) -> Tuple[Optional[str], Optional[Any]]:
    best_name: Optional[str] = None
    best_args: Optional[Any] = None
    for obj in iter_json_objects(event):
        item_type = scalar_to_string(obj.get("type")) or ""
        name = scalar_to_string(obj.get("name") or obj.get("tool_name"))
        arguments = obj.get("arguments") if obj.get("arguments") is not None else obj.get("input")
        if name and ("function_call" in item_type or item_type.endswith("_call") or item_type == "tool_use" or arguments is not None):
            best_name = name
            best_args = arguments
    return best_name, best_args


def _argument_text(arguments: Any) -> str:
    if arguments is None:
        return ""
    if isinstance(arguments, str):
        try:
            decoded = json.loads(arguments)
            return _argument_text(decoded)
        except json.JSONDecodeError:
            return arguments
    if isinstance(arguments, dict):
        for key in ["cmd", "command", "query", "url", "path", "file_path"]:
            value = arguments.get(key)
            if isinstance(value, str):
                return value
        return json.dumps(arguments, sort_keys=True)
    return scalar_to_string(arguments) or ""


def _command_labels(event: Dict[str, Any]) -> Iterable[str]:
    tool_name, arguments = _tool_call(event)
    if not tool_name:
        return []
    text = _argument_text(arguments).lower()
    labels: List[str] = []
    if re.search(r"\b(pytest|unittest|npm test|pnpm test|swift test|go test|cargo test)\b", text):
        labels.append("test")
    if re.search(r"\bcurl\b|\bfetch\s*\(|\bfetch-url\b|request manifest|request replay", text):
        labels.append("request-replay")
    if "launchctl" in text or ".plist" in text or "systemctl" in text:
        labels.append("service-inventory")
    if "cookies" in text or "cookie" in text:
        labels.append("cookie")
    return labels


def _feature_from_text(text: str) -> Optional[str]:
    if not text:
        return None
    has_auth = re.search(r"\b(cookie|cookies|csrf|bearer|authorization|auth state|authenticated)\b", text)
    has_replay = re.search(r"\b(har|cdp|curl|request manifest|request replay)\b|\bfetch\s*\(", text)
    if has_auth and has_replay:
        return "browser_request_replay"
    if re.search(r"\b(lxs01|pi worker|launchd|launchctl|systemd|plist|service inventory|repo instruction)\b", text):
        return "project_memory"
    if re.search(r"\b(known gap|lesson|learned|should have|next time|missing skill|missing helper|prompt update)\b", text):
        return "rediscovered_lesson"
    return None


def _looks_like_understanding_text(text: str) -> bool:
    return bool(re.search(r"\b(found|issue|root cause|main thing|diagnos|understand|plan|risk|gap|lesson|learned|looks like|turns out)\b", text))


def _looks_like_validation_text(text: str) -> bool:
    return bool(re.search(r"\b(test|validated|verified|smoke|passes|fails|known gaps|checks run|lint|screenshot)\b", text))


def _looks_like_error_text(text: str) -> bool:
    return bool(re.search(r"\b(error|exception|traceback|failed|enoent|timed out|nonzero|exit code)\b", text))


def _looks_like_research_text(text: str) -> bool:
    return bool(re.search(r"\b(reading|inspecting|searching|checking|looking at|found the repo|schema|docs|discovery)\b", text))


def _append_evidence(span: PhaseSpan, evidence: str, include_snippets: bool) -> None:
    if not evidence:
        return
    if not include_snippets and len(span.evidence) >= 2:
        return
    if evidence not in span.evidence:
        span.evidence.append(evidence)


def _safe_evidence(text: str) -> str:
    if not text:
        return ""
    clean = SENSITIVE_HEADER_RE.sub(lambda match: match.group(1) + ": <redacted>", text)
    clean = CLI_COOKIE_RE.sub(lambda match: match.group(1) + "<redacted>", clean)
    clean = JSON_SECRET_RE.sub(lambda match: match.group(1) + '"<redacted>"', clean)
    clean = BASIC_AUTH_URL_RE.sub(lambda match: match.group(1) + "<redacted>@", clean)
    clean = JWT_RE.sub("<redacted-jwt>", clean)
    clean = SECRET_TEXT_RE.sub(lambda match: match.group(1).split()[0] + "=<redacted>", clean)
    clean = URL_SECRET_RE.sub(lambda match: match.group(1) + "<redacted>", clean)
    clean = COOKIE_RE.sub(lambda match: match.group(1) + "=<redacted>", clean)
    clean = HOME_PATH_RE.sub("/Users/<redacted>/<redacted-path>", clean)
    return bounded_snippet(clean, 180)


def _signal_text(text: str) -> str:
    if not text:
        return ""
    clean = text
    for tag in [
        "INSTRUCTIONS",
        "environment_context",
        "skills_instructions",
        "plugins_instructions",
        "apps_instructions",
        "app-context",
        "permissions instructions",
    ]:
        clean = re.sub(rf"(?is)<{re.escape(tag)}[^>]*>.*?</{re.escape(tag)}>", " ", clean)
    clean = re.sub(r"(?is)# AGENTS\.md instructions.*?(?=<codex_delegation>|$)", " ", clean)
    return re.sub(r"\s+", " ", clean).strip()


def _browser_request_replay_cards(sessions: Sequence[SessionLearning], include_snippets: bool) -> List[LearningCard]:
    matches = [
        s
        for s in sessions
        if s.feature_counts.get("browser_request_replay", 0) >= 2
        and s.command_labels.get("request-replay", 0)
        and _has_feature_understanding(s, "browser_request_replay")
    ]
    if len(matches) < 2:
        return []
    return [
        _card(
            title="Standardize authenticated browser request replay",
            summary="Multiple sessions rediscover cookie/auth/header/request replay mechanics. This is a strong candidate for a skill plus a deterministic safe request-manifest helper.",
            scope="global",
            problem_type="missing skill",
            phase_pattern="request_idea->investigation_research_discovery->understanding",
            sessions=matches,
            snippets=_snippets(matches, "browser_request_replay", include_snippets),
            recommended_destination="skill + deterministic helper",
            fixability="high",
            why_not_auto_fix="Needs human review because browser auth workflows can expose private cookies, tokens, and service-specific rules.",
        )
    ]


def _late_pivot_cards(sessions: Sequence[SessionLearning], include_snippets: bool) -> List[LearningCard]:
    matches = [
        s
        for s in sessions
        if s.transitions.get(f"{PHASE_IMPLEMENTATION}->{PHASE_INVESTIGATION}", 0)
        + s.transitions.get(f"{PHASE_VALIDATION}->{PHASE_INVESTIGATION}", 0)
        >= 2
    ]
    if len(matches) < 2:
        return []
    return [
        _card(
            title="Detect late pivots before spending implementation tokens",
            summary="Several sessions implement or validate before returning to investigation. Some pivots are healthy, but repeated late pivots suggest missing early-context checks or skills.",
            scope="harness-tooling",
            problem_type="repeated mistake",
            phase_pattern="implementation/proof_validation->investigation_research_discovery",
            sessions=matches,
            snippets=_phase_snippets(matches, [PHASE_INVESTIGATION], include_snippets),
            recommended_destination="prompt update or project checklist",
            fixability="medium",
            why_not_auto_fix="A late pivot can be correct behavior; review should distinguish productive exploration from avoidable missed context.",
        )
    ]


def _project_memory_cards(sessions: Sequence[SessionLearning], include_snippets: bool) -> List[LearningCard]:
    by_project: Dict[str, List[SessionLearning]] = defaultdict(list)
    for session in sessions:
        if (
            session.feature_counts.get("project_memory", 0) >= 2
            and session.command_labels.get("service-inventory", 0)
            and _has_feature_understanding(session, "project_memory")
        ):
            by_project[session.project].append(session)
    cards = []
    for project, matches in by_project.items():
        if len(matches) < 2:
            continue
        cards.append(
            _card(
                title=f"Capture repeated setup discovery for {project}",
                summary="Sessions repeatedly touch repo instructions, service inventory, launchd/systemd, LXS01, Pi worker, or related infrastructure details.",
                scope="project" if project != "unknown" else "infrastructure",
                problem_type="project-memory gap",
                phase_pattern="request_idea->investigation_research_discovery",
                sessions=matches,
                snippets=_snippets(matches, "project_memory", include_snippets),
                recommended_destination="AGENTS.md or deterministic helper",
                fixability="high",
                why_not_auto_fix="Project/infrastructure facts can go stale; review should decide whether to document, script, or ignore.",
            )
        )
    return cards


def _validation_loop_cards(sessions: Sequence[SessionLearning], include_snippets: bool) -> List[LearningCard]:
    matches = [s for s in sessions if s.command_labels.get("test", 0) >= 2 or s.transitions.get(f"{PHASE_VALIDATION}->{PHASE_IMPLEMENTATION}", 0) >= 2]
    if len(matches) < 2:
        return []
    return [
        _card(
            title="Review repeated validation loops",
            summary="Multiple sessions show repeated validation/test loops. Some are expected TDD, but repeated loops can reveal missing deterministic diagnostics or unclear failure interpretation.",
            scope="harness-tooling",
            problem_type="recurring failure pattern",
            phase_pattern="proof_validation->implementation repeated",
            sessions=matches,
            snippets=_phase_snippets(matches, [PHASE_VALIDATION], include_snippets),
            recommended_destination="deterministic helper or test-debug skill",
            fixability="medium",
            why_not_auto_fix="Loop quality depends on whether each iteration used new evidence; the miner only flags review candidates.",
        )
    ]


def _missing_validation_cards(sessions: Sequence[SessionLearning], include_snippets: bool) -> List[LearningCard]:
    matches = [
        s
        for s in sessions
        if any(span.phase == PHASE_IMPLEMENTATION for span in s.spans)
        and not any(span.phase == PHASE_VALIDATION for span in s.spans)
    ]
    if len(matches) < 3:
        return []
    return [
        _card(
            title="Require proof after implementation",
            summary="Several sessions entered implementation but produced no deterministic proof/validation phase. These are candidates for a prompt nudge or project-specific verification checklist.",
            scope="harness-tooling",
            problem_type="missing validation",
            phase_pattern="implementation without proof_validation",
            sessions=matches,
            snippets=_phase_snippets(matches, [PHASE_IMPLEMENTATION], include_snippets),
            recommended_destination="prompt update or validation skill",
            fixability="medium",
            why_not_auto_fix="Some tasks are documentation-only or exploratory; review should confirm whether proof was genuinely missing.",
        )
    ]


def _rediscovered_lesson_cards(sessions: Sequence[SessionLearning], include_snippets: bool) -> List[LearningCard]:
    matches = [s for s in sessions if s.feature_counts.get("rediscovered_lesson", 0)]
    if len(matches) < 2:
        return []
    return [
        _card(
            title="Promote explicit rediscovered lessons to durable context",
            summary="Several sessions contain explicit lesson/gap/next-time language. These are high-signal candidates for skills, prompt updates, project notes, or helper tools.",
            scope="harness-tooling",
            problem_type="rediscovered lesson",
            phase_pattern="understanding->proof_validation",
            sessions=matches,
            snippets=_snippets(matches, "rediscovered_lesson", include_snippets),
            recommended_destination="review queue",
            fixability="high",
            why_not_auto_fix="The wording is high signal but still needs deduplication and owner choice.",
        )
    ]


def _card(
    title: str,
    summary: str,
    scope: str,
    problem_type: str,
    phase_pattern: str,
    sessions: Sequence[SessionLearning],
    snippets: List[str],
    recommended_destination: str,
    fixability: str,
    why_not_auto_fix: str,
) -> LearningCard:
    return LearningCard(
        title=title,
        summary=summary,
        scope=scope,
        problem_type=problem_type,
        phase_pattern=phase_pattern,
        evidence_sessions=[session.session_id for session in sessions[:20]],
        evidence_snippets=snippets[:6],
        source_counts=dict(sorted(Counter(session.source for session in sessions).items())),
        phase_counts=_phase_counts(sessions),
        frequency=len(sessions),
        token_impact=sum(session.total_tokens for session in sessions),
        confidence="high" if len(sessions) >= 3 else "medium",
        fixability=fixability,
        recommended_destination=recommended_destination,
        why_not_auto_fix=why_not_auto_fix,
    )


def _phase_counts(sessions: Sequence[SessionLearning]) -> Dict[str, int]:
    counts: Counter[str] = Counter()
    for session in sessions:
        counts.update({span.phase for span in session.spans})
    return dict(sorted(counts.items()))


def _snippets(sessions: Sequence[SessionLearning], feature: str, include_snippets: bool) -> List[str]:
    snippets: List[str] = []
    for session in sessions:
        if not include_snippets:
            snippets.append(f"{session.session_id}: {feature} signals={session.feature_counts.get(feature, 0)}")
            continue
        for evidence in session.feature_evidence.get(feature, [])[:8]:
            if evidence and evidence not in snippets:
                snippets.append(f"{session.session_id}: {evidence}")
                break
    return snippets


def _has_feature_understanding(session: SessionLearning, feature: str) -> bool:
    evidence = " ".join(session.feature_evidence.get(feature, [])).lower()
    if not evidence:
        return False
    return bool(re.search(r"\b(found|issue|lesson|gap|should|need|redacted|manifest|inventory|service)\b", evidence))


def _merge_duplicate_sessions(sessions: Sequence[SessionLearning]) -> List[SessionLearning]:
    merged: Dict[str, SessionLearning] = {}
    for session in sessions:
        key = f"{session.source}:{session.session_id}"
        existing = merged.get(key)
        if existing is None:
            merged[key] = session
            continue
        starts = [value for value in [existing.start_time, session.start_time] if value]
        ends = [value for value in [existing.end_time, session.end_time] if value]
        existing.start_time = min(starts) if starts else existing.start_time
        existing.end_time = max(ends) if ends else existing.end_time
        existing.total_tokens = max(existing.total_tokens, session.total_tokens)
        existing.spans.extend(session.spans)
        existing.transitions.update(session.transitions)
        existing.feature_counts.update(session.feature_counts)
        existing.command_labels.update(session.command_labels)
        for feature, values in session.feature_evidence.items():
            bucket = existing.feature_evidence.setdefault(feature, [])
            for value in values:
                if value not in bucket and len(bucket) < 20:
                    bucket.append(value)
        for value in session.evidence_terms:
            if value not in existing.evidence_terms and len(existing.evidence_terms) < 40:
                existing.evidence_terms.append(value)
    return list(merged.values())


def _phase_snippets(sessions: Sequence[SessionLearning], phases: Sequence[str], include_snippets: bool) -> List[str]:
    snippets: List[str] = []
    phase_set = set(phases)
    for session in sessions:
        if not include_snippets:
            snippets.append(f"{session.session_id}: transitions={dict(session.transitions)}")
            continue
        for span in session.spans:
            if span.phase in phase_set and span.evidence:
                snippets.append(f"{session.session_id}: {span.evidence[0]}")
                break
    return snippets


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(prog="codex-lesson-miner", description="Mine local agent sessions for recurring lessons and improvement candidates.")
    parser.add_argument("--paths", nargs="*", help="Specific JSONL files or directories to scan")
    parser.add_argument("--source", choices=[SOURCE_CODEX, SOURCE_CLAUDE, SOURCE_PI, SOURCE_GENERIC, SOURCE_ALL], default=SOURCE_CODEX)
    parser.add_argument("--since", help="Only include sessions whose start date is on/after YYYY-MM-DD")
    parser.add_argument("--days", type=int, help="Scan sessions from the last N local days")
    parser.add_argument("--format", choices=["md", "json"], default="md")
    parser.add_argument("--output", help="Write report to file instead of stdout")
    parser.add_argument("--top", type=int, default=20)
    parser.add_argument("--include-snippets", action="store_true", help="Include bounded redacted evidence snippets")
    args = parser.parse_args(argv)

    since = args.since
    if args.days is not None:
        import datetime as dt

        since_date = dt.date.today() - dt.timedelta(days=max(args.days - 1, 0))
        since = since_date.isoformat()
    report = build_learning_report(paths=args.paths, since=since, include_snippets=args.include_snippets, source=args.source)
    output = render_learning_json(report) if args.format == "json" else render_learning_markdown(report, top=args.top)
    if args.output:
        path = Path(args.output).expanduser()
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(output, encoding="utf-8")
    else:
        print(output, end="")
    return 0
