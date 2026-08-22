# 03 — Event store module + snapshot tests

Status: resolved
Type: task
Blocked by: 01, 02
Parent PRD: ../PRD.md

## Goal

Implement the R2-backed, append-only event store: the `EventRecord` model, key
generation, JSON (de)serialization, and the DuckDB derive-current-state read
path — with reproducible snapshot tests. See PRD **Appendix A** for the full
verbatim design; implement it exactly, adapted to R2.

## Module

New `src/basement_analysis/event_store.py`.

## Record model (Pydantic `EventRecord`)

Fields per Appendix A:
`event_id`, `revision_id` (both UUIDv7 via stdlib `uuid.uuid7()`), `operation`
(`create`/`update`/`delete`), `recorded_at` (UTC), `effective_at` (UTC; omitted on
`delete`), `event_type`, `data`, `source` (`repository`, `workflow`, `run_id`,
`git_sha`).

Basement domain rules:
- `event_type` slug enum: `dehumidifier_tank_full`, `dehumidifier_tank_emptied`,
  `dehumidifier_installed`, `custom`.
- `data` = `{"notes": "<text>"}`; `notes` omitted when empty. `custom` **requires**
  non-empty notes; the three dehumidifier types allow optional notes. Validate this.
- Canonical timestamps stored as ISO-8601 UTC with trailing `Z`.
- Event input `effective_at` parsing accepts `YYYY-MM-DD HH:mm:ss` (space, seconds
  required), interpreted as `Europe/London` via `london_wall_clock_to_utc` (ticket 02).

## Injection for reproducibility

- Clock: `now: Callable[[], datetime]` (default real UTC now) sets `recorded_at`.
- Id factory: injectable UUIDv7 generator (default `uuid.uuid7`) for
  `event_id`/`revision_id`.
- No monkeypatching of internals.

## Key generation

`events/year=YYYY/<revision_id>.json`, where `YYYY` is the UTC year of
**`effective_at`** (for `delete`, which has no `effective_at`, use the year of the
target event's `effective_at` — or document + use `recorded_at` year if the target
isn't loaded; decide during implementation and document).

## Write path

- Build + validate a record; serialize to JSON; write to a **local file**; print
  the destination object key. (Upload is done by the caller — the Action uses
  `aws s3 cp`; see ticket 06. No boto3.)

## Read path (DuckDB)

Provide the derive-current-state query and helpers over
`s3://$R2_BUCKET/events/year=*/*.json` (and a local glob for tests), returning:
- current non-deleted events (latest revision per `event_id`, excluding tombstones);
- full history;
- history for one `event_id`;
- deleted events.
Use the `row_number() OVER (PARTITION BY event_id ORDER BY recorded_at DESC,
revision_id DESC)` pattern from Appendix A.

## Tests (owner spec, verbatim intent)

Fixtures under `tests/data/event_store/` (checked in as `year=YYYY/<revision_id>.json`).
- **Write-path snapshot test**: with a frozen clock + fixed id-factory, build
  create/update/delete records and assert emitted JSON is byte-identical to the
  committed snapshot corpus.
- **Read-path test**: point DuckDB at the committed corpus (local glob) and assert
  derive-current-state, single-`event_id` history, and deleted-events results.
- DST test lives with ticket 02's utility but exercise event input parsing here.

## Acceptance criteria

- `EventRecord` round-trips (build → JSON → parse) losslessly; validation rejects
  bad `event_type`, empty-notes `custom`, and non-UTC/naive canonical timestamps.
- Snapshot tests reproducible across runs (frozen clock + ids).
- DuckDB queries return correct current state / history / deleted views against
  the committed corpus.
- pyright strict clean; ruff clean.

## Answer

Landed in commit `f654ae3`, with the production R2 row-loading correction in `34c98f1`:
`EventRecord` validates the append-only create/update/delete model, UTC serialization, enum and
notes rules; injected clocks/UUIDv7 factories make write snapshots byte-reproducible; object keys
partition by effective UTC year; and DuckDB derives current, deleted, full-history, and per-event
views for local or R2 corpora. The live ticket-04 verification read all 12 migrated records through
the production path. The final feature gate passes 108 tests, Ruff, and strict Pyright.
