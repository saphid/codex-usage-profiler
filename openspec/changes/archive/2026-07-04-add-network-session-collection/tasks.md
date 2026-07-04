## 1. OpenSpec

- [x] 1.1 Write proposal, design, and network collection spec
- [x] 1.2 Validate the OpenSpec change strictly

## 2. Collector

- [x] 2.1 Add a dependency-free collector CLI with default tool globs
- [x] 2.2 Stage files with metadata sidecars and incremental state
- [x] 2.3 Push to local or SSH destinations
- [x] 2.4 Emit local JSONL and optional syslog events

## 3. Central Services

- [x] 3.1 Add report refresh and dashboard service assets
- [x] 3.2 Add collector systemd and launchd service assets
- [x] 3.3 Add high-port LAN proxy asset for rootless `.lan` access

## 4. Tests

- [x] 4.1 Add collector unit tests
- [x] 4.2 Add dashboard syslog/access test coverage
- [x] 4.3 Run unit, E2E, and OpenSpec validation

## 5. Deployment

- [x] 5.1 Deploy central profiler to LXSO1
- [x] 5.2 Install collectors on reachable machines
- [x] 5.3 Expose a `.lan` URL
- [x] 5.4 Verify report refresh, dashboard health, and Grafana-visible logging

## 6. Paperclip Attribution Hardening

- [x] 6.1 Preserve collected `source_path` as first-class session metadata
- [x] 6.2 Add structured Paperclip identifiers to collector sidecars
- [x] 6.3 Add optional Paperclip topology snapshots for central reports
- [x] 6.4 Attribute Paperclip company, project, staff, and task from explicit metadata, source paths, snapshots, and workspace hints
- [x] 6.5 Add regression tests for collected sidecars, prompt preambles, and metadata snapshots
