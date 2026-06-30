## ADDED Requirements

### Requirement: Attribute Sessions To Tasks
The system SHALL assign each session a task or end-goal label with evidence where available.

#### Scenario: Task evidence present
- **WHEN** a session contains a user request, thread title, branch name, issue ID, OpenSpec task reference, or automation name
- **THEN** the profiler records a task/end-goal label and supporting evidence

#### Scenario: No task evidence
- **WHEN** no task/end-goal evidence is available
- **THEN** the profiler labels the task as unknown

### Requirement: Classify Outcome Evidence
The system SHALL classify sessions by observable outcome evidence rather than subjective value alone.

#### Scenario: Durable output detected
- **WHEN** a session creates edits, commits, PRs, artifacts, successful tests, or explicit external actions
- **THEN** the profiler records productive outcome evidence

#### Scenario: Blocker detected
- **WHEN** a session ends with repeated failures, missing credentials, user-input requirements, or no successful action
- **THEN** the profiler records blocked or no-op outcome evidence

### Requirement: Detect Repeated Low-Value Patterns
The system SHALL surface repeated-work candidates with affected sessions and usage impact.

#### Scenario: Retry loop detected
- **WHEN** the same failing command or tool sequence repeats without intervening edits
- **THEN** the profiler reports a retry-loop finding with tokens, credits, cost, and quota share

#### Scenario: Repeated no-op automation detected
- **WHEN** scheduled or automated sessions repeatedly do little work and produce no durable output
- **THEN** the profiler reports a no-op automation finding with tokens, credits, cost, and quota share

#### Scenario: Repeated Paperclip diagnostics detected
- **WHEN** Paperclip sessions repeatedly run health checks, launchd checks, runtime-state checks, agent lists, help discovery, live-run polling, or launchd-log reads with little durable output
- **THEN** the profiler reports a Paperclip repeated-healthcheck finding grouped by company, project, and staff role with safe command-label evidence

### Requirement: Preserve Privacy In Value Analysis
The system SHALL avoid exposing raw prompt, response, or tool-output text by default.

#### Scenario: Task report generated
- **WHEN** the profiler prints task or usefulness reports
- **THEN** it uses labels, bounded redacted snippets, hashes, counts, and evidence types unless the user explicitly enables raw text output
