# network-session-collection Specification

## Purpose
TBD - created by archiving change add-network-session-collection. Update Purpose after archive.
## Requirements
### Requirement: Configurable Multi-Tool Collection
The system SHALL provide a collector that scans configured session-file globs for known AI coding/chat tools and skips missing paths without failing the run.

#### Scenario: Missing tool paths
- **WHEN** a host has no Kimi or T3Chat session directory
- **THEN** the collector completes successfully and logs zero matches for those tools

#### Scenario: Added custom path
- **WHEN** a collector config adds a new glob for a tool
- **THEN** matching files are included in the next collection run

### Requirement: Incremental Central Push
The system SHALL copy changed session files into a central collection directory with source host, tool, and original path metadata.

#### Scenario: Changed file copied
- **WHEN** a matched session file has a new size or modification time
- **THEN** the collector stages the file, writes a metadata sidecar, and pushes it to the configured destination

#### Scenario: Unchanged file skipped
- **WHEN** a matched session file is unchanged from collector state
- **THEN** the collector does not restage that file

#### Scenario: Paperclip source path attribution
- **WHEN** a collected session comes from a Paperclip company, agent, project, or workspace path
- **THEN** the metadata sidecar preserves the original `source_path`
- **AND** includes structured Paperclip identifiers when they can be parsed from the path

### Requirement: Paperclip Metadata Snapshot
The system SHALL optionally collect lightweight Paperclip topology metadata so the central report can map IDs to company, staff, project, and workspace names without direct access to the source machine's Paperclip API.

#### Scenario: Collector snapshots Paperclip topology
- **WHEN** the collector can reach the local Paperclip API or workspace directory
- **THEN** it stages a `paperclip-metadata.json` snapshot containing company IDs/names, issue prefixes, agent IDs/titles, project IDs/names, and workspace hints

#### Scenario: Central report consumes snapshot
- **WHEN** the central profiler scans collected sessions and metadata snapshots
- **THEN** Paperclip sessions are attributed by explicit metadata, original source path, agent/project indexes, and workspace hints in that precedence order

### Requirement: LXSO Dashboard Deployment
The system SHALL include service assets that run report refresh and dashboard serving on an LXSO host using the central collection directory.

#### Scenario: Report refresh
- **WHEN** the report refresh service runs
- **THEN** it scans central collected sessions and writes the latest JSON report atomically

#### Scenario: Dashboard health
- **WHEN** the dashboard service is running
- **THEN** `/healthz` returns `ok`

### Requirement: LAN Access
The system SHALL provide a documented `.lan` access path for the dashboard on the home network.

#### Scenario: Caddy available
- **WHEN** Orange Pi Caddy can be updated
- **THEN** `codex-usage.lan` proxies to the LXSO dashboard service

#### Scenario: Caddy not writable
- **WHEN** Caddy cannot be updated non-interactively
- **THEN** a user-level high-port `.lan` proxy can expose the dashboard without root access

### Requirement: Observable Logs
The system SHALL emit structured logs for collector runs, report refreshes, and dashboard HTTP access to local files and optionally to syslog and Loki.

#### Scenario: Collector log forwarding
- **WHEN** a collector run finishes
- **THEN** a structured event includes host, matched files, staged files, pushed files, skipped files, and errors

#### Scenario: Dashboard access log forwarding
- **WHEN** the dashboard handles an HTTP request
- **THEN** a structured access event can be forwarded to the configured syslog and Loki endpoints

#### Scenario: Grafana log visibility
- **WHEN** LXSO2 Grafana has a Loki datasource
- **THEN** collector, report-refresh, and dashboard events can be queried by `job="codex-usage-profiler"` and `service`

