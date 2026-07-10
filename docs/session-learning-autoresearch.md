# Session Learning Autoresearch

Run deterministic learning scans without exposing raw snippets by default:

```bash
scripts/session-learning-autoresearch.sh
```

The runner writes JSON, Markdown, and `summary.md` into `reports/autoresearch` unless a different output directory is passed as the first argument.

LXSO1 input is optional and read-only. Copy session logs into ignored `reports/` directories first:

```bash
mkdir -p reports/lxso1-pi-sessions reports/lxso1-codex-sessions reports/lxso1-hermes-sessions
rsync -a --include='*/' --include='*.jsonl' --exclude='*' lxso1:/home/saphid/.pi/agent/sessions/ reports/lxso1-pi-sessions/
rsync -a --include='*/' --include='*.jsonl' --exclude='*' lxso1:/home/saphid/.codex/sessions/ reports/lxso1-codex-sessions/
rsync -a --include='*/' --include='*.jsonl' --include='*.json' --exclude='*' lxso1:/home/saphid/.hermes/sessions/ reports/lxso1-hermes-sessions/
```

Quality loop:

1. Scan local and LXSO1 logs.
2. Review top cards by frequency, token impact, source counts, and phase evidence.
3. Promote only high-confidence learnings into skills, prompt updates, project memory, or deterministic helpers.
4. Re-run after changes and compare card frequency and missing-validation rates.

Keep `--include-snippets` off unless doing a targeted private review.
