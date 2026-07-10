from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import threading
import unittest
import urllib.request
from pathlib import Path

from codex_usage_profiler.dashboard import make_server


ROOT = Path(__file__).parents[1]
APP_JS = ROOT / "src" / "codex_usage_profiler" / "dashboard_static" / "app.js"


def sample_report() -> dict:
    def attribution(label: str, confidence: str = "high") -> dict:
        return {"label": label, "confidence": confidence, "evidence": [f"fixture:{label}"]}

    def session(
        session_id: str,
        start: str,
        client: str,
        project: str,
        company: str,
        staff: str,
        task: str,
        model: str,
        total_tokens: int,
        cost_usd: float,
        outcome: str,
        edits: int = 0,
        tests: int = 0,
        command_labels: list[str] | None = None,
    ) -> dict:
        return {
            "session_id": session_id,
            "path": f"/tmp/{session_id}.jsonl",
            "start_time": start,
            "end_time": start,
            "cwd": f"/work/{project}",
            "workspace_roots": [],
            "model": model,
            "source": "fixture",
            "originator": client,
            "thread_source": "local",
            "cli_version": "0.1",
            "model_provider": "openai",
            "usage": {
                "input_tokens": total_tokens,
                "cached_input_tokens": 0,
                "output_tokens": 0,
                "reasoning_output_tokens": 0,
                "total_tokens": total_tokens,
            },
            "usage_known": True,
            "event_counts": {},
            "tool_counts": {},
            "tool_sequence": [],
            "command_signatures": [],
            "command_labels": command_labels or [],
            "first_request_hash": session_id,
            "first_request_features": {},
            "file_edit_markers": edits,
            "test_markers": tests,
            "error_markers": 0,
            "warnings": [],
            "client": attribution(client),
            "project": attribution(project),
            "task": attribution(task, "medium"),
            "paperclip_company": attribution(company),
            "paperclip_project": attribution(project),
            "paperclip_staff": attribution(staff),
            "paperclip_task": attribution(task),
            "estimate": {"credits": cost_usd, "cost_usd": cost_usd, "confidence": "rate_card_estimate", "evidence": []},
            "outcome": attribution(outcome, "medium"),
        }

    sessions = [
        session("s-useful", "2026-06-30T10:00:00Z", "Codex Desktop", "Paperclip", "Acme", "Alice", "STA-1", "gpt-5", 100000, 2.0, "useful", edits=1, tests=1),
        session("s-waste", "2026-06-30T11:00:00Z", "Cursor", "Paperclip", "Acme", "Bob", "STA-2", "gpt-5", 200000, 4.0, "exploratory", command_labels=["read", "read", "shell"]),
        session("s-neutral", "2026-06-30T00:00:00Z", "Codex CLI", "PA-Agent", "unknown", "unknown", "local-admin", "gpt-5-mini", 50000, 0.5, "neutral", command_labels=["read"]),
    ]
    return {
        "run": {"session_count": len(sessions), "warning_count": 0, "confidence_note": "fixture"},
        "telemetry": {"available": True, "live_usage": {"windows": [{"usedPercent": 40}]}, "warnings": []},
        "aggregates": {},
        "paperclip_spend": {"projection_days": 30},
        "plan_analysis": {"projection_days": 30, "monthly_plan_price_usd": 20.0},
        "findings": [
            {
                "kind": "retry_loop",
                "title": "Repeated failed workflow",
                "confidence": "medium",
                "session_ids": ["s-waste"],
                "total_tokens": 200000,
                "cost_usd": 4.0,
                "quota_share_percent": None,
                "evidence": ["fixture"],
            }
        ],
        "reconciliation": [],
        "sessions": sessions,
        "warnings": [],
    }


class DashboardTests(unittest.TestCase):
    def test_dashboard_server_serves_static_assets_and_report(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            report_path = Path(tmp) / "report.json"
            report_path.write_text(json.dumps(sample_report()), encoding="utf-8")
            server = make_server(report_path, "127.0.0.1", 0)
            thread = threading.Thread(target=server.serve_forever, daemon=True)
            thread.start()
            base = f"http://127.0.0.1:{server.server_address[1]}"
            try:
                html = urllib.request.urlopen(base + "/", timeout=5).read().decode("utf-8")
                js = urllib.request.urlopen(base + "/app.js", timeout=5).read().decode("utf-8")
                css = urllib.request.urlopen(base + "/styles.css", timeout=5).read().decode("utf-8")
                api = json.loads(urllib.request.urlopen(base + "/api/report", timeout=5).read().decode("utf-8"))
                health = urllib.request.urlopen(base + "/healthz", timeout=5).read().decode("utf-8")
            finally:
                server.shutdown()
                server.server_close()
            self.assertIn('data-testid="session-table"', html)
            self.assertIn("CUPDashboard", js)
            self.assertIn("color-scheme: dark", css)
            self.assertEqual(api["run"]["session_count"], 3)
            self.assertEqual(health, "ok\n")

    def test_dashboard_server_accepts_syslog_options(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            report_path = Path(tmp) / "report.json"
            report_path.write_text(json.dumps(sample_report()), encoding="utf-8")
            server = make_server(
                report_path,
                "127.0.0.1",
                0,
                syslog_host=None,
                syslog_port=514,
                loki_url="http://loki.example/api/v1/push",
            )
            try:
                self.assertEqual(server.RequestHandlerClass.syslog_port, 514)
                self.assertEqual(server.RequestHandlerClass.loki_url, "http://loki.example/api/v1/push")
            finally:
                server.server_close()

    def test_dashboard_data_functions_filter_sort_export_and_permalink(self) -> None:
        script = f"""
const assert = require('assert');
const dashboard = require({json.dumps(str(APP_JS))});
const report = JSON.parse(process.env.CUP_REPORT);
const options = dashboard.buildOptions(report);
assert(options.staff.includes('Alice'));
assert(options.clients.includes('Cursor'));

const stressReport = Object.assign({{}}, report, {{ sessions: [] }});
for (let i = 0; i < 503; i++) {{
  const copy = JSON.parse(JSON.stringify(report.sessions[0]));
  copy.session_id = 'task-' + i;
  copy.paperclip_task = {{ label: 'TASK-' + i, confidence: 'high', evidence: ['fixture'] }};
  copy.task = {{ label: 'TASK-' + i, confidence: 'high', evidence: ['fixture'] }};
  copy.usage.total_tokens = i + 1;
  stressReport.sessions.push(copy);
}}
const taskOptions = dashboard.buildOptions(stressReport).tasks;
assert.strictEqual(taskOptions.length, 500);
assert.strictEqual(taskOptions[0], 'TASK-502');
assert(!taskOptions.includes('TASK-0'));

let state = dashboard.createState();
state.filters.staff = ['Alice'];
state.filters.preset = 'overnight';
state.filters.hourStart = '18';
state.filters.hourEnd = '6';
let filtered = dashboard.applyFilters(report.sessions, state.filters, report);
assert.strictEqual(filtered.length, 1);
assert.strictEqual(filtered[0].session_id, 's-useful');
let summary = dashboard.summarize(filtered, report);
assert.strictEqual(summary.tokens, 100000);
assert.strictEqual(summary.quotaPercent, 40);

state = dashboard.createState();
state.filters.waste = 'retry';
filtered = dashboard.applyFilters(report.sessions, state.filters, report);
assert.strictEqual(filtered.length, 1);
assert.strictEqual(filtered[0].session_id, 's-waste');
assert.strictEqual(dashboard.wasteDrivers(filtered, report)[0].kind, 'retry_loop');

const sorted = dashboard.sortSessions(report.sessions, {{ key: 'tokens', dir: 'desc' }}, report);
assert.strictEqual(sorted[0].session_id, 's-waste');
const csv = dashboard.toCsv(filtered, report);
assert(csv.includes('staff'));
assert(csv.includes('retry_loop'));
const query = dashboard.encodeFilters(state);
assert(query.includes('waste=retry'));
const decoded = dashboard.decodeFilters('?' + query);
assert.strictEqual(decoded.filters.waste, 'retry');

const flow = dashboard.buildFlowModel(report.sessions, report, 'cost');
assert.deepStrictEqual(flow.columns.map((col) => col.id), ['client', 'project', 'staff', 'outcome']);
assert(flow.links.length >= 3);
assert(flow.columns[3].nodes.some((node) => node.label === 'Useful'));
assert(flow.columns[3].nodes.some((node) => node.label === 'Waste'));
assert(flow.columns[3].nodes.some((node) => node.label === 'Neutral'));
assert.strictEqual(Math.round(flow.total * 10) / 10, 6.5);
const flowLayout = dashboard.layoutFlowModel(flow, 900, 300);
const columnXs = flow.columns.map((column) => flowLayout.nodePositions[column.nodes[0].id].x);
assert(columnXs[1] - columnXs[0] > flowLayout.nodeWidth);
assert(columnXs[2] - columnXs[1] > flowLayout.nodeWidth);
assert(columnXs[3] - columnXs[2] > flowLayout.nodeWidth);
for (const item of flowLayout.linkLayouts) {{
  const source = flowLayout.nodePositions[item.source];
  const target = flowLayout.nodePositions[item.target];
  assert(Math.abs(item.sx - (source.x + source.width)) < 0.001);
  assert(Math.abs(item.tx - target.x) < 0.001);
  assert(item.sy >= source.y && item.sy <= source.y + source.height);
  assert(item.ty >= target.y && item.ty <= target.y + target.height);
}}

state = dashboard.createState();
state.filters.brushStartTime = '2026-06-30T10:30:00Z';
state.filters.brushEndTime = '2026-06-30T11:30:00Z';
filtered = dashboard.applyFilters(report.sessions, state.filters, report);
assert.deepStrictEqual(filtered.map((session) => session.session_id), ['s-waste']);

state = dashboard.createState();
state.filters.outcomeBucket = 'Waste';
filtered = dashboard.applyFilters(report.sessions, state.filters, report);
assert.deepStrictEqual(filtered.map((session) => session.session_id), ['s-waste']);

state = dashboard.createState();
state.filters.attributionCoverage = 'partial';
filtered = dashboard.applyFilters(report.sessions, state.filters, report);
assert.deepStrictEqual(filtered.map((session) => session.session_id), ['s-neutral']);

state = dashboard.createState();
state.filters.attributionCoverage = 'unknown-staff';
filtered = dashboard.applyFilters(report.sessions, state.filters, report);
assert.deepStrictEqual(filtered.map((session) => session.session_id), ['s-neutral']);

state = dashboard.createState();
state.filters.sessionIds = ['s-useful', 's-neutral'];
filtered = dashboard.applyFilters(report.sessions, state.filters, report);
assert.deepStrictEqual(filtered.map((session) => session.session_id), ['s-useful', 's-neutral']);

state = dashboard.createState();
state.filters.wasteKind = 'retry_loop';
filtered = dashboard.applyFilters(report.sessions, state.filters, report);
assert.deepStrictEqual(filtered.map((session) => session.session_id), ['s-waste']);

const costBuckets = dashboard.hourlyBuckets(report.sessions, report, 'cost');
assert.strictEqual(Math.round(costBuckets.reduce((sum, bucket) => sum + bucket.total, 0) * 10) / 10, 6.5);
const companySpend = dashboard.companySpendModel(report.sessions, report, 'cost');
assert.strictEqual(companySpend.totals[0].company, 'Acme');
assert.strictEqual(companySpend.totals[0].sessions, 2);
assert(companySpend.totals[0].projectedCost > 0);
assert(companySpend.days.some((row) => row.day === '2026-06-30'));

const coverage = dashboard.coverageStats(report.sessions);
assert(coverage.unknownStaff > 10 && coverage.unknownStaff < 20);
assert.strictEqual(coverage.unknownTask, 0);

state = dashboard.createState();
state.compareMode = true;
state.drawerOpen = false;
state.filters.sessionIds = ['s-useful', 's-waste'];
state.filters.outcomeBucket = 'Useful';
state.filters.attributionCoverage = 'full';
state.filters.wasteKind = 'retry_loop';
state.filters.weekdays = ['2'];
state.filters.brushStartTime = '2026-06-30T10:00:00Z';
state.filters.brushEndTime = '2026-06-30T12:00:00Z';
state.hiddenOutcomes = ['neutral'];
state.visibleColumns = ['start_time', 'session_id', 'tokens'];
const richQuery = dashboard.encodeFilters(state);
const richDecoded = dashboard.decodeFilters('?' + richQuery);
assert.strictEqual(richDecoded.compareMode, true);
assert.strictEqual(richDecoded.drawerOpen, false);
assert.deepStrictEqual(richDecoded.filters.sessionIds, ['s-useful', 's-waste']);
assert.strictEqual(richDecoded.filters.outcomeBucket, 'Useful');
assert.strictEqual(richDecoded.filters.attributionCoverage, 'full');
assert.strictEqual(richDecoded.filters.wasteKind, 'retry_loop');
assert.deepStrictEqual(richDecoded.filters.weekdays, ['2']);
assert.deepStrictEqual(richDecoded.hiddenOutcomes, ['neutral']);
assert.deepStrictEqual(richDecoded.visibleColumns, ['start_time', 'session_id', 'tokens']);
"""
        env = dict(os.environ)
        env["CUP_REPORT"] = json.dumps(sample_report())
        # Hour/day filters work in local time; expectations assume UTC+10.
        env["TZ"] = "Australia/Sydney"
        proc = subprocess.run(["node", "-e", script], text=True, capture_output=True, env=env, check=False)
        self.assertEqual(proc.returncode, 0, proc.stderr)


if __name__ == "__main__":
    unittest.main()
