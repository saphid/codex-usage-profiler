from __future__ import annotations

import re
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
    warnings: List[str] = field(default_factory=list)


def build_paperclip_index(config: Config) -> PaperclipIndex:
    root = Path(config.paperclip_root).expanduser()
    index = PaperclipIndex(root=str(root))
    if not config.paperclip_enabled or not root.exists():
        return index
    _index_agents(root, index)
    _index_projects(root, index)
    return index


def apply_paperclip_attribution(records: List[SessionRecord], index: PaperclipIndex) -> None:
    if not index.companies and not index.agents and not index.projects:
        return
    for record in records:
        context = _context_from_record(record)
        company_id = context.get("company_id")
        agent_id = context.get("agent_id")
        project_id = context.get("project_id")

        company_label = _feature(record, "company") or (index.companies.get(company_id or "") if company_id else None)
        project_label = _feature(record, "project") or (index.projects.get(project_id or "") if project_id else None)
        agent = index.agents.get(agent_id or "") if agent_id else None
        staff_label = _feature(record, "submitted_by") or _feature(record, "agent") or (agent.staff_label if agent else None)
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
            index.companies[company_id] = _choose_company_label(index.companies.get(company_id), company)
        index.agents[agent_id] = PaperclipAgent(
            company_id=company_id,
            agent_id=agent_id,
            staff_label=staff,
            company_label=company,
            evidence=[str(instructions)],
        )


def _index_projects(root: Path, index: PaperclipIndex) -> None:
    project_votes: Dict[str, Counter[str]] = defaultdict(Counter)
    company_votes: Dict[str, Counter[str]] = defaultdict(Counter)
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
        for candidate in _labels_from_project_files(path):
            project_votes[project_id][candidate] += 1
            company_votes[company_id][candidate] += 1
    for project_id, votes in project_votes.items():
        if votes:
            index.projects[project_id] = votes.most_common(1)[0][0]
    for company_id, votes in company_votes.items():
        if votes and company_id not in index.companies:
            index.companies[company_id] = votes.most_common(1)[0][0]


def _labels_from_project_files(path: Path) -> Iterable[str]:
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


def _context_from_record(record: SessionRecord) -> Dict[str, str]:
    blob = "\n".join(value for value in [record.path, record.cwd or "", *record.workspace_roots] if value)
    result: Dict[str, str] = {}
    match = re.search(rf"/(?:\.paperclip|paperclip)/instances/[^/]+/companies/({UUID_RE})(?:/agents/({UUID_RE}))?/codex-home/", blob)
    if match:
        result["company_id"] = match.group(1)
        if match.group(2):
            result["agent_id"] = match.group(2)
    match = re.search(rf"/(?:\.paperclip|paperclip)/instances/[^/]+/projects/({UUID_RE})/({UUID_RE})/", blob)
    if match:
        result["company_id"] = match.group(1)
        result["project_id"] = match.group(2)
    match = re.search(rf"/(?:\.paperclip|paperclip)/instances/[^/]+/workspaces/({UUID_RE})(?:/|$)", blob)
    if match:
        result["agent_id"] = match.group(1)
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


def _choose_company_label(current: Optional[str], candidate: str) -> str:
    if not current:
        return candidate
    if current.startswith("paperclip-company:"):
        return candidate
    if len(candidate) < len(current) or candidate in {"DY Sphere", "STA", "Dinner with Kids", "Min Apps"}:
        return candidate
    return current


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
    path_blob = record.cwd or ""
    match = re.search(r"\b(DYS-\d+)\b", path_blob, re.IGNORECASE)
    if match:
        return match.group(1).upper()
    return None


def _looks_like_uuid_label(label: str) -> bool:
    return bool(re.fullmatch(UUID_RE, label) or re.fullmatch(r"[0-9a-f]{8}", label))
