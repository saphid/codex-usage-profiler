# Dashboard Final Interaction Contract

This contract turns every visible dashboard element in `docs/mockups/dashboard-final.png` into behavior the working dashboard must provide.

## Global App Chrome

- Skip link: keyboard link. On focus and Enter, moves focus to the main dashboard.
- Brand icon/title: static identity. Provides accessible app name.
- Source badge: status pill. On click or info activation, opens source details with report path, CodexBar availability, telemetry confidence, and freshness.
- Live status: status indicator. Announces live quota telemetry availability and current quota percentage when known.
- Search field: text input. Filters sessions by session ID, project, staff, task, model, path, command labels, and attribution evidence. Updates all cards, table, drawer, export, and permalink.
- Date range selector: select/dropdown. Changes the time scope. Updates all dashboard metrics and adds/removes an active date chip.
- Compare toggle: switch. Enables comparative annotations against the prior equivalent window when data is available; otherwise shows why comparison is unavailable.
- Export button: button. Downloads filtered session CSV using current filters, sort, and visible data model.
- Permalink button: button. Copies URL query string preserving filters, sort, selected session, brush range, table page, visible columns, and selected drawer tab.
- More button: menu button. Opens secondary actions such as raw JSON report, refresh, and mockup/spec links.

## Filter Rail

- Hide button: button. Collapses or restores the filter rail; layout expands main dashboard without losing filters.
- Client/tool selector: select. Filters to selected client; updates flow graph selection and active chip.
- Project selector: select. Filters to selected project; updates flow graph and active chip.
- Paperclip company selector: select. Filters to selected Paperclip company; affects table and drawer attribution.
- Staff selector: select. Filters to selected Paperclip staff member; updates flow graph staff column and active chip.
- Task selector: select. Filters to selected task; updates table, drawer, and active chip.
- Model selector: select. Filters by model.
- Outcome selector: select. Filters by value state.
- Review pattern selector: select. Filters by review-candidate signature.
- Confidence slider: range input. Filters sessions whose attribution confidence is lower than the slider. Updates visible value, active chip, and coverage panel.
- Time of day segmented control: buttons. All clears hour filter; Day sets 6a-6p; Night sets 6p-6a. Updates time chart, heatmap, table, and active chip.
- Active filter chips: buttons. Each chip displays one filter and has a remove action. Removing a chip clears only that filter.
- Clear all link and Reset filters button: buttons. Reset all filters, brush selection, selected columns, and page.
- Guide link: link. Opens documentation/spec for the dashboard.

## KPI Strip

- Sessions KPI: tile. Shows filtered sessions and observed-share delta. Info button explains session inclusion.
- Tokens KPI: tile. Shows filtered token total and raw token count. Info button explains input/cached/output token handling.
- Rate-card cost KPI: tile. Shows directional replacement-cost estimate. Info button explains cost-confidence tier and CodexBar local-vs-cache ratios.
- Live quota KPI: tile. Shows current CodexBar quota telemetry when available. It does not allocate historical filtered sessions to quota windows.
- Durable-output KPI: tile. Shows cost/tokens with durable output signals. Clicking filters to durable-output sessions; clicking while active clears that filter.
- Review-candidates KPI: tile. Shows cost/tokens flagged for inspection. Clicking filters to review signals; clicking while active clears review-only.

## Spend Flow Panel

- Graph type: Sankey/alluvial flow diagram. It shows proportional spend moving from Client -> Project -> Staff -> Outcome.
- View-as control: select/segmented control. Changes metric between spend/cost share/tokens. Nodes and link widths recalculate.
- Flow nodes: buttons. Each node displays label, metric value, and share. Hover/focus highlights connected links. Click filters dashboard to that node's dimension/value; clicking the active node clears that node filter.
- Flow links/bands: clickable SVG paths. Width represents token/cost volume. Color indicates target outcome where possible. Hover/focus highlights source and target nodes. Click selects the sessions in that band; clicking the active band clears the band selection.
- Other/unknown buckets: nodes. Group low-volume or unattributed values. Clicking filters to those exact sessions while keeping the grouped node visible as the active reset target.
- Info button: opens explanation of how sessions are grouped, how values are aggregated, and what "unknown" means.

## Usage Over Time Panel

- Stacked hourly bars: bars. Show filtered usage by hour and outcome. Hover/focus shows timestamp, tokens, cost, and outcome split. Click narrows the brush to that hour; clicking the active hour clears the brush.
- Legend: interactive toggles. Turning a legend item off hides that outcome from the chart while preserving total filters.
- Metric dropdown: control. Switches chart between tokens and estimated cost.
- More menu: button. Opens chart actions such as reset brush and export chart data.
- Overnight overlay: highlighted region. Clicking applies Night time-of-day filter.
- Mini brush: interactive range selector. Drag center to move window; drag handles to resize. Brush updates selected absolute time range, main chart highlight, brush summary, KPIs, lower cards, sessions table, drawer, active chip, export, and permalink.
- Brush summary text: live text. Shows currently selected start/end and session count in the brush range.
- Info button: explains chart buckets, local timezone, outcome colors, and brush behavior.

## Usage Heatmap Panel

- Heat cells: buttons. Each cell represents day-of-week/hour usage. Hover/focus shows value. Click filters to that day/hour bucket; clicking the active cell clears the day/hour filter.
- Lower/higher legend: static scale plus info. Explains intensity.
- Info button: explains aggregation and timezone.

## Top Review Candidates Panel

- Rows: buttons. Each row is a review pattern with sessions and directional cost. Click filters to that pattern and updates session table; clicking the active row clears the review-pattern filter.
- Red bars: magnitude. Width encodes candidate cost.
- View all review candidates link: opens/filter table to all review candidates.
- Info button: explains review detection confidence, overlap, and examples.

## Attribution Coverage Panel

- Donut chart: interactive chart. Clicking a segment filters to fully attributed, partial, unknown staff, or unknown task sessions; clicking the active segment clears coverage filtering.
- Legend rows: buttons mirroring donut segments. Clicking an active row clears that coverage bucket.
- View unknown buckets link: toggles unknown attribution filtering.
- Info button: explains attribution confidence and bucket definitions.

## Cleanup Projection Panel

- Reduction selector: select. Recalculates projected savings if de-duplicated top review-candidate sessions are reduced by chosen percent.
- Savings metric: large value. Clicking filters table to the sessions contributing to the projection; clicking while active clears the projection filter.
- Remaining candidate cost / percent rows: derived outputs.
- Calculation link: opens details explaining formula and assumptions.
- Info button: same as calculation link.

## Sessions Table

- Column chooser: button. Opens checkbox menu; toggles visible columns and persists to permalink.
- Density selector: select. Changes row padding without changing data.
- Pagination controls: buttons. Navigate pages; page range updates.
- Header buttons: sortable controls. Toggle ascending/descending and persist sort.
- Row checkbox: selects row for bulk comparison/export.
- Row click/keyboard Enter: selects session, highlights row, and updates Session Details drawer.
- Outcome pill: button-like badge. Click filters by outcome; clicking the active pill clears that outcome filter.
- Confidence indicator: info affordance. Shows attribution evidence/confidence details.

## Session Details Drawer

- Close button: button. Collapses drawer; selected session remains in table.
- Session metadata rows: copyable values where appropriate. IDs/path have copy affordances.
- Impact strip: tokens and rate-card cost for selected session.
- Outcome/confidence/review-pattern boxes: clicking filters or opens explanation.
- Tabs: Evidence, Commands, Linked. Switch visible drawer content without changing selected session.
- Evidence action rows: Edits, Tests, Commits, PRs. Click expands/collapses details or filters to sessions with the same durable-output signal.
- Privacy-safe evidence box: redacted evidence. Copy button copies only safe text.
- Linked sessions: parent/child/review-finding relationships. Clicking selects linked session if present.

## Footer

- Freshness indicator: status text. Shows last report load time.
- Refresh button: reloads report and preserves filters where possible.
- Notification/settings buttons: menu controls. Open relevant settings or explain unimplemented local-only behavior.

## Accessibility Baseline

- Every visible control has a keyboard path, `aria-label` or readable text, focus ring, and tooltip/help text.
- Decorative marks are hidden from assistive tech.
- Info buttons are real buttons, not inert letters.
- Charts expose equivalent text through titles, labels, and table/filter effects.
