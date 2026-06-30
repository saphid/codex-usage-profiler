# Critical Review Summary

This document captures the subagent review pass requested before sharing the repo publicly.

## Review Lanes

- Product/value review: focused on whether the profiler helps a developer understand quota burn and repeated low-value agent behavior.
- Dashboard/implementation review: focused on interaction correctness, misleading UI, accessibility, and test coverage.
- Analysis-methodology review: focused on attribution, quota/cost interpretation, outcome evidence, Paperclip mapping, and report semantics.
- Public/GitHub-readiness review: focused on README, sample data, licensing, repo hygiene, and first-run experience.

The reviewers were explicitly asked not to spend time on security hardening, production deployment, auth, or enterprise polish.

## Critical Findings

### 1. Historical Filters Were Shown As Quota Percentage

The dashboard scaled the current CodexBar quota percentage by the filtered share of historical tokens. That mixed current live quota windows with arbitrary local scan periods.

Decision: critical.

Change: the KPI is now `Live Quota Now`, showing the current CodexBar window only. Historical filters use observed token/cost shares, not quota allocation.

### 2. Cost Looked Like Billing Spend

The UI and README used “estimated cost” language that could be read as billing truth.

Decision: critical.

Change: user-facing language now says `Rate-card cost` or `directional replacement-cost estimate`. Fresh estimates no longer assume `$1/credit` when no `dollars_per_credit` is configured.

### 3. Confidence Was Overstated

Dashboard confidence used the strongest available signal, so one high-confidence client or model field could hide unknown task/staff attribution.

Decision: critical.

Change: dashboard confidence now uses the weakest key attribution signal across client, project, staff, and task.

### 4. “Useful” And “Waste” Overclaimed Value

The dashboard implied edits/tests meant “useful,” and waste findings could disappear when a session also had durable output.

Decision: critical.

Change: visible labels now use `Durable Output` and `Review Candidates`. Review candidates can overlap durable-output sessions. README explains that outcome labels are evidence buckets, not judgments.

### 5. Review Driver Math Double-Counted Overlapping Findings

Cleanup projection summed top finding costs even when findings shared the same sessions.

Decision: critical.

Change: waste/review driver rows now compute matched session tokens/cost directly, and cleanup projection uses the de-duplicated union of sessions in the top drivers.

### 6. Unknown Staff/Task Coverage Was Fake

The coverage panel split unknown usage into staff/task using a fixed 65/35 ratio.

Decision: critical.

Change: unknown staff and unknown task percentages are now measured independently from session attribution fields.

### 7. Panel Links Could Stack Click Handlers

Panel links received new listeners on every render, which could toggle filters multiple times.

Decision: critical.

Change: render uses idempotent `onclick` assignment for those links.

### 8. Public Repo Had No Safe First-Run Story

The dashboard default pointed at a private ignored report; README lacked a sample-data happy path; license metadata conflicted; generated/local files could confuse publishing.

Decision: critical.

Change: added `samples/demo-report.json`, README quickstart, README header image, screenshot asset, MIT `LICENSE`, `CONTRIBUTING.md`, package metadata cleanup, and `.gitignore` entries for local harness folders and `node_modules`.

## Important Deferred Improvements

- Add current-window attribution for active 5-hour/weekly quota windows.
- Show parent/subagent trees so one user goal can be inspected across spawned sessions.
- Add manual “valuable?” labels or a sidecar annotation file for reviewed sessions.
- Improve task titles for hash-like request fallbacks.
- Add outcome evidence fields for commits, PRs, passing tests, final status, and user acceptance.
- Add Paperclip stable IDs alongside labels.
- Add per-driver “best next action” hints such as disable watcher, cache health checks, or add task metadata.

## Retest Expectations

The repo should pass:

```bash
PYTHONPATH=src python3 -m unittest discover -q
npm test
openspec validate add-session-dashboard-ui --strict
```
