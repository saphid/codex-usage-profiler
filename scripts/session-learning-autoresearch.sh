#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
OUT="${1:-$ROOT/reports/autoresearch}"
mkdir -p "$OUT"

export PYTHONPATH="$ROOT/src${PYTHONPATH:+:$PYTHONPATH}"

run_report() {
  local name="$1"
  shift
  python3 -m codex_usage_profiler.learning_cli "$@" --format json --output "$OUT/$name.json"
  python3 -m codex_usage_profiler.learning_cli "$@" --format md --output "$OUT/$name.md"
}

run_report local-all --source all

if [ -d "$ROOT/reports/lxso1-codex-sessions" ]; then
  run_report lxso1-codex --source codex --paths "$ROOT/reports/lxso1-codex-sessions"
fi

if [ -d "$ROOT/reports/lxso1-pi-sessions" ]; then
  run_report lxso1-pi --source pi --paths "$ROOT/reports/lxso1-pi-sessions"
fi

if [ -d "$ROOT/reports/lxso1-hermes-sessions" ]; then
  run_report lxso1-hermes --source generic --paths "$ROOT/reports/lxso1-hermes-sessions"
fi

python3 - <<'PY' "$OUT"
import json
import sys
from pathlib import Path

out = Path(sys.argv[1])
lines = ["# Session Learning Autoresearch", ""]
for path in sorted(out.glob("*.json")):
    data = json.loads(path.read_text())
    run = data["run"]
    lines.append(f"## {path.stem}")
    lines.append("")
    lines.append(f"- Sessions: {run['session_count']}")
    lines.append(f"- Cards: {run['card_count']}")
    lines.append(f"- Sources: {run.get('sources', {})}")
    for card in data["cards"][:8]:
        lines.append(f"- {card['frequency']} sessions: {card['title']} ({card['problem_type']})")
    lines.append("")
summary = "\n".join(lines).rstrip() + "\n"
(out / "summary.md").write_text(summary)
print(out / "summary.md")
PY
