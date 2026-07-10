## 1. Spec And Fixtures

- [x] 1.1 Add phase-span and learning-card fixtures covering linear, looped, and failed-pivot sessions
- [x] 1.2 Add fixtures for browser/cookie/request-replay sessions and source-specific Claude/Pi shapes
- [x] 1.3 Add redaction fixtures for URLs, cookies, bearer tokens, auth headers, and private paths

## 2. Phase Extraction

- [x] 2.1 Add phase span data models with confidence, evidence, and event references
- [x] 2.2 Implement deterministic event-to-phase rules for requests, research, understanding, implementation, and validation
- [x] 2.3 Detect repeated and interleaved phase spans instead of forcing one phase per session
- [x] 2.4 Extract transition patterns such as late repo-instruction discovery, repeated failed validation, and research-after-implementation

## 3. Candidate Mining

- [x] 3.1 Implement deterministic scanners for repeated mistakes, rediscovered lessons, missing skills, missing helpers, prompt updates, and missing validation
- [x] 3.2 Add browser/auth/request-replay detectors for cookies, HAR/CDP capture, curl/fetch conversion, CSRF/header reuse, and safe request manifests
- [x] 3.3 Add project-memory-gap detectors for repo instructions, launchd/service inventory, LXS01/Pi worker references, and repeated setup discovery
- [ ] 3.4 Improve scoring with recency, token-known ratio, stronger cross-project spread gates, and task-type gates

## 4. Cross-Session Comparison

- [x] 4.1 Build stable privacy-safe session/path hashes and transition counts without retaining raw text by default
- [ ] 4.2 Cluster similar candidates across projects and scopes beyond current deterministic feature buckets
- [x] 4.3 Detect "tried X, eventually did Y" candidates from repeated late-pivot transition patterns
- [x] 4.4 Keep evidence reviewable with affected sessions, source counts, phase counts, and optional redacted snippets

## 5. Learning Cards And Reports

- [x] 5.1 Implement learning-card schema and JSON rendering
- [x] 5.2 Implement Markdown report grouped by global, project, language, infrastructure, service, and harness/tooling scope
- [x] 5.3 Include recommended destination: skill, prompt, AGENTS.md, deterministic helper, docs, ignore/no-action
- [x] 5.4 Include confidence, fixability, why-not-auto-fix, evidence sessions, source counts, phase counts, and privacy-safe snippets

## 6. CLI And Validation

- [x] 6.1 Add `codex-lesson-miner` CLI with `--source`, `--days`, `--paths`, `--format`, and `--include-snippets`
- [x] 6.2 Add tests for phase extraction, candidate scoring, redaction, source parsing, and report output
- [x] 6.3 Run read-only local and LXSO1 copied-data scans and verify no obvious raw secrets appear in default output
- [ ] 6.4 Validate OpenSpec change with `openspec validate add-session-learning-miner --strict`

## 7. Autoresearch

- [x] 7.1 Add a repeatable local autoresearch runner
- [x] 7.2 Document read-only LXSO1 copy and scan workflow
