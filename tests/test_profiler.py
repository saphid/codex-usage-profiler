from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from codex_usage_profiler.analysis import (
    build_aggregates,
    build_paperclip_spend,
    build_plan_analysis,
    classify_outcomes,
    find_waste_candidates,
    reconcile_codexbar,
)
from codex_usage_profiler.attribution import attribute_sessions
from codex_usage_profiler.codexbar import (
    collect_codexbar,
    _normalize_cost_output,
    _normalize_usage_output,
    _read_cost_cache,
    _read_history,
    _read_pricing_cache,
)
from codex_usage_profiler.config import Config
from codex_usage_profiler.ingest import parse_logs
from codex_usage_profiler.models import SessionRecord
from codex_usage_profiler.paperclip import apply_paperclip_attribution, build_paperclip_index
from codex_usage_profiler.quota import apply_estimates, build_rate_map
from codex_usage_profiler.reporting import render_json


FIXTURES = Path(__file__).parent / "fixtures"


class ProfilerTests(unittest.TestCase):
    def test_ingest_metadata_and_usage(self) -> None:
        records, warnings = parse_logs([str(FIXTURES / "complete.jsonl")])
        self.assertEqual(warnings, [])
        self.assertEqual(len(records), 1)
        record = records[0]
        self.assertEqual(record.session_id, "sess-complete")
        self.assertEqual(record.cwd, "/Users/saphid/Documents/PA-Agent")
        self.assertEqual(record.model, "gpt-5.5")
        self.assertEqual(record.usage["total_tokens"], 2100)
        self.assertEqual(record.file_edit_markers, 1)
        self.assertEqual(record.test_markers, 1)
        self.assertIn("test", record.command_labels)
        self.assertIsNotNone(record.first_request_hash)
        self.assertIn("TOKEN=<redacted>", record.first_request_snippet or "")

    def test_missing_usage_and_object_metadata(self) -> None:
        records, _ = parse_logs([str(FIXTURES / "missing_usage.jsonl"), str(FIXTURES / "object_meta.jsonl")])
        self.assertEqual(len(records), 2)
        missing = [r for r in records if r.session_id == "sess-missing"][0]
        obj = [r for r in records if r.session_id == "sess-object"][0]
        self.assertFalse(missing.usage_known)
        self.assertTrue(obj.source and obj.source.startswith("{"))

    def test_attribution(self) -> None:
        records, _ = parse_logs([str(FIXTURES / "complete.jsonl"), str(FIXTURES / "object_meta.jsonl")])
        attribute_sessions(records, Config())
        by_id = {r.session_id: r for r in records}
        self.assertEqual(by_id["sess-complete"].client.label, "Codex Desktop")
        self.assertEqual(by_id["sess-complete"].project.label, "PA-Agent")
        self.assertEqual(by_id["sess-object"].project.label, "dream_job")
        self.assertTrue(by_id["sess-object"].task.label.startswith("subagent:"))

    def test_codexbar_parsers(self) -> None:
        usage = _normalize_usage_output(json.loads((FIXTURES / "codexbar_usage.json").read_text()))
        cost = _normalize_cost_output(json.loads((FIXTURES / "codexbar_cost.json").read_text()))
        cache = _read_cost_cache([str(FIXTURES / "codex-v8.json")])
        pricing = _read_pricing_cache([str(FIXTURES / "models-dev-v1.json")])
        history = _read_history(str(FIXTURES / "history_codex.json"))
        self.assertEqual(usage["windows"][0]["usedPercent"], 13)
        self.assertEqual(cost["daily"][0]["totalTokens"], 2100)
        self.assertEqual(cache["days"][0]["models"][0]["cachedInputTokens"], 500)
        self.assertIn("gpt-5.5", pricing["models"])
        self.assertEqual(history["windows"][0]["latest"]["usedPercent"], 15)
        self.assertNotIn("secret", history["preferredAccountHash"])

    def test_codexbar_collected_root(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "collected-sessions" / "macbook-pro" / "codexbar" / "abc"
            root.mkdir(parents=True)
            shutil.copy2(FIXTURES / "codex-v8.json", root / "codex-v8.json")
            shutil.copy2(FIXTURES / "models-dev-v1.json", root / "models-dev-v1.json")
            shutil.copy2(FIXTURES / "history_codex.json", root / "codex.json")
            env = dict(os.environ)
            os.environ["CODEXBAR_COLLECTED_ROOT"] = str(Path(tmp) / "collected-sessions")
            try:
                telemetry = collect_codexbar(enabled=True, timeout=1)
            finally:
                os.environ.clear()
                os.environ.update(env)
            self.assertTrue(telemetry.available)
            self.assertIsNotNone(telemetry.cost_cache)
            self.assertIsNotNone(telemetry.pricing_cache)
            self.assertIsNotNone(telemetry.history)

    def test_estimates_and_reports(self) -> None:
        records, _ = parse_logs([str(FIXTURES / "complete.jsonl"), str(FIXTURES / "object_meta.jsonl")])
        attribute_sessions(records, Config())
        class Telemetry:
            pricing_cache = _read_pricing_cache([str(FIXTURES / "models-dev-v1.json")])
        apply_estimates(records, Config(), Telemetry())
        classify_outcomes(records)
        aggregates = build_aggregates(records)
        paperclip_spend = build_paperclip_spend(records, Config())
        plan_analysis = build_plan_analysis(records, Config(monthly_plan_price_usd=20.0))
        findings = find_waste_candidates(records)
        cost = _normalize_cost_output(json.loads((FIXTURES / "codexbar_cost.json").read_text()))
        reconciliation = reconcile_codexbar(records, cost)
        self.assertGreater(aggregates["project"][0]["total_tokens"], 0)
        self.assertIn("projected_cost_usd", plan_analysis)
        self.assertEqual(paperclip_spend["company_totals"], [])
        self.assertTrue(any(r.estimate.confidence == "rate_card_estimate" for r in records))
        payload = json.loads(render_json(records, aggregates, findings, TelemetryLike(), reconciliation, [], paperclip_spend, plan_analysis, False))
        self.assertIn("sessions", payload)
        self.assertIn("plan_analysis", payload)
        self.assertNotIn("first_request_snippet", payload["sessions"][0])

    def test_paperclip_staff_company_project_attribution(self) -> None:
        root = FIXTURES / "paperclip" / "instances" / "default"
        session = root / "companies" / "67a988b1-d14e-4f38-8d77-ca55848888b0" / "agents" / "08668359-96b5-4049-896f-f11e9925f771" / "codex-home" / "sessions" / "2026" / "06" / "30" / "paperclip-agent.jsonl"
        config = Config(paperclip_root=str(root))
        records, warnings = parse_logs([str(session)])
        self.assertEqual(warnings, [])
        attribute_sessions(records, config)
        apply_paperclip_attribution(records, build_paperclip_index(config))
        class Telemetry:
            pricing_cache = None
        apply_estimates(records, config, Telemetry())
        classify_outcomes(records)
        record = records[0]
        self.assertEqual(record.paperclip_company.label, "STA")
        self.assertEqual(record.paperclip_staff.label, "Security Engineer")
        self.assertEqual(record.paperclip_project.label, "Start2Scale")
        self.assertEqual(record.paperclip_task.label, "STA-42")
        self.assertEqual(record.project.label, "Start2Scale")
        spend = build_paperclip_spend(records, Config(paperclip_root=str(root), projection_days=30))
        self.assertEqual(spend["company_totals"][0]["company"], "STA")
        self.assertEqual(spend["daily"][0]["period"], "2026-06-30")
        self.assertGreater(spend["company_totals"][0]["projected_cost_usd"], 0)

    def test_collected_paperclip_sidecar_preserves_company_and_staff(self) -> None:
        root = FIXTURES / "paperclip" / "instances" / "default"
        source = root / "companies" / "67a988b1-d14e-4f38-8d77-ca55848888b0" / "agents" / "08668359-96b5-4049-896f-f11e9925f771" / "codex-home" / "sessions" / "2026" / "06" / "30" / "paperclip-agent.jsonl"
        with tempfile.TemporaryDirectory() as tmp:
            collected = Path(tmp) / "collected-sessions" / "macbook-pro" / "codex" / "abc" / "paperclip-agent.jsonl"
            collected.parent.mkdir(parents=True)
            shutil.copy2(source, collected)
            collected.with_suffix(".jsonl.meta.json").write_text(
                json.dumps({"collector": "macbook-pro", "tool": "codex", "source_path": str(source)}),
                encoding="utf-8",
            )
            config = Config(paperclip_root=str(root))
            records, warnings = parse_logs([str(collected)])
            self.assertEqual(warnings, [])
            attribute_sessions(records, config)
            apply_paperclip_attribution(records, build_paperclip_index(config))
        record = records[0]
        self.assertEqual(record.source_path, str(source))
        self.assertEqual(record.paperclip_company.label, "STA")
        self.assertEqual(record.paperclip_staff.label, "Security Engineer")
        self.assertEqual(record.project.label, "Start2Scale")

    def test_paperclip_prompt_preamble_attribution(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            session = Path(tmp) / "session.jsonl"
            text = "\n".join(
                [
                    "Paperclip Company ID: 67a988b1-d14e-4f38-8d77-ca55848888b0",
                    "Paperclip Company: Start2Scale",
                    "Paperclip Agent ID: 08668359-96b5-4049-896f-f11e9925f771",
                    "Paperclip Staff: Security Engineer",
                    "Paperclip Project ID: 64b67709-14d6-4158-bb48-fec54144e061",
                    "Paperclip Project: Start2Scale",
                    "Paperclip Issue: STA-42",
                    "Paperclip Task: Security review",
                ]
            )
            session.write_text(
                json.dumps({"timestamp": "2026-06-30T10:00:00Z", "type": "message", "payload": {"message": {"role": "user", "content": text}}, "usage": {"input_tokens": 1, "output_tokens": 2}}) + "\n",
                encoding="utf-8",
            )
            records, _ = parse_logs([str(session)])
            attribute_sessions(records, Config())
            apply_paperclip_attribution(records, build_paperclip_index(Config(paperclip_root="/missing")))
        self.assertEqual(records[0].paperclip_company.label, "Start2Scale")
        self.assertEqual(records[0].paperclip_staff.label, "Security Engineer")
        self.assertEqual(records[0].paperclip_project.label, "Start2Scale")
        self.assertEqual(records[0].paperclip_task.label, "STA-42")

    def test_paperclip_task_labels_require_paperclip_context(self) -> None:
        record = SessionRecord(
            session_id="generic-http-debug",
            path="/tmp/HTTP-404/session.jsonl",
            cwd="/tmp/HTTP-404",
        )
        apply_paperclip_attribution([record], build_paperclip_index(Config(paperclip_root="/missing")))
        self.assertEqual(record.paperclip_task.label, "unknown")
        self.assertEqual(record.task.label, "unknown")

    def test_paperclip_task_labels_skip_infrastructure_prefixes(self) -> None:
        record = SessionRecord(
            session_id="paperclip-http-debug",
            path="/tmp/HTTP-404/session.jsonl",
            cwd="/tmp/HTTP-404",
            first_request_features={"company": "Agent Tooling"},
        )
        apply_paperclip_attribution([record], build_paperclip_index(Config(paperclip_root="/missing")))
        self.assertEqual(record.paperclip_company.label, "Agent Tooling")
        self.assertEqual(record.paperclip_task.label, "unknown")

    def test_paperclip_task_labels_keep_issue_prefixes(self) -> None:
        record = SessionRecord(
            session_id="paperclip-issue",
            path="/work/codex-usage-profiler/AGE-60/session.jsonl",
            cwd="/work/codex-usage-profiler/AGE-60",
            first_request_features={"company": "Agent Tooling"},
        )
        apply_paperclip_attribution([record], build_paperclip_index(Config(paperclip_root="/missing")))
        self.assertEqual(record.paperclip_task.label, "AGE-60")
        self.assertEqual(record.task.label, "AGE-60")

    def test_paperclip_company_prefix_aliases(self) -> None:
        root = FIXTURES / "paperclip" / "instances" / "default"
        with tempfile.TemporaryDirectory() as tmp:
            tmp_root = Path(tmp) / "instance"
            project = tmp_root / "projects" / "d8126350-acdb-495b-ab18-469660d616d2" / "f278a9b4-0d9f-4fe9-88cb-bd20ad8bfd83" / "_default"
            project.mkdir(parents=True)
            (project / "max-17-venue-discovery-token-usage-audit.md").write_text("fixture", encoding="utf-8")
            index = build_paperclip_index(Config(paperclip_root=str(tmp_root)))
            self.assertEqual(index.companies["d8126350-acdb-495b-ab18-469660d616d2"], "Maximum Goat")
            aliased = build_paperclip_index(
                Config(
                    paperclip_root=str(root),
                    paperclip_company_aliases={"67a988b1-d14e-4f38-8d77-ca55848888b0": "Starter Scale"},
                )
            )
            self.assertEqual(aliased.companies["67a988b1-d14e-4f38-8d77-ca55848888b0"], "Starter Scale")

    def test_cli_e2e_paperclip_json_report(self) -> None:
        root = FIXTURES / "paperclip" / "instances" / "default"
        session_root = root / "companies" / "67a988b1-d14e-4f38-8d77-ca55848888b0" / "agents" / "08668359-96b5-4049-896f-f11e9925f771" / "codex-home" / "sessions"
        with tempfile.NamedTemporaryFile("w", encoding="utf-8", suffix=".json", delete=False) as fh:
            json.dump({"paperclip_root": str(root), "codexbar_enabled": False}, fh)
            config_path = fh.name
        try:
            env = dict(os.environ)
            env["PYTHONPATH"] = str(Path(__file__).parents[1] / "src")
            proc = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "codex_usage_profiler",
                    "--paths",
                    str(session_root),
                    "--config",
                    config_path,
                    "--no-codexbar",
                    "--format",
                    "json",
                ],
                text=True,
                capture_output=True,
                check=False,
                env=env,
            )
        finally:
            Path(config_path).unlink(missing_ok=True)
        self.assertEqual(proc.returncode, 0, proc.stderr)
        payload = json.loads(proc.stdout)
        self.assertEqual(payload["run"]["session_count"], 1)
        self.assertEqual(payload["aggregates"]["paperclip_staff"][0]["label"], "Security Engineer")
        self.assertEqual(payload["aggregates"]["paperclip_company"][0]["label"], "STA")
        self.assertNotIn("first_request_snippet", payload["sessions"][0])


class TelemetryLike:
    warnings = []
    live_usage = None
    cost_usage = None
    cost_cache = None
    pi_cache = None
    pricing_cache = None
    history = None
    available = False
    cli_path = None
    app_version = None
    config_path = None
    cost_cache_paths = []
    pricing_cache_paths = []
    history_path = None

    def to_dict(self):
        return {"available": False}


if __name__ == "__main__":
    unittest.main()
