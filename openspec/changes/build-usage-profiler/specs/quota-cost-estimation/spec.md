## ADDED Requirements

### Requirement: Estimate Credits From Tokens
The system SHALL estimate Codex credits from token usage using a versioned local rate card.

#### Scenario: Known model rates
- **WHEN** a session has token usage and its model exists in the rate card
- **THEN** the profiler calculates estimated credits from input, cached input, and output token rates

#### Scenario: Unknown model rates
- **WHEN** a session model is missing from the rate card
- **THEN** the profiler reports token usage and marks credits and cost as unknown for that session

### Requirement: Estimate Effective Cost
The system SHALL estimate effective cost from credits using configured purchased-credit or plan-allocation values.

#### Scenario: Credit value configured
- **WHEN** the config includes a dollars-per-credit value
- **THEN** reports include estimated cost by session, task, project, client, and time bucket

#### Scenario: No cost basis configured
- **WHEN** no cost basis is configured
- **THEN** reports omit dollar totals or mark them as unknown while still showing tokens and credits

### Requirement: Estimate Quota Percentage
The system SHALL report live quota telemetry and observed local usage shares using the best available confidence tier.

#### Scenario: CodexBar live usage available
- **WHEN** CodexBar live usage returns current quota windows
- **THEN** reports show exact current 5-hour, weekly, and model-specific quota telemetry with reset times

#### Scenario: Local logs only
- **WHEN** no account usage snapshots are provided
- **THEN** reports show observed-share percentages within the scanned local sessions

#### Scenario: Usage snapshots provided
- **WHEN** CodexBar history, usage-dashboard, or credit-balance snapshots bound a time interval
- **THEN** the profiler allocates the observed account delta across sessions in that interval and labels results as calibrated estimates

### Requirement: Label Estimate Confidence
The system SHALL label quota, credit, and cost numbers with their confidence tier.

#### Scenario: Report generated
- **WHEN** a report includes quota, credit, or cost values
- **THEN** each value or section states whether it is exact, exact_current, calibrated_estimate, rate_card_estimate, observed_share, or unknown
