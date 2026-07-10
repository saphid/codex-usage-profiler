## ADDED Requirements

### Requirement: Extract Phase Spans
The system SHALL decompose each analyzed session into evidence-backed phase spans for request/idea, investigation/research/discovery, understanding, implementation, and proof/validation.

#### Scenario: Linear session analyzed
- **WHEN** a session contains a user request, file reads, a stated plan, patches, and test commands
- **THEN** the miner records corresponding phase spans with evidence and confidence

#### Scenario: Interleaved session analyzed
- **WHEN** a session alternates between implementation, validation failure, and renewed investigation
- **THEN** the miner records repeated phase spans and transition evidence instead of forcing one linear sequence

### Requirement: Ingest Multiple Agent Session Sources
The system SHALL analyze Codex, Claude Code, Pi, and generic JSON/JSONL session logs without modifying source logs.

#### Scenario: Source-specific scan
- **WHEN** a user runs the miner with `--source codex`, `--source claude`, `--source pi`, or `--source generic`
- **THEN** the miner discovers or parses logs for that source and records the source in each session and card

#### Scenario: Explicit all-source paths
- **WHEN** a user runs the miner with `--source all --paths`
- **THEN** each path is parsed once using source detection rather than being parsed repeatedly by every adapter

### Requirement: Mine Learning Candidates Deterministically
The system SHALL use deterministic scanners to identify learning candidates before any interpretive summarization.

#### Scenario: Repeated browser request replay workflow
- **WHEN** multiple sessions mention cookies, auth headers, curl or fetch replay, browser extensions, HAR/CDP capture, or request manifests
- **THEN** the miner reports a browser/auth request-replay learning candidate with affected sessions and redacted evidence

#### Scenario: Repeated project setup rediscovery
- **WHEN** multiple sessions repeatedly discover the same repo instruction, launchd service, host, script, or infrastructure detail
- **THEN** the miner reports a project-memory or infrastructure learning candidate

### Requirement: Compare Phase Patterns Across Sessions
The system SHALL compare phase spans and transitions across sessions to find recurring process patterns.

#### Scenario: Repeated late pivot detected
- **WHEN** several sessions start with one approach and later switch to a more successful approach after validation or discovery
- **THEN** the miner clusters those transitions and reports the repeated "tried X, eventually did Y" pattern

#### Scenario: Cross-project lesson detected
- **WHEN** similar phase patterns occur across unrelated projects
- **THEN** the miner marks the candidate as global or harness/tooling scope when evidence supports that scope

### Requirement: Emit Reviewable Learning Cards
The system SHALL emit learning cards that identify problems and learnings without applying fixes automatically.

#### Scenario: Learning card generated
- **WHEN** a learning candidate passes recurrence, confidence, and fixability thresholds
- **THEN** the miner emits a card with title, scope, problem type, phase pattern, evidence sessions, source counts, phase evidence counts, confidence, fixability, token impact, and recommended destination

#### Scenario: Candidate is not actionable
- **WHEN** evidence suggests a model limitation, one-off issue, or low-confidence pattern
- **THEN** the miner labels the card accordingly or suppresses it below threshold rather than recommending an automatic fix

### Requirement: Preserve Privacy In Learning Reports
The system SHALL avoid exposing raw private prompts, responses, tool outputs, cookies, tokens, auth headers, or full private URLs by default.

#### Scenario: Default report generated
- **WHEN** the miner writes JSON or Markdown reports
- **THEN** it uses labels, hashes, counts, redacted snippets, and evidence types unless raw snippets are explicitly enabled

### Requirement: Run Autoresearch Reports
The system SHALL provide a repeatable local runner for generating learning reports across local and copied LXSO1 session data.

#### Scenario: Autoresearch runner executed
- **WHEN** LXSO1 session directories have been copied into ignored local report directories
- **THEN** the runner emits per-source reports and a summary without requiring remote mutation or raw snippets
