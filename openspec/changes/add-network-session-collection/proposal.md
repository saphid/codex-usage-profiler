## Why

Codex Usage Profiler is useful on one machine, but Alex's agent sessions are spread across the Mac, LXSO hosts, NurseDroid, and tool-specific homes. A network collector lets the profiler answer "what burned quota overnight?" from one LXSO-hosted dashboard instead of requiring ad hoc rsyncs and local-only scans.

## What Changes

- Add a portable session collector that scans configurable tool globs for Codex, Claude, Pi, T3Chat, Kimi, droid, Cursor, OpenCode, and Paperclip session files.
- Stage changed files with host/tool metadata and push them to a central LXSO collection directory.
- Add central LXSO report refresh and dashboard service templates.
- Add JSONL/syslog/Loki logging for collectors, report refreshes, and dashboard access events so activity appears in Grafana.
- Add deployment docs and service assets for Linux systemd user timers, macOS launchd, and the home `.lan` access path.

## Capabilities

### New Capabilities

- `network-session-collection`: Collect, centralize, profile, serve, and log multi-host AI coding session files.

### Modified Capabilities

None.

## Impact

- Adds a standard-library Python collector CLI and tests.
- Adds optional dashboard syslog and Loki forwarding.
- Adds ops files under `ops/` for systemd, launchd, report refresh, and LAN proxy deployment.
- Reads local user-level session files and copies them to the configured central host; it does not mutate source session stores.
