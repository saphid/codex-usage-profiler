## ADDED Requirements

### Requirement: Local Dashboard Serving
The system SHALL serve a local web dashboard for a selected profiler JSON report without requiring external services.

#### Scenario: Serve selected report
- **WHEN** a user starts the dashboard server with a report path
- **THEN** the system serves the dashboard HTML, CSS, JavaScript, and the selected report at `/api/report`

#### Scenario: Tailscale reachable binding
- **WHEN** a user starts the server with host `0.0.0.0`
- **THEN** the dashboard is reachable from localhost and from the machine's network or Tailscale IP

### Requirement: Dashboard User Stories
The dashboard SHALL implement controls and panels that map to the documented user stories for quota burn, spend attribution, value-evidence inspection, review-candidate detection, export, and accessibility.

#### Scenario: User story coverage
- **WHEN** a maintainer reviews the OpenSpec design
- **THEN** every visible dashboard control and panel has a corresponding user story mapping

### Requirement: Summary Metrics
The dashboard SHALL show summary metrics for session count, tokens, directional rate-card cost, live quota telemetry, durable-output evidence, and review-candidate evidence for the currently filtered sessions.

#### Scenario: Filtered metric refresh
- **WHEN** the user changes a filter
- **THEN** all summary metric totals update to reflect only matching sessions

### Requirement: Evidence-Safe Metric Semantics
The dashboard SHALL distinguish observed local usage, directional rate-card cost, live quota telemetry, durable-output evidence, and review-candidate evidence.

#### Scenario: Avoid overclaiming estimates and value
- **WHEN** the dashboard renders summary metrics and review panels
- **THEN** current quota is shown as live CodexBar telemetry rather than historical filter allocation
- **AND** cost is labelled as a directional rate-card estimate rather than billing spend
- **AND** durable-output and review-candidate labels avoid claiming that work was objectively valuable or wasted
- **AND** cleanup projection uses de-duplicated sessions across overlapping review-candidate findings

### Requirement: Investigation Filters
The dashboard SHALL support filtering by date preset, text search, client/tool, project, Paperclip company, Paperclip staff, task, model, outcome, review pattern, attribution confidence, and time of day.

#### Scenario: Apply multiple filters
- **WHEN** the user selects a project, staff member, outcome, and overnight time window
- **THEN** charts, metrics, table rows, exports, and evidence selection are constrained to sessions matching all selected filters

### Requirement: Usage Visualizations
The dashboard SHALL visualize usage through an hourly timeline, day/hour heatmap, ranked comparisons, spend flow, review candidates, attribution coverage, and cleanup projection.

#### Scenario: Visualize filtered usage
- **WHEN** the user filters to one client or project
- **THEN** each visualization redraws using only that filtered subset

#### Scenario: Reversible chart filtering
- **WHEN** the user clicks an interactive dashboard item such as a durable-output/review-candidate KPI, flow node, flow band, timeline hour, heatmap cell, review-candidate row, coverage bucket, projection action, or outcome pill
- **THEN** the dashboard applies that item's filter, marks the item active, and preserves the filter in the permalink
- **AND WHEN** the user clicks the active item again
- **THEN** the dashboard clears only that item's filter and returns the affected panel toward its default scope without clearing unrelated filters

### Requirement: Session Table And Evidence Drawer
The dashboard SHALL provide a sortable compact session table and a session evidence drawer showing attribution, token/rate-card cost estimates, outcome, review pattern, edits, tests, command labels, and linked identifiers when available.

#### Scenario: Inspect session
- **WHEN** the user selects a session row
- **THEN** the evidence drawer opens with privacy-safe structured evidence for that session

### Requirement: Export And Permalink
The dashboard SHALL allow exporting filtered sessions and copying a permalink that preserves filter state.

#### Scenario: Export filtered CSV
- **WHEN** the user applies filters and activates CSV export
- **THEN** the exported CSV contains only the filtered sessions and includes client, project, staff, task, model, tokens, rate-card cost, outcome, review pattern, and confidence columns

### Requirement: Accessibility And Responsive Layout
The dashboard SHALL provide keyboard-accessible controls, visible focus states, semantic labels, sufficient dark-mode contrast, a skip link, and responsive layout for narrow screens.

#### Scenario: Keyboard operation
- **WHEN** the user navigates the page with the keyboard
- **THEN** interactive controls, table rows, exports, and the evidence drawer are reachable and labelled

### Requirement: Mockup Validation
The implementation SHALL preserve the core structure of the final imagegen mockup: filter rail, KPI strip, main graph grid, session table, and evidence drawer.

#### Scenario: Compare against mockup
- **WHEN** the implementation is reviewed against `docs/mockups/dashboard-final.png`
- **THEN** the working dashboard contains the same functional regions and required controls, even if exact pixels differ
