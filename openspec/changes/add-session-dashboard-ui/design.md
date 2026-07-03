## Context

The profiler can ingest Codex logs, CodexBar telemetry, Paperclip metadata, rate-card cost context, outcome markers, and review-candidate findings. Current output is text or JSON, which is good for automation but weak for quick investigation.

Imagegen exploration produced five compact dark dashboard concepts plus a final synthesized mockup. The final target is stored at `docs/mockups/dashboard-final.png`, with source variants at `docs/mockups/dashboard-v1.png` through `dashboard-v5.png`.

## Goals / Non-Goals

**Goals:**

- Serve a local dashboard from a profiler JSON report.
- Show high-density visual insight without hiding the session evidence.
- Map every visible control or panel to a user story.
- Support filtering by date/time, client/tool, project, Paperclip company/staff/task, model, outcome, review pattern, confidence, and text search.
- Show directional rate-card cost and live quota telemetry from available report data.
- Make review/value-evidence inspection practical through session rows and an evidence drawer.
- Work over localhost and a Tailscale IP when bound to `0.0.0.0`.
- Provide unit/integration tests for UI data behavior and HTTP serving.

**Non-Goals:**

- Exact billing reconciliation.
- Cloud-hosted multi-user analytics.
- Raw prompt display by default.
- Editing Codex logs or Paperclip data.

## User Story To UI Mapping

| User story | UI elements |
| --- | --- |
| Isolate sudden quota burn | date preset, overnight preset, hourly timeline, brush summary, day/hour heatmap |
| Understand usage impact | KPI strip for sessions, tokens, rate-card cost, live quota, durable output, review candidates |
| Find source of spend | filter rail, ranked bars, spend flow, active filter chips |
| Compare tools/projects/staff | client/project/staff rankings and spend flow columns |
| Detect low-value repeated work | review-pattern filter, top review candidates, cleanup projection |
| Inspect value by session | sortable session table, selected row, right evidence drawer |
| Identify attribution gaps | attribution coverage panel and unknown buckets |
| Share/export investigations | CSV export, JSON export/permalink state |
| Use accessibly | skip link, labels, keyboard focus, semantic table, responsive layout |

## Decisions

### Static frontend with small Python server

Use packaged HTML/CSS/JS served by `http.server`. This avoids a build system, external dependencies, and fragile install steps. The server exposes `/api/report` from a selected JSON report.

Alternative: Vite/React. Rejected because it adds dependency and build surface for a local operational tool.

### Pure JavaScript data functions

Filtering, sorting, summarizing, CSV export, quota estimates, and chart data generation live in pure functions exposed as `CUPDashboard`. Integration tests can call them directly in Node while the browser uses the same code.

Alternative: test only rendered HTML. Rejected because it would miss the business logic behind the graphs.

### DOM/CSS/SVG charts

Use CSS bars and inline SVG for timeline, heatmap, rankings, coverage, and spend flow. This keeps the dashboard portable and fast while matching the final mockup closely enough for operational use.

Alternative: Chart.js/D3. Rejected for dependency weight.

### Card-local resets and responsive relayout

Each filterable visualization exposes a local reset button in the panel header. Active chart items still toggle off directly, but reset buttons make recovery obvious when the active item is clipped, scrolled away, or visually subtle. The Sankey/alluvial flow re-renders on viewport changes because its SVG links and DOM nodes are positioned from the container width.

### Privacy-safe evidence drawer

Show structured evidence such as edits, tests, commits, PRs, commands, token counts, attribution confidence, session IDs, and local paths. Do not show raw prompts unless a report explicitly includes snippets.

Alternative: always show raw prompt context. Rejected because logs can contain secrets or personal data.

## Risks / Trade-offs

- Cost/quota estimates can be approximate -> label them as estimates and preserve source/telemetry status.
- Large reports can make client-side filtering heavy -> keep rows compact and render a capped visible table with aggregate totals over all filtered sessions.
- Staff/task attribution can be incomplete -> show coverage and unknown buckets instead of hiding uncertainty.
- Browser visual fidelity can drift from the mockup -> store mockups and add stable test IDs for future screenshot testing.

## Migration Plan

1. Keep existing CLI report generation unchanged.
2. Add dashboard package data and server entrypoint.
3. Serve any existing JSON report with `codex-usage-dashboard --report <path>`.
4. Rollback by removing the dashboard script/static assets; profiling reports remain compatible.

## Open Questions

- Whether future versions should persist manual value-review labels back to a local sidecar file.
- Whether to add a dedicated report schema version once more dashboard-specific fields are needed.
