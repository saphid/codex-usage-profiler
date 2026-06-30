## ADDED Requirements

### Requirement: Discover Session Logs
The system SHALL discover Codex JSONL session logs from configured roots and default local Codex session roots.

#### Scenario: Default roots exist
- **WHEN** the profiler runs without explicit input paths
- **THEN** it scans `~/.codex/sessions`, `~/.codex/archived_sessions`, and Paperclip per-company/per-agent Codex homes for `*.jsonl` files

#### Scenario: Explicit root provided
- **WHEN** the user provides one or more log paths
- **THEN** the profiler scans only those files or directories

#### Scenario: Paperclip codex homes exist
- **WHEN** `~/.paperclip/instances/default/companies/*/codex-home` or `~/.paperclip/instances/default/companies/*/agents/*/codex-home` exists
- **THEN** the profiler discovers nested `sessions` and `archived_sessions` logs without requiring explicit paths

### Requirement: Parse Session Metadata
The system SHALL parse session identity, timestamps, working directory, model, source, originator, thread source, and workspace roots from supported event records.

#### Scenario: Metadata fields present
- **WHEN** a session file contains `session_meta` and `turn_context` records
- **THEN** the normalized session includes IDs, cwd, model, source, originator, thread source, and workspace roots where present

#### Scenario: Metadata fields missing or typed unexpectedly
- **WHEN** a session file omits metadata or contains non-string metadata values
- **THEN** parsing continues and the normalized session records missing values plus warnings

### Requirement: Extract Token Usage
The system SHALL extract cumulative token usage from supported response usage snapshots without double counting.

#### Scenario: Multiple cumulative snapshots
- **WHEN** a session contains multiple `payload.info.total_token_usage` snapshots
- **THEN** the normalized session uses the latest or greatest cumulative totals for that session

#### Scenario: No usage snapshot
- **WHEN** a session contains no token usage snapshot
- **THEN** the normalized session remains reportable with token totals set to zero or unknown

### Requirement: Preserve Privacy By Default
The system SHALL avoid printing raw prompt, response, or tool-output text during ingestion and reporting.

#### Scenario: Report generated
- **WHEN** the profiler prints a report
- **THEN** it includes metadata, counts, paths, and attribution evidence but not message bodies by default

### Requirement: Classify Safe Command Labels
The system SHALL derive bounded command labels for repeated-work detection without storing raw shell commands in default reports.

#### Scenario: Known Paperclip diagnostic command
- **WHEN** a command checks Paperclip health, launchd state, runtime state, agent lists, activity help, live runs, or launchd logs
- **THEN** the normalized session records a privacy-safe command label such as `paperclip:api_health` or `paperclip:agent_runtime_state`

#### Scenario: Unknown command
- **WHEN** a command does not match a known safe label
- **THEN** the profiler records only a generic command class and fingerprint by default
