from __future__ import annotations

import argparse
import datetime as dt
import sys
from pathlib import Path
from typing import Optional

from .analysis import build_aggregates, classify_outcomes, find_waste_candidates, reconcile_codexbar
from .attribution import attribute_sessions
from .codexbar import collect_codexbar
from .config import load_config
from .ingest import parse_logs
from .paperclip import apply_paperclip_attribution, build_paperclip_index
from .quota import apply_estimates
from .reporting import render_json, render_text


def main(argv: Optional[list[str]] = None) -> int:
    parser = argparse.ArgumentParser(
        prog="codex-usage-profiler",
        description="Profile local Codex usage by client, project, task, session, quota, cost, and outcome.",
    )
    parser.add_argument("--paths", nargs="*", help="Specific JSONL files or directories to scan")
    parser.add_argument("--since", help="Only include sessions whose start date is on/after YYYY-MM-DD")
    parser.add_argument("--days", type=int, help="Scan sessions from the last N local days")
    parser.add_argument("--config", help="Optional JSON config path")
    parser.add_argument("--format", choices=["text", "json"], default="text")
    parser.add_argument("--output", help="Write report to file instead of stdout")
    parser.add_argument("--top", type=int, default=10, help="Rows per text section")
    parser.add_argument("--no-codexbar", action="store_true", help="Disable CodexBar CLI/cache import")
    parser.add_argument("--codexbar-timeout", type=int, default=30)
    parser.add_argument("--include-snippets", action="store_true", help="Include bounded redacted first-request snippets")
    parser.add_argument("--report", default="all", choices=["all", "sessions", "summary"], help="Reserved report selector")
    args = parser.parse_args(argv)

    since = args.since
    if args.days is not None:
        since_date = dt.date.today() - dt.timedelta(days=max(args.days - 1, 0))
        since = since_date.isoformat()

    config = load_config(args.config)
    telemetry = collect_codexbar(enabled=(not args.no_codexbar and config.codexbar_enabled), timeout=args.codexbar_timeout)
    paperclip_index = build_paperclip_index(config)
    records, warnings = parse_logs(args.paths, since=since)
    attribute_sessions(records, config)
    apply_paperclip_attribution(records, paperclip_index)
    warnings.extend(paperclip_index.warnings)
    apply_estimates(records, config, telemetry)
    classify_outcomes(records)
    aggregates = build_aggregates(records)
    findings = find_waste_candidates(records)
    reconciliation = reconcile_codexbar(records, telemetry.cost_usage)

    if args.format == "json":
        output = render_json(records, aggregates, findings, telemetry, reconciliation, warnings, args.include_snippets)
    else:
        output = render_text(records, aggregates, findings, telemetry, reconciliation, warnings, args.top, args.include_snippets)

    if args.output:
        path = Path(args.output).expanduser()
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(output, encoding="utf-8")
    else:
        sys.stdout.write(output)
    return 0
