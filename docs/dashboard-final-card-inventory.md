# Dashboard Final Mockup Card Inventory

Reference image: `docs/mockups/dashboard-final.png`.

## App Chrome

- Skip link: accessibility link at top-left. It jumps keyboard users to main content.
- Top bar: full-width dark navigation strip. It anchors global controls that affect the whole dashboard.
- Brand mark: circular Codex-style icon. It identifies the app.
- App title: "Codex Usage Profiler". It states the current tool.
- Source pill: green "Source: Codex API" badge. It tells the user where usage data came from.
- Live status dot and label: confirms current telemetry is connected.
- Global search: centered search input. It filters sessions, projects, staff, and tasks.
- Date range button: calendar-styled selector. It scopes the whole dashboard by time.
- Compare toggle: switch. It enables comparative mode.
- Export button: action button. It exports filtered data.
- Permalink button: action button. It copies shareable filter state.
- More menu: compact icon button. It reserves secondary actions.
- Close icon: top-right app control in the mockup. It is visual chrome only unless embedded.

## Filter Rail Card

- Card title: "Filters". It defines the left rail.
- Hide control: small icon plus label. It collapses the rail.
- Client / Tool select: dropdown. It filters by harness/app.
- Project select: dropdown. It filters by repository/project.
- Paperclip Company select: dropdown. It filters company attribution.
- Staff select: dropdown. It filters Paperclip staff attribution.
- Task select: dropdown. It filters inferred or Paperclip task.
- Model select: dropdown. It filters model usage.
- Outcome select: dropdown. It filters durable-output/neutral/review/unknown outcomes.
- Review Pattern select: dropdown. It filters known review-candidate signatures.
- Confidence slider: range input with 0% and 100% endpoints. It filters attribution confidence.
- Time of Day segmented control: All, Day, Night. It isolates overnight burn without custom typing.
- Active filters title/count: tells user how many constraints are applied.
- Clear all link: removes active filters.
- Active filter chips: date/outcome/confidence chips with close buttons. They show current scope.
- Reset filters button: clears all filters.
- Version label: bottom-left product version.
- Guide link: bottom-right documentation/help entry.

## KPI Strip Card

- Card container: one horizontal strip with vertical dividers. It summarizes the selected scope.
- Sessions metric: count plus prior-period delta. It answers "how many sessions?"
- Tokens metric: token total plus delta. It answers "how much quota activity?"
- Rate-card Cost metric: directional rate-card cost plus delta. It answers "rough spend?"
- Live Quota Now metric: current CodexBar quota percentage when available. It answers "what is my current subscription window state?"
- Durable Output metric: cost/tokens with durable-output evidence. It answers "how much had observable output signals?"
- Review Candidates metric: cost/tokens matching review patterns. It answers "how much deserves inspection?"
- Info icons: small circular icons beside labels. They indicate explanatory tooltip affordances.

## Spend Flow Card

- Title: "Spend Flow". It identifies the flow visualization.
- Info icon: explains how flow is computed.
- Path label: "Client -> Project -> Staff -> Outcome". It states the attribution chain.
- View-as segmented control: Spend and Cost %. It changes the metric displayed.
- Four columns: Client, Project, Staff, Outcome. They show where spend moves.
- Flow nodes: rectangular labelled bars with value and percent. They rank each column.
- Connecting bands: translucent paths between columns. They show relationship/proportion.
- Outcome blocks: Durable Output, Neutral, Review. They summarize final value state.

## Usage Over Time Card

- Title: "Usage Over Time (Hourly)". It defines the chart granularity.
- Info icon: tooltip affordance.
- Legend: Durable Output, Neutral, Review, Unknown. It maps colors.
- Metric dropdown: "Tokens". It changes plotted measure.
- More menu: secondary chart options.
- Stacked hourly bars: vertical bars colored by outcome. They show when usage happened.
- Y-axis labels: 0M through 10M. They show scale.
- X-axis date labels: date and midnight markers. They show time placement.
- Overnight overlay: dashed highlighted window labelled "Overnight (6p-6a)". It makes overnight burn visible.
- Mini brush: compressed timeline with draggable handles. It zooms/selects a time range.
- Brush summary: text showing selected time window.

## Usage Heatmap Card

- Title: "Usage Heatmap (Tokens)". It identifies day/hour aggregation.
- Info icon: tooltip affordance.
- Day labels: Mon through Sun. They show rows.
- Hour labels: 12a, 3a, 6a, 9a, 12p, 3p, 6p, 9p, 12a. They show columns.
- Heat cells: blue intensity squares. They show token density by day/hour.
- Lower/higher legend: color scale. It explains intensity.

## Top Review Candidates Card

- Title: "Top Review Candidates". It identifies ranked review candidates.
- Info icon: tooltip affordance.
- Table header: Pattern, Sessions, Candidate Cost. It defines row values.
- Rows: repeated commands, broad prompts, wrong approach, context bloat, unnecessary exploration. They rank review causes.
- Red spend bars: visual magnitude. They make cost comparison fast.
- View all review candidates link: opens full pattern list.

## Attribution Coverage Card

- Title: "Attribution Coverage". It identifies attribution health.
- Info icon: tooltip affordance.
- Donut chart: fully attributed center value. It shows coverage share.
- Legend: fully attributed, partial, unknown staff, unknown task. It exposes gaps.
- Percent values: exact bucket shares.
- View unknown buckets link: drills into missing attribution.

## Cleanup Projection Card

- Title: "Cleanup Projection". It estimates savings.
- Info icon: tooltip affordance.
- Reduction selector: percent dropdown. It controls hypothetical improvement.
- Projected candidate cost saved: large red dollar/day value. It quantifies opportunity.
- Total-cost share: percent of current cost. It explains relative impact.
- New candidate cost row: post-cleanup estimate.
- Remaining candidate percent row: post-cleanup share.
- Calculation link: opens explanation.

## Sessions Table Card

- Title and count: "Sessions (1,248)". It states current row set.
- Info icon: tooltip affordance.
- Column chooser button: controls visible columns.
- Density dropdown: compact/comfortable display.
- Pagination range: "1-50 of 1,248". It shows current page.
- Pagination controls: previous, page numbers, next. They navigate rows.
- Selection checkbox column: selects sessions for bulk comparison.
- Sortable headers: Start Time, Session ID, Client/Tool, Project, Staff, Task, Model, Tokens, Rate-card Cost, Outcome, Review Pattern, Confidence.
- Rows: compact session summaries.
- Outcome pills: red/green/gray badges. They communicate value state.
- Confidence dots/percent: show trust level.
- Selected row: blue highlight. It drives the session details drawer.

## Session Details Drawer Card

- Header icon and title: "Session Details". It identifies selected row details.
- Close button: hides drawer.
- Session metadata rows: ID, start time, duration, client/tool, project, staff, task, model. They identify the session.
- Copy/open affordances: small buttons near IDs/links. They support investigation.
- Token/cost strip: token total and rate-card cost. It summarizes impact.
- Outcome/confidence row: durable-output/review badge and confidence percent/dot. It explains evidence classification.
- Review pattern row: shows matched pattern or none.
- Tabs: Evidence, Commands, Linked. They switch evidence categories.
- Evidence action rows: Edits, Tests, Commits, Pull Requests. They show durable-output signals.
- Privacy-safe evidence box: redacted textual evidence. It avoids raw prompt leakage.
- Linked sessions card: parent/child relationships. It helps inspect repeated workflows.
- Internal scrollbar: drawer scrolls independently.

## Footer Status

- Freshness indicator: green check and "Data fresh as of..." text. It tells the user whether data is current.
- Refresh link: reloads data.
- Notification/settings icons: small secondary controls.
