from __future__ import annotations

import json
from typing import Any, Dict, List, Optional

from .models import CodexBarTelemetry, Finding, SessionRecord


def render_json(
    records: List[SessionRecord],
    aggregates: Dict[str, Any],
    findings: List[Finding],
    telemetry: CodexBarTelemetry,
    reconciliation: List[Dict[str, Any]],
    warnings: List[str],
    paperclip_spend: Optional[Dict[str, Any]] = None,
    plan_analysis: Optional[Dict[str, Any]] = None,
    include_snippets: bool = False,
) -> str:
    payload = {
        "run": {
            "session_count": len(records),
            "warning_count": len(warnings) + len(telemetry.warnings),
            "confidence_note": "Local profiler output is investigative. Cost is a directional rate-card estimate, live quota is current-window telemetry when available, and outcome labels are evidence buckets rather than proof of value.",
        },
        "telemetry": telemetry.to_dict(),
        "aggregates": aggregates,
        "paperclip_spend": paperclip_spend or {},
        "plan_analysis": plan_analysis or {},
        "findings": [item.to_dict() for item in findings],
        "reconciliation": reconciliation,
        "sessions": [record.to_dict(include_snippets=include_snippets) for record in records],
        "warnings": warnings + telemetry.warnings,
    }
    return json.dumps(payload, indent=2, sort_keys=True)


def render_text(
    records: List[SessionRecord],
    aggregates: Dict[str, Any],
    findings: List[Finding],
    telemetry: CodexBarTelemetry,
    reconciliation: List[Dict[str, Any]],
    warnings: List[str],
    paperclip_spend: Optional[Dict[str, Any]] = None,
    plan_analysis: Optional[Dict[str, Any]] = None,
    top: int = 10,
    include_snippets: bool = False,
) -> str:
    lines: List[str] = []
    total_tokens = sum(r.usage.get("total_tokens", 0) for r in records)
    total_cost = sum(r.estimate.cost_usd or 0.0 for r in records)
    lines.append("Codex Usage Profiler")
    lines.append("=" * 20)
    lines.append(f"Sessions scanned: {len(records)}")
    lines.append(f"Observed tokens: {total_tokens:,}")
    lines.append(f"Rate-card cost: ${total_cost:,.2f} (directional replacement-cost estimate)")
    lines.append("")
    lines.extend(_render_codexbar(telemetry))
    lines.extend(_render_plan_analysis(plan_analysis or {}))
    lines.extend(_render_aggregate("By client", aggregates.get("client", []), top))
    lines.extend(_render_aggregate("By project", aggregates.get("project", []), top))
    lines.extend(_render_aggregate("By task", aggregates.get("task", []), min(top, 15)))
    lines.extend(_render_paperclip_company_spend(paperclip_spend or {}, top))
    lines.extend(_render_aggregate("Paperclip companies", aggregates.get("paperclip_company", []), top))
    lines.extend(_render_aggregate("Paperclip staff", aggregates.get("paperclip_staff", []), top))
    lines.extend(_render_aggregate("Paperclip tasks", aggregates.get("paperclip_task", []), top))
    lines.extend(_render_aggregate("By model", aggregates.get("model", []), top))
    lines.extend(_render_aggregate("By day", aggregates.get("day", []), top))
    lines.extend(_render_aggregate("Automation/subagents", aggregates.get("thread_source", []), top))
    lines.extend(_render_sessions(records, top, include_snippets))
    lines.extend(_render_findings(findings, top))
    lines.extend(_render_reconciliation(reconciliation, top))
    all_warnings = warnings + telemetry.warnings
    if all_warnings:
        lines.append("")
        lines.append("Warnings")
        lines.append("-" * 8)
        for warning in all_warnings[:top]:
            lines.append(f"- {warning}")
    return "\n".join(lines) + "\n"


def _render_codexbar(telemetry: CodexBarTelemetry) -> List[str]:
    lines = ["CodexBar", "-" * 8]
    if not telemetry.available:
        return lines + ["unavailable", ""]
    lines.append(f"cli: {telemetry.cli_path or 'missing'}")
    if telemetry.app_version:
        lines.append(f"app: {telemetry.app_version}")
    usage = telemetry.live_usage or {}
    if usage:
        lines.append(f"usage source: {usage.get('source') or 'unknown'} confidence: {usage.get('dataConfidence') or 'unknown'}")
        for window in usage.get("windows", []) if isinstance(usage.get("windows"), list) else []:
            if not isinstance(window, dict):
                continue
            title = window.get("title") or window.get("id") or "window"
            used = window.get("usedPercent")
            resets = window.get("resetsAt") or window.get("resetDescription")
            if used is not None:
                lines.append(f"- {title}: {used}% used, resets {resets} (exact_current)")
    cost = telemetry.cost_usage or {}
    if cost:
        lines.append(
            f"CodexBar cost last30: {cost.get('last30DaysTokens', 0):,} tokens, "
            f"${cost.get('last30DaysCostUSD') or 0:,.2f} {cost.get('currencyCode') or 'USD'}"
        )
    lines.append("")
    return lines


def _render_aggregate(title: str, rows: List[Dict[str, Any]], top: int) -> List[str]:
    lines = [title, "-" * len(title)]
    if not rows:
        return lines + ["none", ""]
    lines.append(_fmt_row("label", "sessions", "tokens", "share", "cost"))
    for row in rows[:top]:
        lines.append(
            _fmt_row(
                str(row.get("label", "unknown"))[:34],
                str(row.get("sessions", 0)),
                f"{int(row.get('total_tokens', 0)):,}",
                f"{float(row.get('observed_share_percent', 0.0)):.1f}%",
                f"${float(row.get('estimated_cost_usd', 0.0)):,.2f}",
            )
        )
    lines.append("")
    return lines


def _render_plan_analysis(plan: Dict[str, Any]) -> List[str]:
    lines = ["Plan comparison", "---------------"]
    if not plan:
        return lines + ["none", ""]
    lines.append(
        f"Observed span: {int(plan.get('observed_span_days') or 1)}d | "
        f"observed ${float(plan.get('observed_cost_usd') or 0.0):,.2f} | "
        f"projected {int(plan.get('projection_days') or 30)}d ${float(plan.get('projected_cost_usd') or 0.0):,.2f}"
    )
    rows = plan.get("plans") if isinstance(plan.get("plans"), list) else []
    if not rows:
        lines.append("Add --monthly-plan-price-usd or --plan-price NAME=USD to compare plans.")
        lines.append("")
        return lines
    lines.append(_fmt_row("plan", "price", "projected", "ratio", "delta"))
    for row in rows[:8]:
        ratio = row.get("projected_vs_price_percent")
        lines.append(
            _fmt_row(
                str(row.get("plan", "plan"))[:34],
                f"${float(row.get('monthly_price_usd') or 0.0):,.2f}",
                f"${float(row.get('projected_rate_card_cost_usd') or 0.0):,.2f}",
                "n/a" if ratio is None else f"{float(ratio):.0f}%",
                f"${float(row.get('delta_usd') or 0.0):+,.2f}",
            )
        )
    lines.append("")
    return lines


def _render_paperclip_company_spend(spend: Dict[str, Any], top: int) -> List[str]:
    lines = ["Paperclip company spend", "-----------------------"]
    totals = spend.get("company_totals") if isinstance(spend.get("company_totals"), list) else []
    if not totals:
        return lines + ["none", ""]
    lines.append(_fmt_row("company", "sessions", "tokens", "cost", "proj30d"))
    for row in totals[:top]:
        lines.append(
            _fmt_row(
                str(row.get("company", "unknown"))[:34],
                str(row.get("sessions", 0)),
                f"{int(row.get('total_tokens', 0)):,}",
                f"${float(row.get('estimated_cost_usd', 0.0)):,.2f}",
                f"${float(row.get('projected_cost_usd', 0.0)):,.2f}",
            )
        )
    daily = spend.get("daily") if isinstance(spend.get("daily"), list) else []
    if daily:
        lines.append("")
        lines.append("Latest Paperclip company days")
        lines.append(_fmt_row("day/company", "sessions", "tokens", "cost", "staff"))
        latest = sorted(daily, key=lambda row: str(row.get("period", "")), reverse=True)[:top]
        for row in latest:
            staff = row.get("top_staff") if isinstance(row.get("top_staff"), dict) else {}
            top_staff = next(iter(staff.keys()), "unknown")
            lines.append(
                _fmt_row(
                    f"{row.get('period', 'unknown')} {row.get('company', 'unknown')}"[:34],
                    str(row.get("sessions", 0)),
                    f"{int(row.get('total_tokens', 0)):,}",
                    f"${float(row.get('estimated_cost_usd', 0.0)):,.2f}",
                    str(top_staff)[:12],
                )
            )
    lines.append("")
    return lines


def _render_sessions(records: List[SessionRecord], top: int, include_snippets: bool) -> List[str]:
    lines = ["Top sessions", "------------"]
    sorted_records = sorted(records, key=lambda r: r.usage.get("total_tokens", 0), reverse=True)
    lines.append(_fmt_row("project", "client", "tokens", "outcome", "task"))
    for record in sorted_records[:top]:
        task = record.task.label
        if include_snippets and record.first_request_snippet:
            task = f"{task} {record.first_request_snippet}"
        lines.append(
            _fmt_row(
                record.project.label[:18],
                record.client.label[:18],
                f"{record.usage.get('total_tokens', 0):,}",
                record.outcome.label[:12],
                task[:34],
            )
        )
    lines.append("")
    return lines


def _render_findings(findings: List[Finding], top: int) -> List[str]:
    lines = ["Review candidates", "-----------------"]
    if not findings:
        return lines + ["none", ""]
    for finding in findings[:top]:
        cost = f"${finding.cost_usd:,.2f}" if finding.cost_usd is not None else "unknown"
        lines.append(f"- {finding.kind}: {finding.title} | {finding.total_tokens:,} tokens | {cost} | {finding.confidence}")
    lines.append("")
    return lines


def _render_reconciliation(rows: List[Dict[str, Any]], top: int) -> List[str]:
    lines = ["CodexBar local-vs-cache ratio", "----------------------------"]
    if not rows:
        return lines + ["none", ""]
    lines.append(_fmt_row("date", "model", "local", "codexbar", "ratio"))
    for row in rows[:top]:
        ratio = row.get("scope_ratio_percent", row.get("coverage_percent"))
        coverage_text = "unknown" if ratio is None else f"{float(ratio):.1f}%"
        lines.append(
            _fmt_row(
                str(row.get("date", "unknown")),
                str(row.get("model", "unknown"))[:18],
                f"{int(row.get('local_tokens', 0)):,}",
                f"{int(row.get('codexbar_tokens', 0)):,}",
                coverage_text,
            )
        )
    lines.append("")
    return lines


def _fmt_row(a: str, b: str, c: str, d: str, e: str) -> str:
    return f"{a:<36} {b:>8} {c:>14} {d:>9} {e:>12}"
