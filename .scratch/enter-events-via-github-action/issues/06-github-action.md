# 06 — GitHub Action to log events + workflow_run rebuild trigger

Status: open
Type: task
Blocked by: 03, 05
Parent PRD: ../PRD.md

## Goal

Give the owner a `workflow_dispatch` Action to log a new event (create only),
store it in R2, and trigger the site rebuild natively.

## `log-event` CLI subcommand (repeated use → CLI)

Add `basement log-event`:
- args: `--effective-at "YYYY-MM-DD HH:mm:ss"` (UK local, seconds required),
  `--event-type <slug>`, `--notes <text>` (optional; required for `custom`).
- builds + validates an `EventRecord` (`operation: create`) via ticket 03,
  populating `source` from GHA env: `repository`←`GITHUB_REPOSITORY`,
  `workflow`←`GITHUB_WORKFLOW`, `run_id`←`GITHUB_RUN_ID`, `git_sha`←`GITHUB_SHA`.
- writes the JSON to a local file and **prints the destination object key**.

## `.github/workflows/log-event.yml`

- `on: workflow_dispatch` with inputs:
  - `effective_at` — string, required, placeholder `YYYY-MM-DD HH:mm:ss`.
  - `event_type` — `type: choice`, options: `dehumidifier tank full`,
    `dehumidifier tank emptied`, `custom`. (Workflow maps display → slug;
    `dehumidifier installed` intentionally excluded — one-off, already migrated.)
  - `notes` — string, optional, default `""`.
- Steps: checkout → setup-uv → `uv run basement log-event …` (capture the printed
  key) → `aws s3 cp <file> "s3://$R2_BUCKET/<key>"` using the existing R2 env/creds
  pattern (`AWS_*`, `--endpoint-url "$R2_ENDPOINT_URL"`,
  `AWS_REQUEST_CHECKSUM_CALCULATION=when_required`, etc.).
- **No** `actions: write`, no `GH_TOKEN`, no `gh workflow run` — the rebuild is
  triggered by `workflow_run` below.

## `basement-site.yml` — subscribe via `workflow_run`

```yaml
on:
  schedule:
    - cron: "30 2 * * *"
  workflow_dispatch:
  workflow_run:
    workflows: ["Log basement event"]   # == name: in log-event.yml
    types: [completed]
```

Gate the build job on success so a failed event-write doesn't rebuild:

```yaml
jobs:
  build-and-publish:
    if: >-
      github.event_name != 'workflow_run' ||
      github.event.workflow_run.conclusion == 'success'
```

Caveat to document: `workflow_run` only fires from the **default-branch** version
of the file — fine here (`main`).

## Rollout (one-off)

Run `curate-ingested-r2 --rebuild-all` once after deploy so the curated parquet is
re-derived under UTC (ticket 02) and picks up the migrated events (ticket 04).

## Acceptance criteria

- Dispatching `log-event.yml` with a datetime + type + notes writes a valid
  `create` record to `s3://$R2_BUCKET/events/year=YYYY/<revision_id>.json`.
- Its completion triggers `basement-site.yml` via `workflow_run`; a failed
  log-event run does **not** trigger a rebuild.
- The rebuilt site reflects the new event.
- `log-event.yml` holds no cross-workflow dispatch call or elevated token.
