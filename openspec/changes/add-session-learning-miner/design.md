## Context

The current profiler normalizes sessions and finds usage/waste signals, but those signals are session-level. Alex's proposed phase model is useful, but too tidy if treated as a single ordered funnel. Real agent sessions loop: research can happen after failed implementation, proof can reveal misunderstood requirements, and a final solution can differ from the first strategy.

The miner should therefore model phase spans and transitions, not a single canonical narrative. The core product question is: "What should Alex teach the agent, skill system, prompt, or deterministic tooling so future sessions avoid repeated rediscovery?"

## Goals / Non-Goals

**Goals:**

- Identify recurring problems and learnings across local sessions.
- Explain agent behavior as phase spans with evidence and confidence.
- Detect strategy drift such as "agent tried browser UI, then eventually needed request capture" or "agent researched broadly, then discovered repo-specific instructions late".
- Compare similar spans and transitions across sessions.
- Produce reviewable learning cards grouped by global, project, language, infrastructure, service, and harness/tooling scope.
- Support Codex, Claude Code, Pi, and generic JSON/JSONL session sources.
- Provide a repeatable autoresearch command for local and copied LXSO1 session data.
- Use deterministic scanning first; use local LLM summarization only after candidate narrowing and redaction.

**Non-Goals:**

- Do not automatically edit skills, prompts, AGENTS.md, helper tools, or logs.
- Do not judge "model intelligence" directly; infer observable process patterns only.
- Do not require perfect phase classification.
- Do not force every event into exactly one phase.
- Do not expose raw private logs by default.

## Decisions

1. Model sessions as phase spans, not a linear lifecycle.

   Rationale: Alex's five phases are right as analytical lenses, but wrong if used as strict sequence. A session can contain multiple investigation and implementation spans. A span has `phase`, `start_event`, `end_event`, `evidence`, `confidence`, and optional `hypothesis`.

   Alternative rejected: one label per session. Too coarse to explain drift or repeated rediscovery.

2. Separate deterministic evidence extraction from interpretive learning synthesis.

   Rationale: Deterministic scanners catch repeatable facts: commands, tool calls, errors, patches, tests, phase markers, token spikes, and repeated text fingerprints. Interpretation can then summarize a small candidate bundle.

   Alternative rejected: send whole logs to an LLM. Too expensive, private, and unstable.

3. Compare transitions as first-class objects.

   Rationale: The most useful lesson is often not "research happened"; it is "research path A failed, then path B worked". Store transitions like `investigation -> implementation -> validation_failed -> investigation` and repeated late pivots.

   Alternative rejected: cluster only final findings. Misses process mistakes.

4. Emit learning cards, not automatic fixes.

   Rationale: Alex explicitly wants the first step to identify problems/learnings. A card can later become a skill, prompt update, deterministic helper, project note, or no action.

   Alternative rejected: auto-generate skills/prompts immediately. Too easy to encode noisy conclusions.

5. Treat uncertainty honestly.

   Rationale: Some issues are model limitations or one-off context gaps. Cards need `confidence`, `fixability`, `scope`, and `recommended_destination`.

   Alternative rejected: rank everything as a bug to fix. Creates busywork.

## Phase Model

- `request_idea`: user asks, delegation input, thread title, project/task framing.
- `investigation_research_discovery`: file reads, search, schema inspection, browser/network inspection, external docs, exploratory commands.
- `understanding`: agent states a diagnosis, plan, discovered invariant, risk, or "main thing".
- `implementation`: patches, file creation, command execution that changes state, generated artifacts.
- `proof_validation`: tests, lint, smoke checks, screenshots, verification commands, final status/known gaps.

Spans may overlap or repeat. Events can have multiple weak labels when evidence is ambiguous.

## Learning Card Schema

Each card should include:

- `title`
- `summary`
- `scope`: global, project, language, infrastructure, service, harness-tooling
- `problem_type`: repeated mistake, rediscovered lesson, missing skill, missing helper, prompt update, model limitation, project-memory gap
- `phase_pattern`: phase spans and transition pattern behind the card
- `evidence_sessions`
- `evidence_snippets`: bounded and redacted by default
- `frequency`, `token_impact`, `recency`
- `confidence`
- `fixability`
- `recommended_destination`: skill, prompt, AGENTS.md, deterministic helper, docs, ignore/no-action
- `why_not_auto_fix`
- `source_counts`
- `phase_counts`

## Risks / Trade-offs

- Phase classification may be noisy -> store confidence and allow multiple labels.
- Repeated terms can be false positives -> require cross-session or token-impact thresholds before card creation.
- Some failures are model limitations -> label `model limitation` rather than inventing useless process fixes.
- Privacy risk from log text -> default to hashes, labels, redacted snippets, and explicit opt-in for raw evidence.
- LLM summaries can hallucinate lessons -> every card must cite deterministic evidence and can be generated from candidate bundles only.
- Cross-source token accounting is inconsistent -> include source counts and treat token impact as directional unless token-known ratio is added.

## Migration Plan

Add the miner alongside the existing profiler. Default output is JSON/Markdown under `reports/`. Existing profiler commands and dashboard behavior remain unchanged. LXSO1 data is copied into ignored local `reports/` directories before scanning. Rollback is deleting the new modules, runner, docs, and CLI entrypoint; no external state is modified.

## Open Questions

- Should phase spans be persisted in a local cache for faster repeated analysis, or recomputed for MVP?
- What minimum recurrence threshold should create a card: 2 sessions with high similarity, 3 sessions, or token-impact based?
- Should the first dashboard version show phase timelines, or only learning cards?
