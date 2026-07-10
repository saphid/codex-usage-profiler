from __future__ import annotations

import json
import subprocess
import sys
import unittest
from pathlib import Path

from codex_usage_profiler.learning import (
    PHASE_IMPLEMENTATION,
    PHASE_INVESTIGATION,
    PHASE_REQUEST,
    PHASE_UNDERSTANDING,
    PHASE_VALIDATION,
    build_learning_report,
    render_learning_json,
    render_learning_markdown,
)


FIXTURES = Path(__file__).parent / "fixtures"


class LearningMinerTests(unittest.TestCase):
    def test_phase_spans_and_transitions(self) -> None:
        report = build_learning_report([str(FIXTURES / "learning_linear.jsonl"), str(FIXTURES / "learning_loop.jsonl")])
        by_id = {session.session_id: session for session in report.sessions}
        phases = [span.phase for span in by_id["learn-linear"].spans]
        self.assertIn(PHASE_REQUEST, phases)
        self.assertIn(PHASE_INVESTIGATION, phases)
        self.assertIn(PHASE_UNDERSTANDING, phases)
        self.assertIn(PHASE_IMPLEMENTATION, phases)
        self.assertIn(PHASE_VALIDATION, phases)
        self.assertGreater(by_id["learn-loop"].transitions.get(f"{PHASE_VALIDATION}->{PHASE_INVESTIGATION}", 0), 0)

    def test_learning_cards_and_redaction(self) -> None:
        report = build_learning_report(
            [
                str(FIXTURES / "learning_loop.jsonl"),
                str(FIXTURES / "learning_cookie.jsonl"),
                str(FIXTURES / "learning_project_memory.jsonl"),
                str(FIXTURES / "learning_project_memory_2.jsonl"),
            ],
            include_snippets=True,
        )
        titles = {card.title for card in report.cards}
        self.assertIn("Standardize authenticated browser request replay", titles)
        self.assertTrue(any("Capture repeated setup discovery" in title for title in titles))
        text = render_learning_json(report)
        self.assertNotIn("abc123", text)
        self.assertNotIn("supersecret", text)
        self.assertIn("<redacted>", text)
        markdown = render_learning_markdown(report)
        self.assertIn("Codex Session Learning Miner", markdown)

    def test_cli_json(self) -> None:
        proc = subprocess.run(
            [
                sys.executable,
                "-m",
                "codex_usage_profiler.learning_cli",
                "--paths",
                str(FIXTURES / "learning_loop.jsonl"),
                str(FIXTURES / "learning_cookie.jsonl"),
                "--format",
                "json",
            ],
            text=True,
            capture_output=True,
            check=False,
            env={"PYTHONPATH": str(Path(__file__).parents[1] / "src")},
        )
        self.assertEqual(proc.returncode, 0, proc.stderr)
        payload = json.loads(proc.stdout)
        self.assertEqual(payload["run"]["session_count"], 2)
        self.assertGreaterEqual(payload["run"]["card_count"], 1)
        self.assertIn("path_hash", payload["sessions"][0])
        self.assertNotIn("path", payload["sessions"][0])
        self.assertNotIn("evidence", payload["sessions"][0]["spans"][0])

    def test_cli_source_pi_json(self) -> None:
        proc = subprocess.run(
            [
                sys.executable,
                "-m",
                "codex_usage_profiler.learning_cli",
                "--source",
                "pi",
                "--paths",
                str(FIXTURES / "learning_pi.jsonl"),
                "--format",
                "json",
            ],
            text=True,
            capture_output=True,
            check=False,
            env={"PYTHONPATH": str(Path(__file__).parents[1] / "src")},
        )
        self.assertEqual(proc.returncode, 0, proc.stderr)
        payload = json.loads(proc.stdout)
        self.assertEqual(payload["run"]["sources"], {"pi": 1})

    def test_object_role_does_not_crash(self) -> None:
        report = build_learning_report([str(FIXTURES / "learning_object_role.jsonl")])
        self.assertEqual(len(report.sessions), 0)

    def test_instruction_preamble_does_not_create_learning_signal(self) -> None:
        report = build_learning_report([str(FIXTURES / "learning_preamble_noise.jsonl")])
        self.assertEqual(len(report.sessions), 0)

    def test_snippet_redaction_covers_headers_urls_and_paths(self) -> None:
        report = build_learning_report(
            [str(FIXTURES / "learning_secret_headers.jsonl"), str(FIXTURES / "learning_cookie.jsonl")],
            include_snippets=True,
        )
        text = render_learning_json(report)
        self.assertNotIn("sid=abc", text)
        self.assertNotIn("csrf=def", text)
        self.assertNotIn("key123", text)
        self.assertNotIn("alex:pass@", text)
        self.assertNotIn("signed", text)
        self.assertNotIn("private/file.txt", text)
        self.assertNotIn("eyJabc.def.ghi", text)
        self.assertIn("<redacted>", text)

    def test_duplicate_session_ids_are_merged(self) -> None:
        report = build_learning_report(
            [
                str(FIXTURES / "learning_duplicate_a.jsonl"),
                str(FIXTURES / "learning_duplicate_b.jsonl"),
            ]
        )
        self.assertEqual(len(report.sessions), 1)
        self.assertEqual(report.sessions[0].session_id, "learn-duplicate")
        self.assertEqual(report.sessions[0].total_tokens, 2200)

    def test_git_fetch_and_generic_commands_do_not_overmatch(self) -> None:
        report = build_learning_report(
            [
                str(FIXTURES / "learning_git_fetch_noise.jsonl"),
                str(FIXTURES / "learning_generic_command_after_patch.jsonl"),
            ]
        )
        by_id = {session.session_id: session for session in report.sessions}
        self.assertNotIn("browser_request_replay", by_id["learn-git-fetch-noise"].feature_counts)
        self.assertEqual(by_id["learn-git-fetch-noise"].command_labels.get("request-replay", 0), 0)
        self.assertEqual(by_id["learn-generic-command"].transitions.get(f"{PHASE_IMPLEMENTATION}->{PHASE_INVESTIGATION}", 0), 0)

    def test_claude_and_pi_sources_parse_real_shapes(self) -> None:
        claude = build_learning_report([str(FIXTURES / "learning_claude.jsonl")], source="claude")
        self.assertEqual(claude.sessions[0].source, "claude")
        self.assertEqual(claude.sessions[0].project, "auth-tools")
        self.assertGreater(claude.sessions[0].total_tokens, 0)
        self.assertIn(PHASE_IMPLEMENTATION, [span.phase for span in claude.sessions[0].spans])
        self.assertIn(PHASE_VALIDATION, [span.phase for span in claude.sessions[0].spans])

        pi = build_learning_report([str(FIXTURES / "learning_pi.jsonl")], source="pi")
        self.assertEqual(pi.sessions[0].source, "pi")
        self.assertEqual(pi.sessions[0].project, "pi-worker")
        self.assertGreater(pi.sessions[0].command_labels.get("service-inventory", 0), 0)
        self.assertIn("project_memory", pi.sessions[0].feature_counts)

    def test_missing_validation_card(self) -> None:
        report = build_learning_report(
            [
                str(FIXTURES / "learning_pi.jsonl"),
                str(FIXTURES / "learning_generic_command_after_patch.jsonl"),
                str(FIXTURES / "learning_no_validation_a.jsonl"),
                str(FIXTURES / "learning_no_validation_b.jsonl"),
            ]
        )
        self.assertIn("Require proof after implementation", {card.title for card in report.cards})


if __name__ == "__main__":
    unittest.main()
