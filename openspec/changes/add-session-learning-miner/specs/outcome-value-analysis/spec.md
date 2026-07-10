## MODIFIED Requirements

### Requirement: Classify Outcome Evidence
The system SHALL classify sessions by observable outcome evidence rather than subjective value alone, and SHALL expose phase-aware evidence where available.

#### Scenario: Durable output detected
- **WHEN** a session creates edits, commits, PRs, artifacts, successful tests, or explicit external actions
- **THEN** the profiler records productive outcome evidence and links it to implementation or proof/validation phase spans when those spans are available

#### Scenario: Blocker detected
- **WHEN** a session ends with repeated failures, missing credentials, user-input requirements, or no successful action
- **THEN** the profiler records blocked or no-op outcome evidence and links it to the failed phase or transition when that evidence is available

#### Scenario: Strategy drift detected
- **WHEN** a session's observable activity shifts from one approach to a different approach before successful validation or final status
- **THEN** the profiler records the transition as outcome evidence for learning-mining review
