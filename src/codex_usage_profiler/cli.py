from __future__ import annotations

import argparse
import datetime as dt
import sys
from pathlib import Path
from typing import Optional

from .analysis import (
    build_aggregates,
    build_paperclip_spend,
    build_plan_analysis,
    classify_outcomes,
    find_waste_candidates,
    reconcile_codexbar,
)
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
    parser.add_argument("--monthly-plan-price-usd", type=float, help="Compare projected replacement cost to this monthly plan price")
    parser.add_argument("--plan-price", action="append", default=[], metavar="NAME=USD", help="Add a named monthly plan price comparison")
    parser.add_argument("--projection-days", type=int, help="Projection horizon for plan/company spend, default 30")
    parser.add_argument("--report", default="all", choices=["all", "sessions", "summary"], help="Reserved report selector")
    args = parser.parse_args(argv)

    since = args.since
    if args.days is not None:
        since_date = dt.date.today() - dt.timedelta(days=max(args.days - 1, 0))
        since = since_date.isoformat()

    config = load_config(args.config)
    if args.monthly_plan_price_usd is not None:
        config.monthly_plan_price_usd = args.monthly_plan_price_usd
    if args.projection_days is not None:
        config.projection_days = max(1, args.projection_days)
    for item in args.plan_price:
        name, sep, price = item.partition("=")
        if not sep:
            parser.error("--plan-price must be NAME=USD")
        try:
            config.plan_prices_usd[name] = float(price)
        except ValueError:
            parser.error("--plan-price price must be numeric")
    telemetry = collect_codexbar(enabled=(not args.no_codexbar and config.codexbar_enabled), timeout=args.codexbar_timeout)
    paperclip_index = build_paperclip_index(config, args.paths)
    records, warnings = parse_logs(args.paths, since=since)
    attribute_sessions(records, config)
    apply_paperclip_attribution(records, paperclip_index)
    warnings.extend(paperclip_index.warnings)
    apply_estimates(records, config, telemetry)
    classify_outcomes(records)
    aggregates = build_aggregates(records)
    paperclip_spend = build_paperclip_spend(records, config)
    plan_analysis = build_plan_analysis(records, config)
    findings = find_waste_candidates(records)
    reconciliation = reconcile_codexbar(records, telemetry.cost_usage)

    if args.format == "json":
        output = render_json(records, aggregates, findings, telemetry, reconciliation, warnings, paperclip_spend, plan_analysis, args.include_snippets)
    else:
        output = render_text(records, aggregates, findings, telemetry, reconciliation, warnings, paperclip_spend, plan_analysis, args.top, args.include_snippets)

    if args.output:
        path = Path(args.output).expanduser()
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(output, encoding="utf-8")
    else:
        sys.stdout.write(output)
    return 0
