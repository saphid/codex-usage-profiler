## Why

The profiler already produces useful JSON/text, but the user needs a fast visual way to see where observed Codex usage concentrates by tool, project, task, staff/company, session, time, rate-card cost, live quota telemetry, and outcome evidence. The target is not perfect billing. The target is an operational dashboard that quickly exposes review candidates, repeated low-value patterns, and cleanup opportunities.

The UI must be compact, dark-mode first, accessible, and functional enough that Alex can inspect real overnight token burn from a Tailscale-reachable local page.

## What Changes

- Add a local dashboard server for existing profiler JSON reports.
- Add a compact dark dashboard with filters, KPI totals, live quota/rate-card cost context, hourly timeline, heatmap, ranked comparisons, spend flow, review candidates, attribution coverage, cleanup projection, session table, and evidence drawer.
- Add imagegen-derived mockup artifacts and use the final mockup as the implementation target.
- Add export and permalink controls for filtered investigations.
- Add integration tests for the served UI/API and dashboard filtering/export logic.

## Capabilities

### New Capabilities

- `dashboard-ui`: Browse, filter, visualize, export, and inspect Codex usage reports in a local accessible web dashboard.

## User Stories

- As a heavy Codex user, I want date and overnight filters so I can isolate sudden quota burn.
- As a subscription owner, I want observed token totals, directional rate-card cost, and live quota telemetry so I can see relative impact without mistaking estimates for billing.
- As a project owner, I want breakdowns by client/tool, project, Paperclip company, Paperclip staff, task, model, outcome, and review pattern so I can find the source of spend.
- As an operator, I want charts for time, heatmap, rankings, spend flow, review candidates, coverage, and cleanup projection so I can understand the system at a glance.
- As an investigator, I want a sortable session table and evidence drawer so I can inspect evidence and decide what deserves follow-up.
- As Alex, I want Tailscale-friendly local serving and accessible controls so I can use the dashboard from my own machines.

## Impact

- Adds static frontend assets packaged with the Python project.
- Adds a small Python HTTP server entrypoint.
- Keeps existing CLI profiling behavior unchanged.
- Uses existing report JSON shape; no new database or external service is required.
