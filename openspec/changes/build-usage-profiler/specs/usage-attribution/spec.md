## ADDED Requirements

### Requirement: Attribute Client
The system SHALL assign each session a client label, confidence level, and evidence list.

#### Scenario: Direct originator signal
- **WHEN** session metadata includes a known `originator` or `source`
- **THEN** the profiler labels the client using that signal and records it as evidence

#### Scenario: Ambiguous client
- **WHEN** available signals do not identify a known client
- **THEN** the profiler labels the client as `unknown` with low confidence

### Requirement: Attribute Project
The system SHALL assign each session a project label derived from cwd, workspace roots, or configured path aliases.

#### Scenario: Documents project path
- **WHEN** cwd is under `~/Documents/<project>`
- **THEN** the profiler labels the project as `<project>`

#### Scenario: Codex worktree path
- **WHEN** cwd is under `~/.codex/worktrees/<id>/<project>`
- **THEN** the profiler labels the project as `<project>` rather than the transient worktree ID

#### Scenario: Missing cwd
- **WHEN** no cwd or workspace root exists
- **THEN** the profiler labels the project as `unknown`

### Requirement: Distinguish Invocation Type
The system SHALL preserve whether a session appears user-started, automated, or subagent-spawned.

#### Scenario: Thread source present
- **WHEN** `thread_source` is present in session metadata
- **THEN** the normalized session includes that thread source for grouping and filtering

#### Scenario: Subagent source object
- **WHEN** a metadata field contains subagent spawn details
- **THEN** the profiler records the session as subagent-related without failing on object-valued metadata

### Requirement: Support Configurable Rules
The system SHALL allow built-in attribution rules to be extended by a project-local config file.

#### Scenario: Alias configured
- **WHEN** config maps a path prefix or source fingerprint to a client or project label
- **THEN** the profiler applies the configured label and records the matching rule as evidence

### Requirement: Attribute Paperclip Sessions
The system SHALL assign Paperclip company, project, staff role, and task labels when deterministic local evidence exists.

#### Scenario: Paperclip agent codex-home path
- **WHEN** a session path is under `~/.paperclip/instances/default/companies/<company-id>/agents/<agent-id>/codex-home`
- **THEN** the profiler uses Paperclip company and agent instruction metadata to label the client, company, and staff role

#### Scenario: Paperclip project metadata exists
- **WHEN** Paperclip project/task files or first-request fields identify `Company`, `Project`, `Queue`, `Task`, `Title`, `Submitted by`, or `Agent`
- **THEN** the profiler records project, task, and staff attribution evidence

#### Scenario: Paperclip task evidence missing
- **WHEN** a Paperclip session lacks explicit task or issue evidence
- **THEN** the profiler leaves task unknown and reports attribution coverage instead of inferring a task from unrelated filenames
