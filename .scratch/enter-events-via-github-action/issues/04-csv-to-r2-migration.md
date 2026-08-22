# 04 — Migrate basement_events.csv into R2; remove the CSV

Status: open
Type: task
Blocked by: 03
Parent PRD: ../PRD.md

## Goal

Migrate the 12 existing rows of `data/basement_events.csv` into the R2 event
store as `create` records, then remove the CSV from the repo.

## Script

`scripts/migrate_events_csv.py` (one-off → standalone script, not a CLI
subcommand). Reads the existing CSV, builds one `EventRecord` (`operation:
create`) per row via the ticket-03 builder, writes the JSON files, and uploads
them to R2 (`aws s3 sync`/`cp`, same creds as the existing workflow).

## Mapping (the 12 rows)

- `effective_at`: CSV naive-local timestamp → UTC via `london_wall_clock_to_utc`.
- **5** "dehumide**r** tank full" rows → `event_type: dehumidifier_tank_full`
  (typo dropped — the enum is the identity; no text to misspell).
- **1** "dehumidifier installed in centre of room …" row (2026-07-01 21:00) →
  `event_type: dehumidifier_installed`, notes = original text verbatim.
- **remaining free-text rows** → `event_type: custom`, `data.notes` = the original
  text **verbatim** (including the "(uncertain timestamp) …" prefixes).
- `recorded_at` = actual UTC instant the migration runs.
- `event_id` / `revision_id` = freshly generated UUIDv7.
- `source` = `{"workflow": "csv-migration"}` (run_id / git_sha omitted).

## Verify before removing the CSV

- Run the derive-current-state query against R2 and confirm all 12 events appear
  with the expected `event_type`, `effective_at` (UTC), and notes.
- Confirm the `dehumidifier_installed` event resolves to `2026-07-01 21:00` London
  (used by ticket 05 to replace the hardcoded constant).

## Then

- `git rm data/basement_events.csv`.
- Re-add `data/basement_events.csv` to `.gitignore` (it was specifically
  un-ignored via `!data/basement_events.csv` — revert that).

## Acceptance criteria

- All 12 events present in R2, correctly typed, UTC `effective_at`, notes verbatim.
- CSV removed from the repo and re-gitignored.
- No consumer still reads `data/basement_events.csv` (coordinate with ticket 05).
