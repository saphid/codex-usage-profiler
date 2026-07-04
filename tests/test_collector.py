from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from codex_usage_profiler.collector import discover_candidates, load_collector_config, run_collection, stage_file, stage_paperclip_metadata
from codex_usage_profiler.ingest import parse_logs
from codex_usage_profiler.attribution import attribute_sessions
from codex_usage_profiler.config import Config


class CollectorTests(unittest.TestCase):
    def test_config_defaults_and_custom_globs(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            config_path = Path(tmp) / "collector.json"
            config_path.write_text(
                json.dumps(
                    {
                        "collector_name": "fixture-host",
                        "include_defaults": False,
                        "tools": {"kimi": str(Path(tmp) / "kimi" / "*.jsonl")},
                    }
                ),
                encoding="utf-8",
            )
            config = load_collector_config(str(config_path))
            self.assertEqual(config["collector_name"], "fixture-host")
            self.assertEqual(list(config["tools"].keys()), ["kimi"])

    def test_incremental_stage_push_and_metadata(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source_dir = root / "source" / ".claude" / "projects"
            source_dir.mkdir(parents=True)
            session = source_dir / "session.jsonl"
            session.write_text(
                "\n".join(
                    [
                        json.dumps({"timestamp": "2026-07-03T01:00:00Z", "cwd": "/work/demo", "model": "claude-test"}),
                        json.dumps({"timestamp": "2026-07-03T01:01:00Z", "usage": {"input_tokens": 10, "output_tokens": 5}}),
                    ]
                )
                + "\n",
                encoding="utf-8",
            )
            config = {
                "collector_name": "fixture-host",
                "destination": str(root / "central"),
                "include_defaults": False,
                "tools": {"claude": [str(source_dir / "*.jsonl")]},
                "exclude": [],
                "state_path": str(root / "state.json"),
                "staging_dir": str(root / "staging"),
                "log_path": str(root / "collector.log"),
                "syslog_host": "",
                "loki_url": "",
                "max_file_bytes": 1_000_000,
            }
            first = run_collection(config)
            self.assertEqual(first["matched_files"], 1)
            self.assertEqual(first["staged_files"], 1)
            self.assertEqual(first["pushed_files"], 1)
            copied = list((root / "central" / "fixture-host" / "claude").glob("*/*.jsonl"))
            self.assertEqual(len(copied), 1)
            meta = json.loads(copied[0].with_suffix(".jsonl.meta.json").read_text(encoding="utf-8"))
            self.assertEqual(meta["tool"], "claude")
            self.assertEqual(meta["collector"], "fixture-host")
            second = run_collection(config)
            self.assertEqual(second["matched_files"], 1)
            self.assertEqual(second["staged_files"], 0)
            self.assertEqual(second["skipped_files"], 1)

    def test_collected_path_attributes_client(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "collected-sessions" / "fixture-host" / "claude" / "abc" / "session.jsonl"
            path.parent.mkdir(parents=True)
            path.write_text(
                json.dumps({"timestamp": "2026-07-03T01:00:00Z", "usage": {"input_tokens": 1, "output_tokens": 2}}) + "\n",
                encoding="utf-8",
            )
            records, warnings = parse_logs([str(path)])
            self.assertEqual(warnings, [])
            attribute_sessions(records, Config())
            self.assertEqual(records[0].client.label, "Claude Code")
            self.assertEqual(records[0].project.label, "fixture-host:claude")
            self.assertEqual(records[0].usage["total_tokens"], 3)

    def test_discover_skips_excludes_and_oversized_candidates_are_counted(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            good = root / "good.jsonl"
            auth = root / "auth.json"
            good.write_text("{}\n", encoding="utf-8")
            auth.write_text("{}\n", encoding="utf-8")
            codexbar = root / "Library" / "Caches" / "CodexBar" / "cost-usage" / "codex-v8.json"
            codexbar.parent.mkdir(parents=True)
            codexbar.write_text("{}\n", encoding="utf-8")
            config = {
                "include_defaults": False,
                "tools": {"codex": [str(root / "*.json*")], "codexbar": [str(codexbar)]},
                "exclude": ["**/auth.json"],
            }
            self.assertEqual(discover_candidates(config), [("codex", good.resolve()), ("codexbar", codexbar.resolve())])

    def test_missing_source_during_stage_is_not_fatal(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source = root / "source.jsonl"
            source.write_text("{}\n", encoding="utf-8")
            config = {
                "collector_name": "fixture-host",
                "destination": str(root / "central"),
                "include_defaults": False,
                "tools": {"codex": [str(source)]},
                "exclude": [],
                "state_path": str(root / "state.json"),
                "staging_dir": str(root / "staging"),
                "log_path": str(root / "collector.log"),
                "syslog_host": "",
                "loki_url": "",
            }
            with mock.patch("codex_usage_profiler.collector.stage_file", side_effect=FileNotFoundError):
                result = run_collection(config)
            self.assertEqual(result["errors"], [])
            self.assertEqual(result["vanished_files"], 1)

    def test_stage_file_adds_structured_paperclip_sidecar_context(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source = root / ".paperclip" / "instances" / "default" / "companies" / "67a988b1-d14e-4f38-8d77-ca55848888b0" / "agents" / "08668359-96b5-4049-896f-f11e9925f771" / "codex-home" / "sessions" / "session.jsonl"
            source.parent.mkdir(parents=True)
            source.write_text("{}\n", encoding="utf-8")
            copied = stage_file(root / "staging", "fixture-host", "codex", source, source.stat())
            meta = json.loads(copied.with_suffix(".jsonl.meta.json").read_text(encoding="utf-8"))
            self.assertEqual(meta["paperclip"]["company_id"], "67a988b1-d14e-4f38-8d77-ca55848888b0")
            self.assertEqual(meta["paperclip"]["agent_id"], "08668359-96b5-4049-896f-f11e9925f771")

    def test_stage_paperclip_metadata_snapshot(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            instance = root / ".paperclip" / "instances" / "default"
            workspace = instance / "workspaces" / "8ec73631-7c0f-4049-8a96-c205536c3cce"
            workspace.mkdir(parents=True)
            (workspace / "sre-sta-42-heartbeat.md").write_text("ok", encoding="utf-8")
            companies = [{"id": "67a988b1-d14e-4f38-8d77-ca55848888b0", "name": "Start2Scale", "issuePrefix": "STA", "status": "active"}]
            agents = [{"id": "08668359-96b5-4049-896f-f11e9925f771", "companyId": companies[0]["id"], "name": "Security Engineer", "title": "Security Engineer"}]
            projects = [{"id": "64b67709-14d6-4158-bb48-fec54144e061", "companyId": companies[0]["id"], "name": "Start2Scale"}]

            def fake_fetch(url, timeout, warnings, label):
                if label == "companies":
                    return companies
                if label.startswith("agents:"):
                    return agents
                if label.startswith("projects:"):
                    return projects
                return []

            with mock.patch("codex_usage_profiler.collector._fetch_json_list", side_effect=fake_fetch):
                result = stage_paperclip_metadata(root / "staging", "fixture-host", {"paperclip_root": str(instance)})
            self.assertIsNotNone(result)
            snapshots = list((root / "staging").glob("fixture-host/paperclip_metadata/*/paperclip-metadata.json"))
            self.assertEqual(len(snapshots), 1)
            payload = json.loads(snapshots[0].read_text(encoding="utf-8"))
            self.assertEqual(payload["companies"][0]["name"], "Start2Scale")
            self.assertEqual(payload["agents"][0]["title"], "Security Engineer")
            self.assertEqual(payload["workspaces"][0]["staffLabel"], "SRE")
            self.assertEqual(payload["workspaces"][0]["companyId"], companies[0]["id"])


if __name__ == "__main__":
    unittest.main()
