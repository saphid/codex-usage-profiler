## ADDED Requirements

### Requirement: Discover CodexBar Sources
The system SHALL discover installed CodexBar CLI, config, cache, and history sources without requiring secrets to be printed.

#### Scenario: CodexBar installed
- **WHEN** CodexBar CLI or known local CodexBar paths exist
- **THEN** the profiler records available source paths, versions, and capabilities

#### Scenario: CodexBar missing
- **WHEN** CodexBar is not installed
- **THEN** the profiler continues with direct Codex log ingestion and reports CodexBar telemetry as unavailable

### Requirement: Import Live Codex Usage
The system SHALL import live Codex quota windows from CodexBar when available.

#### Scenario: CLI usage succeeds
- **WHEN** `codexbar usage --provider codex --source auto --format json` returns valid JSON
- **THEN** the profiler imports current quota percentages, reset times, credits, extra rate windows, source, and data confidence

#### Scenario: CLI usage fails
- **WHEN** CodexBar usage command fails or times out
- **THEN** the profiler records a warning and falls back to local log estimates

### Requirement: Import CodexBar Cost History
The system SHALL import CodexBar local cost usage output or cache as aggregate calibration data.

#### Scenario: CLI cost succeeds
- **WHEN** `codexbar cost --provider codex --format json` returns valid JSON
- **THEN** the profiler imports daily token totals, daily cost totals, model breakdowns, and currency code

#### Scenario: Cache available
- **WHEN** CodexBar cost cache files exist
- **THEN** the profiler imports cache metadata and best-effort daily/model aggregates while preserving cache version and producer key

### Requirement: Import Historical Quota Snapshots
The system SHALL import timestamped CodexBar quota history when available.

#### Scenario: History exists
- **WHEN** `~/Library/Application Support/com.steipete.codexbar/history/codex.json` exists
- **THEN** the profiler imports used percent, reset time, capture time, account key, and window type without exposing account secrets

### Requirement: Redact CodexBar Secrets
The system SHALL avoid exposing CodexBar tokens, cookies, API keys, account identifiers, or raw auth files.

#### Scenario: Diagnostics generated
- **WHEN** the profiler reports CodexBar source status or errors
- **THEN** it redacts secret-like fields and shows only non-sensitive paths, schema versions, timestamps, and aggregate usage
