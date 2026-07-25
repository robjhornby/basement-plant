## Agent skills

### Issue tracker

Issues and PRDs are tracked as local markdown under `.scratch/<feature-slug>/`; external PRs are not a triage surface. See `docs/agents/issue-tracker.md`.

### Triage labels

The repo uses the default five-label triage vocabulary. See `docs/agents/triage-labels.md`.

### Domain docs

This repo uses the single-context domain layout. See `docs/agents/domain.md`.

### Python

Use `uv run` for Python commands and `uv add` / `uv remove` to manage dependencies.

### Project record

Observations, decisions, and landed work go in `LOG.md`, one line each: `- <date> (<who>) <thread> <saw|chose|did>: <what> [link]`. Append only, never edit. `STATUS.md` holds where things stand now.
