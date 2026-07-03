from __future__ import annotations

import re
import json
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, Iterable, List, Optional

from .config import Config
from .models import Attribution, SessionRecord
from .util import bounded_snippet


UUID_RE = r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}"


@dataclass
class PaperclipAgent:
    company_id: str
    agent_id: str
    staff_label: str
    company_label: Optional[str] = None
    evidence: List[str] = field(default_factory=list)


@dataclass
class PaperclipIndex:
    root: str
    companies: Dict[str, str] = field(default_factory=dict)
    agents: Dict[str, PaperclipAgent] = field(default_factory=dict)
    projects: Dict[str, str] = field(default_factory=dict)
    company_votes: Dict[str, Counter[str]] = field(default_factory=lambda: defaultdict(Counter))
    warnings: List[str] = field(default_factory=list)


def build_paperclip_index(config: Config, paths: Optional[List[str]] = None) -> PaperclipIndex:
    root = Path(config.paperclip_root).expanduser()
    index = PaperclipIndex(root=str(root))
    if not config.paperclip_enabled:
        return index
    if root.exists():
        _index_agents(root, index)
        _index_projects(root, index)
    _index_collected_metadata(paths or [], index)
    _finalize_company_labels(index)
    _apply_config_aliases(index, config)
    return index


def apply_paperclip_attribution(records: List[SessionRecord], index: PaperclipIndex) -> None:
    for record in records:
        context = _context_from_record(record)
        company_id = context.get("company_id")
        agent_id = context.get("agent_id")
        project_id = context.get("project_id")
        if not agent_id and context.get("workspace_id") in index.agents:
            agent_id = context.get("workspace_id")
        agent = index.agents.get(agent_id or "") if agent_id else None
        if not company_id and agent:
            company_id = agent.company_id

        company_label = _feature(record, "company") or (index.companies.get(company_id or "") if company_id else None)
        project_label = _feature(record, "project") or (index.projects.get(project_id or "") if project_id else None)
        staff_label = _feature(record, "staff") or _feature(record, "submitted_by") or _feature(record, "agent") or (agent.staff_label if agent else None)
        paperclip_task = _paperclip_task_label(record)

        if company_label:
            record.paperclip_company = Attribution(company_label, "high", [f"paperclip.company_id:{company_id}"] if company_id else ["first_request.company"])
        elif company_id:
            record.paperclip_company = Attribution(f"paperclip-company:{company_id[:8]}", "medium", [f"paperclip.company_id:{company_id}"])

        if project_label:
            evidence = [f"paperclip.project_id:{project_id}"] if project_id else ["first_request.project"]
            record.paperclip_project = Attribution(project_label, "high", evidence)
            record.project = Attribution(project_label, "high", evidence)
        elif company_label:
            record.paperclip_project = Attribution(company_label, "medium", ["paperclip company fallback"])
            if _looks_like_uuid_label(record.project.label):
                record.project = Attribution(company_label, "medium", ["paperclip company fallback"])

        if staff_label:
            evidence = [f"paperclip.agent_id:{agent_id}"] if agent_id else ["first_request staff field"]
            record.paperclip_staff = Attribution(staff_label, "high", evidence)
            if record.client.label in {"Codex CLI", "Codex exec", "unknown"}:
                record.client = Attribution(f"Paperclip: {staff_label}", "high", evidence)
        elif agent_id:
            record.paperclip_staff = Attribution(f"paperclip-agent:{agent_id[:8]}", "medium", [f"paperclip.agent_id:{agent_id}"])

        if paperclip_task:
            record.paperclip_task = Attribution(paperclip_task, "high", ["first_request/project path issue signal"])
            record.task = Attribution(paperclip_task, "high", ["paperclip task signal"])
        elif record.paperclip_staff.label != "unknown" and record.task.label.startswith("request:"):
            record.task = Attribution(f"paperclip:{record.paperclip_staff.label}", "medium", ["paperclip staff fallback"])


def _index_agents(root: Path, index: PaperclipIndex) -> None:
    for instructions in root.glob("companies/*/agents/*/instructions/AGENTS.md"):
        parts = instructions.parts
        try:
            company_id = parts[parts.index("companies") + 1]
            agent_id = parts[parts.index("agents") + 1]
        except (ValueError, IndexError):
            continue
        try:
            text = instructions.read_text(encoding="utf-8", errors="replace")
        except OSError as exc:
            index.warnings.append(f"paperclip_agent_read_failed:{agent_id}:{type(exc).__name__}")
            continue
        staff = _extract_staff_label(text) or f"paperclip-agent:{agent_id[:8]}"
        company = _extract_company_label(text)
        if company:
            _vote_company(index, company_id, company)
        index.agents[agent_id] = PaperclipAgent(
            company_id=company_id,
            agent_id=agent_id,
            staff_label=staff,
            company_label=company,
            evidence=[str(instructions)],
        )


def _index_projects(root: Path, index: PaperclipIndex) -> None:
    project_votes: Dict[str, Counter[str]] = defaultdict(Counter)
    projects_root = root / "projects"
    if not projects_root.exists():
        return
    for path in projects_root.glob("*/*/_default"):
        if not path.is_dir():
            continue
        parts = path.parts
        try:
            company_id = parts[parts.index("projects") + 1]
            project_id = parts[parts.index("projects") + 2]
        except (ValueError, IndexError):
            continue
        for candidate in _project_labels_from_project_files(path):
            project_votes[project_id][candidate] += 1
        for candidate in _company_labels_from_project_files(path):
            _vote_company(index, company_id, candidate, weight=8)
    for project_id, votes in project_votes.items():
        if votes:
            index.projects[project_id] = votes.most_common(1)[0][0]


def _index_collected_metadata(paths: List[str], index: PaperclipIndex) -> None:
    for metadata_path in _discover_collected_metadata(paths):
        try:
            payload = json.loads(metadata_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            index.warnings.append(f"paperclip_metadata_read_failed:{metadata_path}:{type(exc).__name__}")
            continue
        if not isinstance(payload, dict):
            continue
        _index_metadata_payload(payload, metadata_path, index)


def _discover_collected_metadata(paths: List[str]) -> List[Path]:
    found: List[Path] = []
    seen: set[Path] = set()
    for raw in paths:
        path = Path(raw).expanduser()
        candidates: Iterable[Path]
        if path.is_file() and path.name == "paperclip-metadata.json":
            candidates = [path]
        elif path.is_dir():
            candidates = path.rglob("paperclip-metadata.json")
        else:
            candidates = []
        for candidate in candidates:
            resolved = candidate.resolve()
            if resolved not in seen:
                seen.add(resolved)
                found.append(resolved)
    return found


def _index_metadata_payload(payload: Dict[str, object], path: Path, index: PaperclipIndex) -> None:
    company_by_prefix: Dict[str, str] = {}
    for row in payload.get("companies", []) if isinstance(payload.get("companies"), list) else []:
        if not isinstance(row, dict):
            continue
        company_id = str(row.get("id") or "")
        name = str(row.get("name") or "")
        prefix = str(row.get("issuePrefix") or "").upper()
        if company_id and name:
            index.companies[company_id] = name
            _vote_company(index, company_id, name, weight=20)
        if company_id and prefix:
            company_by_prefix[prefix] = company_id
    for row in payload.get("projects", []) if isinstance(payload.get("projects"), list) else []:
        if not isinstance(row, dict):
            continue
        project_id = str(row.get("id") or "")
        name = str(row.get("name") or "")
        company_id = str(row.get("companyId") or "")
        if project_id and name:
            index.projects[project_id] = name
        if company_id and company_id in index.companies:
            _vote_company(index, company_id, index.companies[company_id], weight=5)
    for row in payload.get("agents", []) if isinstance(payload.get("agents"), list) else []:
        if not isinstance(row, dict):
            continue
        agent_id = str(row.get("id") or "")
        company_id = str(row.get("companyId") or "")
        if not agent_id or not company_id:
            continue
        staff = _staff_label_from_metadata_agent(row)
        index.agents[agent_id] = PaperclipAgent(
            company_id=company_id,
            agent_id=agent_id,
            staff_label=staff,
            company_label=index.companies.get(company_id),
            evidence=[str(path)],
        )
    for row in payload.get("workspaces", []) if isinstance(payload.get("workspaces"), list) else []:
        if not isinstance(row, dict):
            continue
        workspace_id = str(row.get("id") or "")
        company_id = str(row.get("companyId") or "")
        if not company_id:
            prefixes = [str(item).upper() for item in row.get("issuePrefixes", [])] if isinstance(row.get("issuePrefixes"), list) else []
            for prefix in prefixes:
                if prefix in company_by_prefix:
                    company_id = company_by_prefix[prefix]
                    break
        staff = str(row.get("staffLabel") or "") or f"paperclip-workspace:{workspace_id[:8]}"
        if workspace_id and company_id:
            index.agents.setdefault(
                workspace_id,
                PaperclipAgent(
                    company_id=company_id,
                    agent_id=workspace_id,
                    staff_label=staff,
                    company_label=index.companies.get(company_id),
                    evidence=[str(path)],
                ),
            )


def _staff_label_from_metadata_agent(row: Dict[str, object]) -> str:
    for key in ["title", "name", "role"]:
        value = str(row.get(key) or "").strip()
        if value:
            return bounded_snippet(value, 80)
    agent_id = str(row.get("id") or "")
    return f"paperclip-agent:{agent_id[:8]}"


def _project_labels_from_project_files(path: Path) -> Iterable[str]:
    names = [item.name for item in path.iterdir() if item.is_file() and item.suffix.lower() in {".md", ".json", ".jsonl"}]
    blob = " ".join(names).lower()
    if "dinner-with-kids" in blob or "family-dinners" in blob:
        yield "Dinner with Kids"
    if "start2scale" in blob or "sta" in blob:
        yield "STA"
    if "birdnet" in blob or "frigate" in blob:
        yield "Min Apps"
    for name in names[:20]:
        stem = name.rsplit(".", 1)[0]
        cleaned = re.sub(r"^(max|min|dys)-\d+-", "", stem)
        cleaned = re.sub(r"[-_]+", " ", cleaned).strip()
        if cleaned:
            yield cleaned.title()


def _company_labels_from_project_files(path: Path) -> Iterable[str]:
    names = [item.name.lower() for item in path.iterdir() if item.is_file()]
    prefixes = Counter()
    for name in names:
        match = re.match(r"([a-z]+)-\d+[-_.]", name)
        if match:
            prefixes[match.group(1)] += 1
    if prefixes.get("max"):
        yield "Maximum Goat"
    if prefixes.get("min"):
        yield "Min Apps"
    if prefixes.get("dys"):
        yield "DY Sphere"
    if prefixes.get("sta"):
        yield "STA"


def _context_from_record(record: SessionRecord) -> Dict[str, str]:
    blob = "\n".join(value for value in [record.path, record.source_path or "", record.cwd or "", *record.workspace_roots] if value)
    result: Dict[str, str] = {
        key: value
        for key, value in {
            "company_id": _feature(record, "company_id"),
            "agent_id": _feature(record, "agent_id"),
            "project_id": _feature(record, "project_id"),
            "workspace_id": _feature(record, "workspace_id"),
        }.items()
        if value
    }
    match = re.search(rf"/(?:\.paperclip|paperclip)/instances/[^/]+/companies/({UUID_RE})(?:/agents/({UUID_RE}))?/codex-home/", blob)
    if match:
        result.setdefault("company_id", match.group(1))
        if match.group(2):
            result.setdefault("agent_id", match.group(2))
    match = re.search(rf"/(?:\.paperclip|paperclip)/instances/[^/]+/projects/({UUID_RE})/({UUID_RE})/", blob)
    if match:
        result.setdefault("company_id", match.group(1))
        result.setdefault("project_id", match.group(2))
    match = re.search(rf"/(?:\.paperclip|paperclip)/instances/[^/]+/workspaces/({UUID_RE})(?:/|$)", blob)
    if match:
        result.setdefault("workspace_id", match.group(1))
        result.setdefault("agent_id", match.group(1))
    return result


def _extract_staff_label(text: str) -> Optional[str]:
    first_lines = "\n".join(text.splitlines()[:8])
    match = re.search(r"(?im)^#\s+(.+?)\s*$", first_lines)
    if match:
        label = match.group(1).strip()
        if label and label.lower() not in {"paperclip company"}:
            return label
    patterns = [
        r"You are agent\s+(.+?)\s+\(",
        r"You are the\s+(.+?)\s+for\s+([A-Z][A-Za-z0-9 &/.-]+)",
        r"You are the\s+(.+?)\.",
    ]
    for pattern in patterns:
        match = re.search(pattern, first_lines)
        if match:
            return bounded_snippet(match.group(1).strip(), 80)
    return None


def _extract_company_label(text: str) -> Optional[str]:
    first_lines = "\n".join(text.splitlines()[:12])
    known = ["DY Sphere", "Dinner with Kids", "STA", "Min Apps"]
    for name in known:
        if re.search(re.escape(name), first_lines, re.IGNORECASE):
            return name
    match = re.search(r"\bat\s+([A-Z][A-Za-z0-9 &/.-]+?)\.", first_lines)
    if match:
        return _clean_company(match.group(1))
    match = re.search(r"\bfor\s+([A-Z][A-Za-z0-9 &/.-]+?)\.", first_lines)
    if match:
        return _clean_company(match.group(1))
    return None


def _vote_company(index: PaperclipIndex, company_id: str, candidate: str, weight: int = 1) -> None:
    if not company_id or not candidate:
        return
    index.company_votes[company_id][candidate] += weight


def _finalize_company_labels(index: PaperclipIndex) -> None:
    for company_id, votes in index.company_votes.items():
        if votes:
            index.companies[company_id] = votes.most_common(1)[0][0]


def _apply_config_aliases(index: PaperclipIndex, config: Config) -> None:
    for company_id, label in config.paperclip_company_aliases.items():
        if label:
            index.companies[company_id] = label
    for project_id, label in config.paperclip_project_aliases.items():
        if label:
            index.projects[project_id] = label
    for agent_id, label in config.paperclip_agent_aliases.items():
        agent = index.agents.get(agent_id)
        if agent and label:
            agent.staff_label = label


def _clean_company(value: str) -> str:
    cleaned = value.strip().rstrip(",")
    if cleaned.lower() in {"the company", "company", "the local paperclip company"}:
        return "Paperclip Company"
    return cleaned


def _feature(record: SessionRecord, key: str) -> Optional[str]:
    value = record.first_request_features.get(key)
    return value if value and value.lower() not in {"unknown", "none"} else None


def _paperclip_task_label(record: SessionRecord) -> Optional[str]:
    features = record.first_request_features
    if features.get("issue"):
        return features["issue"]
    if features.get("task"):
        return features["task"]
    path_blob = "\n".join(value for value in [record.cwd or "", record.source_path or "", record.path, *record.workspace_roots] if value)
    match = re.search(r"\b([A-Z]{2,10}-\d+)\b", path_blob, re.IGNORECASE)
    if match:
        return match.group(1).upper()
    match = re.search(r"\b([a-z]{2,10})[-_](\d{1,6})\b", path_blob, re.IGNORECASE)
    if match:
        return f"{match.group(1).upper()}-{match.group(2)}"
    return None


def _looks_like_uuid_label(label: str) -> bool:
    return bool(re.fullmatch(UUID_RE, label) or re.fullmatch(r"[0-9a-f]{8}", label))
