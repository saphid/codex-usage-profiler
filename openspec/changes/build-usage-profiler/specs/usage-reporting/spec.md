## ADDED Requirements

### Requirement: Report Usage By Client
The system SHALL produce a report ranking clients by comparative token usage and session count.

#### Scenario: Client summary requested
- **WHEN** the user runs the default report
- **THEN** the output includes total tokens, input tokens, cached input tokens, output tokens, session count, and share of observed tokens by client

### Requirement: Report Usage By Project
The system SHALL produce a report ranking projects by comparative token usage and session count.

#### Scenario: Project summary requested
- **WHEN** the user runs the default report
- **THEN** the output includes token totals, session count, and top clients per project

### Requirement: Report Paperclip Attribution
The system SHALL report Paperclip usage by company, project, staff role, and task with attribution coverage.

#### Scenario: Paperclip sessions found
- **WHEN** the scan includes Paperclip codex-home sessions
- **THEN** the report includes ranked Paperclip company, staff, project, and task summaries with token, cost, session-count, and observed-share totals

#### Scenario: Paperclip attribution incomplete
- **WHEN** company, staff, project, or task attribution is unknown for some Paperclip sessions
- **THEN** the report includes unknown buckets and enough coverage metrics to identify which metadata is missing

### Requirement: Report Usage By Task And Session
The system SHALL produce reports ranking tasks and individual sessions by usage impact.

#### Scenario: Task/session summary requested
- **WHEN** the user requests a task or session report
- **THEN** the output includes tokens, estimated credits, estimated cost, quota percentage, client, project, model, outcome classification, and evidence links for each task or session

### Requirement: Report Usage Over Time
The system SHALL summarize observed usage by configurable time bucket.

#### Scenario: Daily bucket
- **WHEN** the user selects daily grouping
- **THEN** the output groups token totals and session counts by local calendar day

#### Scenario: Hourly bucket
- **WHEN** the user selects hourly grouping
- **THEN** the output groups token totals and session counts by local hour

### Requirement: Surface Automation Concentration
The system SHALL highlight sessions and groups associated with automation or subagents.

#### Scenario: Automation sessions found
- **WHEN** sessions include `thread_source` values such as `automation` or `subagent`
- **THEN** the report includes a section ranking their token usage by project and client

### Requirement: Emit Machine Readable Output
The system SHALL support JSON output for normalized sessions and aggregate reports.

#### Scenario: JSON requested
- **WHEN** the user requests JSON output
- **THEN** the profiler emits valid JSON containing normalized session records, aggregates, warnings, and run metadata
