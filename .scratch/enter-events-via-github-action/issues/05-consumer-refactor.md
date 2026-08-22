# 05 — Refactor event consumers to the enum + R2 read path

Status: open
Type: task
Blocked by: 03
Parent PRD: ../PRD.md

## Goal

Move every consumer of the event log off free-text `description` substring
matching and off the local CSV, onto the `event_type` enum and the R2 event
store (via the curated parquet, per Option (a)).

## Owner decisions (verbatim)

> Let's change how tank_estimator reads these events to use the full event type
> as an enum.
> Updating tank_estimator and any other users of this event log is in scope and
> must be done as part of this feature update.
> Make the dehumidifier installed its own event type in the migration, and update
> the script to load it from the event log rather than hardcode it, this is now
> in scope.

## Scope

### `Event` model
- `Event` (now Pydantic, ticket 01) gains the `event_type` enum field and `notes`;
  `timestamp` is UTC. Derive a display label where rendering needs text
  (`custom` → notes; dehumidifier types → canonical display string).

### Curated parquet events partition (`curated_dataset.py`)
- `event_frame` / `load_events_from_parquet` schema changes from
  `(timestamp, description)` to `(timestamp UTC, event_type, notes)`.

### hosted + local builds
- `hosted_curation.py`: replace `load_events(CSV)` with a DuckDB
  derive-current-state query over `s3://$R2_BUCKET/events/year=*/*.json`, feeding
  the curated parquet events partition (published via `aws s3 sync --delete` as now).
- Local full build (`basement` without `--reuse-curated`): read events from the
  **R2** store via DuckDB (local R2 creds). Remove `load_events`-from-CSV.

### `tank_estimator.py`
- Match tank events on `event_type` (`dehumidifier_tank_full` /
  `dehumidifier_tank_emptied`) instead of substring matching.
- Replace hardcoded `DEHUMIDIFIER_INSTALLED_AT` (line 47) with the install date
  derived from the single/earliest `dehumidifier_installed` event. Document the
  zero-events and multiple-events cases (per "prefer simple models" — earliest
  wins, no heavy guard).

### `scripts/tank_drawdown_gauge.py`
- Stop reading the CSV (`EVENTS_CSV`, line 37) — read events from the event store.
- Stop hardcoding `DEHUMIDIFIER_INSTALLED_AT` (line 38) — derive from the log.

### Other consumers
- Audit `static_site.py` rendering + `summaries.py` for description-based logic;
  switch to enum + derived label.

### Tests
- Rework fixtures that synthesize `basement_events.csv`
  (`test_curated_dataset.py`, `test_hosted_curation.py`,
  `test_static_site_summary.py`) to the new event-store inputs.

## Acceptance criteria

- No consumer references `data/basement_events.csv` or matches event description
  substrings; all key off `event_type`.
- Install date comes from the `dehumidifier_installed` event; tank estimation
  output matches the pre-refactor result for the migrated data.
- hosted + local builds read events from R2; full suite green; pyright strict
  clean; ruff clean.
