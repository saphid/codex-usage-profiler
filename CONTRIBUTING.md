# Contributing

Codex Usage Profiler is intentionally small and local-first. Useful changes should help a developer answer one of these questions faster:

- Which tool, project, task, or session consumed usage?
- Which sessions deserve inspection?
- Which repeated patterns can be reduced or removed?
- Which attribution gaps prevent confident decisions?

## Good Contributions

- Add parsers for real Codex log variants without exposing prompt/response bodies by default.
- Improve attribution confidence with observable evidence.
- Improve review-candidate detection with de-duplicated session sets and clear action hints.
- Add dashboard interactions that make an investigation faster.
- Add fixtures and tests for every new inference.

## Guardrails

- Do not frame estimates as official billing.
- Do not frame durable-output evidence as proof that work was valuable.
- Do not add sample data from private logs.
- Keep the default path read-only.

## Tests

```bash
PYTHONPATH=src python3 -m unittest discover -q
npm test
```
