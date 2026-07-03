#!/usr/bin/env bash
set -euo pipefail

APP_HOME="${CUP_APP_HOME:-$HOME/services/codex-usage-profiler}"
DATA_HOME="${CUP_DATA_HOME:-$HOME/.local/share/codex-usage-profiler}"
STATE_HOME="${CUP_STATE_HOME:-$HOME/.local/state/codex-usage-profiler}"
LOG_HOME="${CUP_LOG_HOME:-$HOME/.local/log/codex-usage-profiler}"
PYTHON="${CUP_PYTHON:-$APP_HOME/.venv/bin/python}"
REPORT="$STATE_HOME/latest-report.json"
TMP_REPORT="$STATE_HOME/latest-report.tmp.json"
LOG_FILE="$LOG_HOME/report-refresh.jsonl"
SYSLOG_HOST="${CUP_SYSLOG_HOST:-192.168.1.30}"
SYSLOG_PORT="${CUP_SYSLOG_PORT:-514}"
LOKI_URL="${CUP_LOKI_URL:-http://192.168.1.221:3100/loki/api/v1/push}"
PORT="${CUP_PORT:-8775}"

mkdir -p "$STATE_HOME" "$LOG_HOME" "$DATA_HOME/collected-sessions"
exec 9>"$STATE_HOME/report-refresh.lock"
if ! flock -n 9; then
  echo '{"event":"report_refresh_skipped","reason":"already_running"}'
  exit 0
fi
export CODEXBAR_COLLECTED_ROOT="$DATA_HOME/collected-sessions"

paths=("$DATA_HOME/collected-sessions")

started="$(date +%s)"
"$PYTHON" -m codex_usage_profiler \
  --codexbar-timeout 10 \
  --paths "${paths[@]}" \
  --format json \
  --output "$TMP_REPORT" \
  --monthly-plan-price-usd "${CUP_MONTHLY_PLAN_PRICE_USD:-200}" \
  --plan-price Plus=20 \
  --plan-price Pro=200
mv "$TMP_REPORT" "$REPORT"

"$PYTHON" - "$REPORT" "$LOG_FILE" "$SYSLOG_HOST" "$SYSLOG_PORT" "$LOKI_URL" "$started" "$PORT" <<'PY'
import json
import sys
import time
from pathlib import Path

from codex_usage_profiler.syslog_util import emit_loki_json, emit_syslog_json

report_path = Path(sys.argv[1])
log_path = Path(sys.argv[2])
syslog_host = sys.argv[3]
syslog_port = int(sys.argv[4])
loki_url = sys.argv[5]
started = int(sys.argv[6])
port = sys.argv[7]
payload = json.loads(report_path.read_text(encoding="utf-8"))
tokens = sum((s.get("usage") or {}).get("total_tokens", 0) for s in payload.get("sessions", []))
cost = sum((s.get("estimate") or {}).get("cost_usd") or 0.0 for s in payload.get("sessions", []))
event = {
    "event": "report_refresh",
    "sessions": len(payload.get("sessions", [])),
    "tokens": tokens,
    "cost_usd": round(cost, 6),
    "report_path": str(report_path),
    "dashboard_port": port,
    "duration_seconds": round(time.time() - started, 3),
    "warnings": payload.get("warnings", [])[:10],
}
log_path.parent.mkdir(parents=True, exist_ok=True)
with log_path.open("a", encoding="utf-8") as fh:
    fh.write(json.dumps(event, sort_keys=True) + "\n")
emit_syslog_json(event, host=syslog_host, port=syslog_port, tag="codex-usage-profiler")
emit_loki_json(event, url=loki_url, labels={"service": "report", "host": "lxso1"})
print(json.dumps(event, sort_keys=True))
PY
