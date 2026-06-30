## 1. Project Skeleton

- [x] 1.1 Add `README.md` with MVP scope, privacy stance, and example commands
- [x] 1.2 Add `pyproject.toml` for a standard-library Python CLI package
- [x] 1.3 Create package/module layout for parser, attribution, reporting, and CLI entrypoint
- [x] 1.4 Add `.gitignore` for Python caches, virtualenvs, and generated reports

## 2. Session Log Ingest

- [x] 2.1 Implement default and explicit JSONL log discovery
- [x] 2.2 Implement streaming JSONL parser with per-file warnings
- [x] 2.3 Normalize `session_meta` and `turn_context` fields into session records
- [x] 2.4 Extract final cumulative token usage from `payload.info.total_token_usage`
- [x] 2.5 Count event and tool-call activity without retaining raw message text
- [x] 2.6 Extract bounded task/outcome evidence: first request label, tool sequence, edits, tests, commits, final status, and artifact markers

## 3. CodexBar Telemetry

- [x] 3.1 Detect CodexBar CLI, app version, config path, cache paths, and history paths
- [x] 3.2 Import live Codex quota windows from `codexbar usage --provider codex --source auto --format json`
- [x] 3.3 Import daily/model token and cost aggregates from `codexbar cost --provider codex --format json`
- [x] 3.4 Parse CodexBar cost cache and model-pricing cache with version guards
- [x] 3.5 Parse CodexBar quota history snapshots from `history/codex.json`
- [x] 3.6 Redact CodexBar secret-like fields in diagnostics and JSON output

## 4. Attribution

- [x] 4.1 Implement client attribution from `originator`, `source`, `thread_source`, and source objects
- [x] 4.2 Implement project attribution from cwd, workspace roots, Documents paths, and Codex worktree paths
- [x] 4.3 Implement task/end-goal attribution from prompt labels, branches, issue IDs, OpenSpec references, automation names, and session metadata
- [x] 4.4 Add confidence and evidence fields to each attribution result
- [x] 4.5 Add optional local config loading for path/client/task aliases, plan settings, rate cards, CodexBar settings, and usage snapshots

## 5. Quota And Cost

- [x] 5.1 Implement versioned rate-card loading and model-rate matching, preferring CodexBar pricing cache when available
- [x] 5.2 Estimate directional rate-card cost from input, cached input, and output token counts
- [x] 5.3 Estimate credits only when configured credit conversion is available
- [x] 5.4 Implement observed-share quota percentages from scanned local sessions
- [x] 5.5 Implement exact-current quota report from CodexBar live usage
- [ ] 5.6 Implement calibrated historical quota percentages from matching CodexBar history and imported usage/credit snapshots
- [x] 5.7 Compare direct JSONL totals against CodexBar daily/model cost aggregates and report scope-ratio gaps
- [x] 5.8 Label every quota/cost number with confidence tier

## 6. Outcome And Waste Analysis

- [x] 6.1 Classify session outcomes as durable-output, exploratory, blocked, no-op, startup-heavy, or unknown evidence buckets
- [x] 6.2 Detect no-op automation and heartbeat-like sessions
- [x] 6.3 Detect repeated command signatures without intervening edits; proving retry loops after failures is deferred
- [x] 6.4 Detect repeated indexing or repeated MCP/tool queries
- [x] 6.5 Detect startup-heavy sessions and test loops with no intervening code changes
- [x] 6.6 Attach tokens, rate-card cost, sessions, and evidence to each finding; quota share is deferred until historical quota calibration exists

## 7. Reporting

- [x] 7.1 Implement aggregate summaries by client, project, task, model, and thread source
- [x] 7.2 Implement per-session usage and outcome report
- [x] 7.3 Implement daily and hourly time bucket summaries
- [x] 7.4 Implement automation/subagent concentration report section
- [x] 7.5 Implement CodexBar telemetry status and reconciliation report
- [x] 7.6 Implement compact text table output
- [x] 7.7 Implement JSON output for normalized sessions, aggregates, warnings, findings, CodexBar telemetry, and run metadata

## 8. Tests And Verification

- [x] 8.1 Add JSONL fixtures for complete, partial, missing-usage, object-valued metadata, and repeated-work sessions
- [x] 8.2 Add CodexBar fixture files for usage output, cost output, cache metadata, pricing cache, and history snapshots
- [x] 8.3 Add parser tests for discovery, metadata normalization, token extraction, and outcome evidence extraction
- [x] 8.4 Add CodexBar telemetry tests for CLI JSON import, cache parsing, history parsing, and redaction
- [x] 8.5 Add attribution tests for known client/project/task/path cases
- [x] 8.6 Add quota/cost tests for known, unknown, exact-current, and calibrated rate scenarios
- [x] 8.7 Add reporting tests for aggregation, findings, confidence labels, reconciliation, and JSON output validity
- [x] 8.8 Run a read-only smoke scan against local Codex logs and CodexBar telemetry and verify no raw prompt/response text or secrets appear in default output

## 9. Paperclip Attribution And Waste Detection

- [x] 9.1 Discover Paperclip company-level and per-agent Codex homes by default
- [x] 9.2 Build a read-only Paperclip index from company/agent instructions and project task files
- [x] 9.3 Attribute Paperclip sessions to company, project, staff role, and explicit task/issue ID when evidence exists
- [x] 9.4 Add privacy-safe command labels for repeated Paperclip diagnostics
- [x] 9.5 Detect repeated Paperclip health/runtime/help/live-run diagnostics grouped by company, project, and staff role
- [x] 9.6 Add Paperclip company, staff, project, and task summaries to text and JSON reports
- [x] 9.7 Add unit fixture coverage and subprocess end-to-end coverage for Paperclip attribution
- [x] 9.8 Run the profiler against local Codex, CodexBar, and Paperclip logs and review spend/cleanup findings
