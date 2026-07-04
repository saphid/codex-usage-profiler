## Context

The profiler currently scans local paths. Alex's real usage spans several machines and harnesses: this Mac, LXSO1, LXSO2, LXSO3, NurseDroid, Codex, Claude, Pi, T3Chat, Kimi, droid, Cursor, OpenCode, and Paperclip. LXSO1 is the best central app host because it is always on and already runs agent services. `grafana.lan` and Loki now live on LXSO2, while Orange Pi still owns `.lan` DNS/Caddy and the syslog/Postgres observability path.

## Goals / Non-Goals

**Goals:**

- Run Codex Usage Profiler continuously on an LXSO machine.
- Collect session files from all reachable hosts without requiring tool-specific daemons.
- Make new tools easy to add with config globs.
- Preserve source host/tool/path metadata.
- Refresh the central report on a timer and serve the dashboard over LAN/Tailscale.
- Emit collector, report-refresh, and dashboard events to local JSONL logs, Orange Pi syslog/Postgres, and LXSO2 Loki for Grafana.

**Non-Goals:**

- Exact billing reconstruction.
- Parsing every proprietary chat database format in the collector.
- Replacing existing Grafana/Loki infrastructure.
- Copying auth files, caches, model downloads, browser profiles, or arbitrary app data.

## Decisions

1. Use push collectors over SSH/rsync.

   Rationale: every machine can run a user-level timer and push changed files to LXSO1. No central credentials or inbound collector API are needed.

2. Use config-driven globs with conservative defaults.

   Rationale: Codex and Claude have known JSONL locations, but T3Chat, Kimi, and droid session paths can vary by install. Defaults catch common session directories; per-host config can add or remove paths.

3. Stage files under `collector/tool/hash/basename` plus a metadata sidecar.

   Rationale: this avoids path collisions, keeps source metadata, and lets the profiler infer client/host from central paths while source files stay untouched.

3a. Snapshot lightweight Paperclip topology.

   Rationale: central LXSO reports do not have direct access to the Mac's Paperclip API or local company/agent instruction tree. The collector can safely stage a small `paperclip-metadata.json` snapshot with company, agent, project, and workspace labels. This avoids opaque UUID-only reports while keeping raw prompts and source data out of the snapshot.

4. Keep the collector dependency-free.

   Rationale: LXSO, NurseDroid, Orange Pi, and macOS all have Python 3. A standard-library collector is easier to install than a daemon with a dependency tree.

5. Log to JSONL, syslog, and Loki.

   Rationale: JSONL gives local troubleshooting. Syslog matches the existing Orange Pi ingestion path. Direct Loki push makes the same events visible in canonical `grafana.lan` without requiring journald scraping on every host.

6. Prefer LXSO1 for the dashboard; use a high-port `.lan` proxy if Caddy cannot be modified.

   Rationale: Orange Pi Caddy is root-owned. When passwordless sudo is unavailable, `codex-usage.lan:8775` can still work through wildcard `.lan` DNS plus a user-level proxy.

## Risks / Trade-offs

- Tool paths can be wrong or incomplete -> keep config visible and log zero-match tools.
- First collection can copy many files -> skip oversized files and copy only mtime/size changes after the first run.
- Non-Codex logs can lack token fields -> central report labels token-known coverage rather than inventing numbers.
- Remote forwarding can fail independently -> local JSONL logs remain authoritative and forwarding failures do not fail collection.
- `.lan` without a port needs root Caddy changes -> provide a working high-port path and document the root-owned route.

## Migration Plan

1. Add collector, tests, and ops assets.
2. Deploy the repo to LXSO1 and install dashboard/report systemd user units.
3. Install collector configs/timers on this Mac, LXSO1, LXSO2, LXSO3, and NurseDroid.
4. Start a user-level Orange Pi LAN proxy if Caddy cannot be patched.
5. Run collectors once, refresh the report, check dashboard health, and query Loki/Grafana labels.
6. Roll back by disabling the user timers/services and deleting the central collection directory.

## Open Questions

- Whether to add direct parsers for T3Chat/Kimi/droid browser storage formats after real files are observed.
- Whether LXSO2 Loki should later scrape host journald directly in addition to direct push events.
