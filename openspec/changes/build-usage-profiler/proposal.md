## Why

Alex uses multiple AI coding harnesses against one Codex subscription, but current logs are scattered and hard to compare. A local profiler can turn existing session logs into practical quota, cost, and waste signals while labeling whether each number is exact, calibrated, or estimated.

## What Changes

- Add a small local CLI that discovers Codex session logs and extracts session metadata, token usage, model, working directory, and tool activity.
- Attribute each session to a likely client such as Codex CLI, Codex app, Pi Coding Agent, Cursor, or unknown using prompt fingerprints, paths, process/context clues, and configurable rules.
- Group usage by client, project, task/end goal, session, model, and time bucket.
- Estimate credits, effective cost, and quota percentage using a versioned rate card and optional usage-dashboard or credit-balance snapshots.
- Map sessions to likely tasks and end goals using local evidence such as prompts, cwd, branch, OpenSpec task references, issue IDs, edits, tests, commits, and final status.
- Detect repeated low-value patterns such as no-op automation, retry loops, repeated indexing, repeated MCP queries, startup-heavy sessions, and test loops without code changes.
- Produce human-readable reports plus machine-readable JSON for follow-up analysis.
- Add a rule-friendly internal event/session model so later inefficient-workflow detectors can reuse parsed logs.

## Capabilities

### New Capabilities

- `session-log-ingest`: Discover and parse Codex session logs from local filesystem sources into normalized session records.
- `usage-attribution`: Attribute normalized sessions to likely client and project labels with confidence and evidence.
- `usage-reporting`: Summarize comparative usage by client, project, model, time, and session activity.
- `quota-cost-estimation`: Estimate credits, cost, and quota percentage with confidence tiers.
- `outcome-value-analysis`: Connect sessions to tasks/end goals and surface low-value repeated-work candidates.
- `codexbar-telemetry-ingest`: Import CodexBar live usage, historical quota snapshots, local cost scans, and model pricing caches as calibration data.

### Modified Capabilities

None.

## Impact

- New standalone project at `/Users/saphid/Documents/codex-usage-profiler`.
- Local filesystem reads from configured Codex log locations, defaulting to common user-level Codex session paths.
- No network access required for MVP.
- Optional local config for rate cards, plan details, path aliases, and manually captured usage snapshots.
- CodexBar integration via installed CLI and local cache/history files when available.
- No account scraping in the MVP. Exact quota/cost labels require imported/account-derived data; local logs alone produce estimates.
