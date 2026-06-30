## Context

Codex Desktop writes JSONL session logs under `/Users/saphid/.codex/sessions/YYYY/MM/DD/` and older files under `/Users/saphid/.codex/archived_sessions/`. Observed records include `session_meta`, `turn_context`, `response_item`, and `event_msg`. Session metadata carries `source`, `originator`, `thread_source`, `cwd`, `cli_version`, and IDs. Turn context carries model, cwd, workspace roots, date, timezone, and sandbox settings. Response info carries cumulative `total_token_usage` with input, cached input, output, reasoning output, and total token counts.

The first design treated quota and value as out of scope. That is the main issue: Alex wants to know which tool, project, task, and session consumed tokens, credits, cost, and subscription allowance, then compare that against evidence of useful outcome. The profiler should be an agent waste profiler, not just a token dashboard.

Paperclip stores additional per-company and per-agent Codex homes under `~/.paperclip/instances/default/companies/*/.../codex-home/`. Those logs are the largest observed local usage source and need first-class discovery. Paperclip also leaves useful attribution context in company/agent instruction files and project task files, so the profiler can map many sessions to company, staff role, project, and sometimes explicit task IDs.

OpenAI's current Codex rate card maps token usage to credits per million input, cached input, and output tokens. Codex plan limits still depend on plan, model, task size, local/cloud execution, and shared agentic usage. Therefore exact subscription-percentage reconstruction from local logs alone is not guaranteed, but the tool should still try with confidence levels and calibration inputs.

CodexBar is installed locally at `/Applications/CodexBar.app` with CLI `codexbar` version 0.37.2. It is a first-class calibration source. Its public docs describe Codex sources in this order: OAuth API, CLI RPC, optional OpenAI web dashboard extras, CLI PTY diagnostics, and local cost-usage scanning. Local observed paths:

- Config: `~/.config/codexbar/config.json`
- Live/history: `~/Library/Application Support/com.steipete.codexbar/history/codex.json`
- Local cost cache: `~/Library/Caches/CodexBar/cost-usage/codex-v8.json`
- Pi sessions cache: `~/Library/Caches/CodexBar/cost-usage/pi-sessions-v3.json`
- Model pricing cache: `~/Library/Caches/CodexBar/model-pricing/models-dev-v1.json`
- Widget snapshot: `~/Library/Group Containers/Y5PE65HELJ.com.steipete.codexbar/widget-snapshot.json`

Observed CLI outputs:

- `codexbar usage --provider codex --source auto --format json` returns exact current Codex windows, credits, reset times, account plan/login method, Spark windows, and confidence.
- `codexbar cost --provider codex --format json` returns daily token/cost totals and model breakdowns from local Codex/Pi session scans.

## Goals / Non-Goals

**Goals:**

- Build a fast read-only profiler for local Codex JSONL session files and CodexBar telemetry.
- Normalize sessions into stable records: identity, time range, client, project, task, model, token totals, credit estimate, cost estimate, tool counts, and attribution evidence.
- Report usage by client, project, task, session, model, day/hour, and thread source.
- Estimate quota pressure as percentages with confidence levels:
  - observed usage share inside the scanned logs
  - estimated credit/cost share from token-based Codex rates
  - exact current quota windows from CodexBar usage output when available
  - calibrated historical subscription-quota share from CodexBar history, usage-dashboard, or credit-balance snapshots
- Map sessions to end goals using local evidence: first user request, thread title/source, cwd, branch, OpenSpec change/task references, issue IDs, commits, file edits, tests, PR actions, calendar/mail/external writes, and final status.
- Attribute Paperclip sessions to company, project, staff/agent role, and task/issue ID when evidence is present in codex-home paths, agent instructions, project files, or first request fields.
- Detect low-value/repeated-work patterns using objective evidence before any subjective usefulness score.

**Non-Goals:**

- Do not claim official billing accuracy unless backed by exported/account usage data.
- Do not scrape account pages in the MVP; allow manual snapshot/import first.
- Do not send private prompts, logs, repo contents, or usage data to a remote service.
- Do not mutate, archive, or clean up Codex logs.

## Decisions

1. Implement as a Python CLI using standard library first.

   Rationale: JSONL parsing, path walking, datetime bucketing, counters, config loading, and table rendering are straightforward without dependencies. If later account dashboard ingestion needs browser automation, keep that as a separate optional adapter.

2. Treat JSONL session files as primary for per-session attribution, and CodexBar as primary for quota/cost calibration.

   Rationale: JSONL contains local session tokens and task evidence. CodexBar already knows how to fetch current Codex quota windows, parse local Codex/Pi cost usage, cache model pricing, and store historical usage snapshots. Account usage state is needed for actual subscription percentage because other agentic features and server-side metering can affect limits. The design supports these accuracy tiers:

   - `observed`: percent of scanned local usage
   - `estimated`: token usage converted to credits/cost using configured rate card
   - `exact_current`: current quota windows from CodexBar/OAuth/CLI RPC
   - `calibrated`: estimated sessions reconciled to CodexBar history, usage snapshots, or credit-balance deltas

3. Use CodexBar CLI before reading private cache internals.

   Rationale: `codexbar usage` and `codexbar cost` are documented machine-readable interfaces. Cache files are useful for historical data and offline operation, but their schema names have already versioned locally (`codex-v8`, `pi-sessions-v3`) while docs mention older versions. Treat cache parsing as best-effort with version capture and fallback.

4. Use final cumulative token usage per session.

   Rationale: `payload.info.total_token_usage` is cumulative within a session. Taking the latest/greatest snapshot avoids double counting. Per-turn deltas can be derived later for intra-session timelines.

5. Convert tokens to credits through a versioned local rate card, preferring CodexBar pricing cache when present.

   Rationale: Codex flexible pricing is token-based for most current plans. Store model rates with `effective_date`, `source_url`, and token-type prices. Formula:

   `credits = input_tokens / 1_000_000 * input_rate + cached_input_tokens / 1_000_000 * cached_input_rate + output_tokens / 1_000_000 * output_rate`

   If a model is research preview or unknown, report tokens and mark credits/cost as unknown unless the user config supplies rates.

6. Separate credits, cost, and subscription quota.

   Rationale: They answer different questions.

   - credits: Codex usage unit from token mix
   - cost: estimated dollars from purchased-credit value or configured exchange rate
   - quota percentage: observed/calibrated share of allowance window

   For included Plus/Pro plan usage, cost is best shown as effective allocation of monthly plan price or replacement-credit estimate, not official bill.

7. Attribute task/end goal as an evidence graph.

   Rationale: A single session can represent a user task, subagent task, OpenSpec task, issue, branch, or automation run. The tool should create local entities:

   ```
   session -> thread -> task/end_goal -> project -> client
             \-> evidence: prompt summary, cwd, branch, files, tools, commits, tests, final status
   ```

   It should prefer deterministic evidence. Optional local-only summarization can be added later, but MVP should use rule-based extraction and short redacted snippets.

8. Treat Paperclip as a structured local source, not just another cwd.

   Rationale: Paperclip per-agent Codex homes encode company and agent IDs in paths while AGENTS.md and project task files provide human-readable role, company, project, and task names. The profiler should build a read-only `PaperclipIndex`, then enrich sessions with:

   - company from company/agent/project metadata
   - staff role from agent instruction headings or "You are ..." text
   - project from prompt fields, project files, or cwd
   - task from explicit `Task:`, issue IDs, or structured project-task metadata

   When task IDs are absent, the report should say attribution is unknown rather than guessing from unrelated filenames.

9. Score usefulness from outcomes and waste patterns, not vibes.

   Rationale: "Was it useful?" is subjective, but useless repeated tasks leave traces. The MVP should classify sessions into evidence buckets:

   - `productive`: edits, commits, PRs, tests fixed, external action completed, artifact created
   - `exploratory`: meaningful reads/searches/design without edits
   - `blocked`: ended with blocker/error/needs user input
   - `no-op`: little activity and no durable output
   - `repeated`: similar task/tool sequence repeated across windows
   - `unknown`: insufficient evidence

9. Output both text and JSON.

   Rationale: Text answers immediate questions; JSON lets later detectors, charts, or notebooks consume normalized records.

## Data Flow

```
JSONL logs ───────┐
CodexBar usage ───┤
CodexBar cost ────┼─ ingest ─ normalize sessions ─ attribute client/project/task
CodexBar history ─┤                                      │
rate card/cache ──┤                                      ▼
quota snaps ──────┘                             usage + evidence model
                                                  │
                                                  ▼
                      reports: tokens, rate-card cost, live quota, review evidence
```

## Quota And Cost Model

- Local logs provide token counts per session and task evidence.
- CodexBar cost output/cache provides daily/model token and cost totals over a rolling history, including supported Pi sessions.
- CodexBar usage output provides exact current 5-hour/weekly/Spark windows, reset times, credits, and data confidence.
- CodexBar history provides timestamped used-percent/reset snapshots that may later calibrate historical local-session estimates when reset windows can be matched.
- Rate card or CodexBar model-pricing cache provides model/token-type cost conversion.
- User config may provide plan, monthly plan price, purchased-credit value, and optional manual snapshots.
- Current implementation reports live quota windows and local-vs-CodexBar ratios; it does not claim historical quota allocation unless a matching calibration interval is implemented.
- Reports must label every number:
  - `exact`: directly from imported account usage/credit record
  - `exact_current`: directly from current CodexBar usage/OAuth/CLI RPC output
  - `calibrated_estimate`: local session allocation reconciled to account delta; deferred until matching reset-window calibration exists
  - `rate_card_estimate`: token-to-cost calculation only
  - `observed_share`: percent of scanned logs only
  - `unknown`: missing rates or missing token data

## Waste Pattern Model

Initial detectors should be deterministic:

- heartbeat/no-op: repeated scheduled sessions with no model-worthy work or no durable output
- repeated command signature: same command or tool signature repeated without intervening edits; this is a review candidate, not proof of a failed retry loop
- repeated indexing: large reads/searches of same repo paths across nearby sessions
- repeated MCP query: same connector/tool query returns similar metadata repeatedly
- repeated Paperclip health/runtime checks: repeated `api/health`, `launchctl`, `plutil`, `runtime-state`, `agent list`, `activity --help`, live-run, or launchd-log checks with no durable user-facing output
- startup-heavy: high input/cached-input usage with little tool/output activity
- test loop: same test command fails repeatedly with no code edits between runs
- long idle/low activity: long session span with low tool/action count and no output

Each finding should include evidence, affected sessions, observed tokens, rate-card cost, overlap-aware session IDs, and confidence. Quota share is deferred until calibrated historical quota windows are available.

## Risks / Trade-offs

- Exact historical quota percent may be impossible from local logs alone -> report confidence tier and use CodexBar snapshots where available.
- CodexBar cache schema can change -> prefer CLI JSON, then parse caches with version guards.
- Rate cards change -> keep rates versioned and user-overridable.
- Prompt/task extraction can expose private text -> default to short redacted snippets and local-only processing.
- Attribution mistakes -> include confidence/evidence and keep unknown as valid.
- Paperclip task attribution depends on explicit task IDs being present in prompts, paths, or project files -> report coverage and recommend adding task metadata at session start.
- False waste positives -> report "review candidates", not accusations.
- Large log sets -> stream JSONL and retain only normalized summaries plus bounded fingerprints.

## Migration Plan

Initial project has no runtime migration. Implementation will add files under the project, then validate against fixtures plus a read-only scan of local logs.

The first usable release should support CodexBar CLI import, CodexBar cost cache import, `rate_card_estimate`, `observed_share`, and exact current quota windows. A follow-up release should improve historical reconciliation from CodexBar history and manual snapshots.

Rollback is deleting the project checkout; no external state is written.

## Open Questions

- What plan tier should be the default config: Plus, Pro 5x, Pro 20x, Business, or manual?
- How much of CodexBar's `history/codex.json` should be trusted as stable versus treated as best-effort cache?
- Should task summaries use raw first-user-message snippets by default, or only hashes/derived labels unless explicitly enabled?
