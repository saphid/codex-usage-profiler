## Why

The existing profiler shows where Codex usage went, but it does not explain what the agent was trying to do, where it changed course, or which lessons should be taught once instead of relearned across sessions. Alex needs a read-only learning miner that identifies recurring problems and learnings before any automatic skill, prompt, or helper-tool changes are attempted.

## What Changes

- Add a session learning miner that decomposes sessions into evidence-backed work phase spans: request/idea, investigation/research/discovery, understanding, implementation, and proof/validation.
- Support Codex, Claude Code, Pi, and generic JSON/JSONL session sources through source-aware adapters.
- Add deterministic scanners for repeated failure patterns, rediscovered lessons, missing skills, missing deterministic helpers, prompt-update candidates, and cross-session workflow drift.
- Add cross-session comparison over phase spans and learning cards, so the tool can detect "tried X, eventually did Y" patterns without assuming a session is linear.
- Add reviewable learning-card outputs with scope, evidence, source counts, phase counts, confidence, likely fix type, and privacy-safe citations.
- Add an autoresearch runner that refreshes local/LXSO1 reports from ignored local copies of session data.
- Keep the first release focused on identifying problems and learnings. Applying fixes to skills, prompts, or helper tools is explicitly deferred.
- Preserve the current read-only privacy posture: no log mutation, no raw prompt/response output by default, and no network requirement.

## Capabilities

### New Capabilities

- `session-learning-mining`: Parse normalized sessions into phase spans, identify recurring lessons/problems, compare similar spans across sessions, and emit reviewable learning cards.

### Modified Capabilities

- `outcome-value-analysis`: Extend existing outcome evidence from whole-session buckets into phase-aware evidence and learning-oriented review candidates.

## Impact

- Adds a new CLI/report path, `codex-lesson-miner`/`clm`, reusing existing JSONL ingestion where possible plus Claude/Pi/generic parsing, attribution, token estimates, and privacy redaction.
- Adds new normalized data structures for phase spans, transitions, learning candidates, clusters, and learning cards.
- Adds OpenSpec coverage and fixtures for session narratives, non-linear phase interleaving, repeated browser/auth request replay lessons, and deterministic helper candidates.
- No changes to log files, Codex state, skills, prompts, or helper tools in this change.
