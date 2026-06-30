from __future__ import annotations

from collections import Counter, defaultdict
from typing import Dict, Iterable, List, Optional, Tuple

from .models import Attribution, Finding, SessionRecord
from .util import day_key, hour_key


def classify_outcomes(records: List[SessionRecord]) -> None:
    for record in records:
        tool_total = sum(record.tool_counts.values())
        evidence: List[str] = []
        if record.file_edit_markers:
            evidence.append(f"edit_markers={record.file_edit_markers}")
        if record.test_markers:
            evidence.append(f"test_markers={record.test_markers}")
        if record.error_markers:
            evidence.append(f"error_markers={record.error_markers}")
        if record.thread_source == "automation":
            evidence.append("thread_source=automation")
        if record.thread_source == "subagent":
            evidence.append("thread_source=subagent")

        if record.file_edit_markers or _has_action_tool(record):
            record.outcome = Attribution("durable-output", "medium", evidence or ["durable/action tool marker"])
        elif record.error_markers:
            record.outcome = Attribution("blocked", "medium", evidence)
        elif tool_total == 0 and record.usage.get("total_tokens", 0) < 5000:
            record.outcome = Attribution("no-op", "medium", evidence or ["low tokens and no tool calls"])
        elif tool_total <= 1 and record.usage.get("input_tokens", 0) > 75000:
            record.outcome = Attribution("startup-heavy", "medium", evidence or ["large input, little tool activity"])
        elif tool_total > 0:
            record.outcome = Attribution("exploratory", "low", evidence or ["tool activity without durable output marker"])
        else:
            record.outcome = Attribution("unknown", "low", evidence or ["insufficient evidence"])


def find_waste_candidates(records: List[SessionRecord]) -> List[Finding]:
    findings: List[Finding] = []
    findings.extend(_find_paperclip_repeated_healthchecks(records))
    findings.extend(_find_noop_automation(records))
    findings.extend(_find_retry_loops(records))
    findings.extend(_find_repeated_tools(records))
    findings.extend(_find_startup_heavy(records))
    findings.extend(_find_test_loops(records))
    return sorted(findings, key=lambda item: item.total_tokens, reverse=True)


def aggregate(records: List[SessionRecord], key: str) -> List[Dict[str, object]]:
    buckets: Dict[str, Dict[str, object]] = {}
    total_tokens_all = sum(r.usage.get("total_tokens", 0) for r in records)
    for record in records:
        label = _key(record, key)
        bucket = buckets.setdefault(
            label,
            {
                "label": label,
                "sessions": 0,
                "input_tokens": 0,
                "cached_input_tokens": 0,
                "output_tokens": 0,
                "total_tokens": 0,
                "estimated_cost_usd": 0.0,
                "estimated_credits": 0.0,
                "observed_share_percent": 0.0,
                "top_models": Counter(),
                "top_clients": Counter(),
                "outcomes": Counter(),
            },
        )
        bucket["sessions"] = int(bucket["sessions"]) + 1
        for token_key in ["input_tokens", "cached_input_tokens", "output_tokens", "total_tokens"]:
            bucket[token_key] = int(bucket[token_key]) + record.usage.get(token_key, 0)
        if record.estimate.cost_usd is not None:
            bucket["estimated_cost_usd"] = float(bucket["estimated_cost_usd"]) + record.estimate.cost_usd
        if record.estimate.credits is not None:
            bucket["estimated_credits"] = float(bucket["estimated_credits"]) + record.estimate.credits
        bucket["top_models"][record.model or "unknown"] += 1  # type: ignore[index]
        bucket["top_clients"][record.client.label] += 1  # type: ignore[index]
        bucket["outcomes"][record.outcome.label] += 1  # type: ignore[index]
    for bucket in buckets.values():
        if total_tokens_all:
            bucket["observed_share_percent"] = int(bucket["total_tokens"]) / total_tokens_all * 100
        bucket["top_models"] = dict(bucket["top_models"].most_common(5))  # type: ignore[union-attr]
        bucket["top_clients"] = dict(bucket["top_clients"].most_common(5))  # type: ignore[union-attr]
        bucket["outcomes"] = dict(bucket["outcomes"].most_common())  # type: ignore[union-attr]
    return sorted(buckets.values(), key=lambda item: int(item["total_tokens"]), reverse=True)


def build_aggregates(records: List[SessionRecord]) -> Dict[str, List[Dict[str, object]]]:
    return {
        "client": aggregate(records, "client"),
        "project": aggregate(records, "project"),
        "task": aggregate(records, "task"),
        "model": aggregate(records, "model"),
        "thread_source": aggregate(records, "thread_source"),
        "paperclip_company": aggregate(records, "paperclip_company"),
        "paperclip_project": aggregate(records, "paperclip_project"),
        "paperclip_staff": aggregate(records, "paperclip_staff"),
        "paperclip_task": aggregate(records, "paperclip_task"),
        "day": aggregate(records, "day"),
        "hour": aggregate(records, "hour"),
    }


def reconcile_codexbar(records: List[SessionRecord], cost_usage: Optional[Dict[str, object]]) -> List[Dict[str, object]]:
    if not cost_usage:
        return []
    codexbar_daily = cost_usage.get("daily")
    if not isinstance(codexbar_daily, list):
        return []
    local: Dict[Tuple[str, str], int] = defaultdict(int)
    local_dates = set()
    for record in records:
        date = day_key(record.start_time)
        local_dates.add(date)
        local[(date, record.model or "unknown")] += record.usage.get("total_tokens", 0)
    rows: List[Dict[str, object]] = []
    for day in codexbar_daily:
        if not isinstance(day, dict):
            continue
        date = str(day.get("date") or "unknown")
        if local_dates and date not in local_dates:
            continue
        for model in day.get("modelBreakdowns", []) if isinstance(day.get("modelBreakdowns"), list) else []:
            if not isinstance(model, dict):
                continue
            model_name = str(model.get("modelName") or "unknown")
            cb_tokens = int(model.get("totalTokens") or 0)
            local_tokens = local.get((date, model_name), 0)
            coverage = local_tokens / cb_tokens * 100 if cb_tokens else None
            scope_note = "unknown"
            if coverage is not None:
                if coverage < 80:
                    scope_note = "local_logs_missing_or_window_mismatch"
                elif coverage > 120:
                    scope_note = "local_logs_exceed_codexbar_scope"
                else:
                    scope_note = "similar_scope"
            rows.append(
                {
                    "date": date,
                    "model": model_name,
                    "local_tokens": local_tokens,
                    "codexbar_tokens": cb_tokens,
                    "coverage_percent": coverage,
                    "scope_ratio_percent": coverage,
                    "scope_note": scope_note,
                    "codexbar_cost_usd": model.get("cost"),
                }
            )
    return sorted(rows, key=lambda row: abs((row.get("codexbar_tokens") or 0) - (row.get("local_tokens") or 0)), reverse=True)


def _key(record: SessionRecord, key: str) -> str:
    if key == "client":
        return record.client.label
    if key == "project":
        return record.project.label
    if key == "task":
        return record.task.label
    if key == "model":
        return record.model or "unknown"
    if key == "thread_source":
        return record.thread_source or "unknown"
    if key == "paperclip_company":
        return record.paperclip_company.label
    if key == "paperclip_project":
        return record.paperclip_project.label
    if key == "paperclip_staff":
        return record.paperclip_staff.label
    if key == "paperclip_task":
        return record.paperclip_task.label
    if key == "day":
        return day_key(record.start_time)
    if key == "hour":
        return hour_key(record.start_time)
    return "unknown"


def _has_action_tool(record: SessionRecord) -> bool:
    action_names = ["git-commit", "git_commit", "create", "send", "draft", "calendar", "gmail", "apply_patch"]
    blob = " ".join(record.tool_counts.keys()).lower()
    return any(name in blob for name in action_names)


def _finding(kind: str, title: str, records: List[SessionRecord], confidence: str, evidence: List[str]) -> Finding:
    total_tokens = sum(r.usage.get("total_tokens", 0) for r in records)
    costs = [r.estimate.cost_usd for r in records if r.estimate.cost_usd is not None]
    total_cost = sum(costs) if costs else None
    return Finding(
        kind=kind,
        title=title,
        confidence=confidence,
        session_ids=[r.session_id for r in records],
        total_tokens=total_tokens,
        cost_usd=total_cost,
        quota_share_percent=None,
        evidence=evidence,
    )


def _find_noop_automation(records: List[SessionRecord]) -> List[Finding]:
    groups: Dict[str, List[SessionRecord]] = defaultdict(list)
    for record in records:
        if record.thread_source == "automation" and record.outcome.label in {"no-op", "startup-heavy", "unknown"}:
            groups[record.task.label].append(record)
    return [
        _finding("noop_automation", f"No-op automation: {task}", items, "medium", ["thread_source=automation", "low durable output"])
        for task, items in groups.items()
        if len(items) >= 2
    ]


def _find_paperclip_repeated_healthchecks(records: List[SessionRecord]) -> List[Finding]:
    health_labels = {
        "paperclip:api_health",
        "paperclip:launchagent_plist",
        "paperclip:launchctl_service",
        "paperclip:agent_runtime_state",
        "paperclip:agent_list",
        "paperclip:activity_help",
        "paperclip:live_runs",
        "paperclip:launchd_error_log",
        "paperclip:install_readlink",
    }
    groups: Dict[str, List[SessionRecord]] = defaultdict(list)
    for record in records:
        labels = set(record.command_labels)
        matched = sorted(labels & health_labels)
        if not matched or record.paperclip_company.label == "unknown":
            continue
        staff = record.paperclip_staff.label if record.paperclip_staff.label != "unknown" else "unknown-staff"
        project = record.project.label if record.project.label != "unknown" else record.paperclip_company.label
        groups[f"{project}:{staff}"].append(record)
    findings: List[Finding] = []
    for key, items in groups.items():
        if len(items) < 10:
            continue
        labels = Counter(label for record in items for label in record.command_labels if label in health_labels)
        findings.append(
            _finding(
                "paperclip_repeated_healthcheck",
                f"Repeated Paperclip health/runtime checks: {key}",
                items,
                "high",
                [f"{label} x{count}" for label, count in labels.most_common(6)],
            )
        )
    return findings


def _find_retry_loops(records: List[SessionRecord]) -> List[Finding]:
    by_sig: Dict[str, List[SessionRecord]] = defaultdict(list)
    for record in records:
        if record.file_edit_markers:
            continue
        for sig in set(record.command_signatures):
            if ":shell:" in sig or ":test:" in sig:
                by_sig[sig].append(record)
    return [
        _finding("repeated_command_signature", f"Repeated command signature: {sig}", items, "low", [sig, "no edit markers"])
        for sig, items in by_sig.items()
        if len(items) >= 3
    ]


def _find_repeated_tools(records: List[SessionRecord]) -> List[Finding]:
    by_seq: Dict[str, List[SessionRecord]] = defaultdict(list)
    for record in records:
        query_tools = [name for name in record.tool_sequence if "search" in name.lower() or "tool" in name.lower() or "mcp" in name.lower()]
        if len(query_tools) >= 2 and not record.file_edit_markers:
            by_seq[" > ".join(query_tools[:5])].append(record)
    return [
        _finding("repeated_tool_query", f"Repeated tool/query pattern: {seq}", items, "low", [seq])
        for seq, items in by_seq.items()
        if len(items) >= 2
    ]


def _find_startup_heavy(records: List[SessionRecord]) -> List[Finding]:
    items = [
        record
        for record in records
        if record.usage.get("input_tokens", 0) > 100_000
        and sum(record.tool_counts.values()) <= 2
        and not record.file_edit_markers
    ]
    if len(items) < 2:
        return []
    return [_finding("startup_heavy", "Large startup contexts with little action", items, "medium", ["input_tokens>100k", "tool_calls<=2"])]


def _find_test_loops(records: List[SessionRecord]) -> List[Finding]:
    by_sig: Dict[str, List[SessionRecord]] = defaultdict(list)
    for record in records:
        if record.file_edit_markers:
            continue
        for sig in set(record.command_signatures):
            if ":test:" in sig:
                by_sig[sig].append(record)
    return [
        _finding("test_loop", f"Repeated test without edits: {sig}", items, "medium", [sig, "no edit markers"])
        for sig, items in by_sig.items()
        if len(items) >= 2
    ]
