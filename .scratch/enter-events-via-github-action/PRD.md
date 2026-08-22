# PRD: Enter basement events via a GitHub Action (R2-backed event store)

## Goal

Replace the checked-in `data/basement_events.csv` with an append-only, auditable
event store in R2, and give the owner a GitHub Action to log new events by hand.
Logging an event through the Action stores it in R2 and triggers the site
rebuild so the published site reflects the new event.

Alongside this, normalize **all** canonical timestamps in the pipeline (events
*and* sensor/weather/rainfall data) to UTC instants, pushing `Europe/London` to
the ingestion and presentation boundaries only.

Repo: `robjhornby/basement-plant`. Tracker: local markdown under `.scratch/`.

## Background: current state

- Events live in `data/basement_events.csv` (12 rows), format `Time,Event` where
  `Time` is `YYYY/MM/DD HH:MM[:SS]` and `Event` is free text.
- `load_events()` in `static_site.py` parses the CSV into `Event(timestamp, description)`.
- The hosted GHA build (`hosted_curation.py:241`) reads the **checked-out CSV** as
  the authoritative history and writes it into the R2 curated parquet
  `events/source=local_manual` partition via `aws s3 sync --delete`.
- `tank_estimator.py` detects tank events by **substring-matching** the description
  for "tank full" / "tank emptied"; the existing rows carry the typo "dehumide**r**".
- `DEHUMIDIFIER_INSTALLED_AT = datetime(2026, 7, 1, 21, 0)` is hardcoded in both
  `tank_estimator.py:47` and `scripts/tank_drawdown_gauge.py:38`.
- The whole pipeline currently works in **naive Europe/London wall-clock** time.
- Deps: `duckdb`, `numpy`, `pillow`, `polars` — **no boto3, no pydantic**. Reads use
  DuckDB (httpfs); the workflow writes R2 via the `aws` CLI.
- Actions secrets: `R2_ENDPOINT_URL`, `R2_ACCESS_KEY_ID`, `R2_SECRET_ACCESS_KEY`,
  `R2_BUCKET`, `R2_SITE_BUCKET`.
- Python is **3.14** — `uuid.uuid7()` is in the stdlib (no dependency needed).

## Resolved design decisions

The full generic design is embedded verbatim in **Appendix A** (S3/R2 event
store) and **Appendix B** (UTC normalization). The basement-specific decisions
made on top of them:

### Storage model
- Immutable **one-JSON-file-per-mutation** under
  `s3://$R2_BUCKET/events/year=YYYY/<revision_id>.json` (Appendix A).
- `event_id` / `revision_id` are **UUIDv7** (stdlib `uuid.uuid7()`).
- Partition `year=YYYY` keys off **`effective_at`** (UTC year of when the event
  occurred), not `recorded_at`.
- Append-only; `create` / `update` / `delete` (tombstone) operations. DuckDB
  derives current state. **DuckDB** is the read tool (already how this codebase
  reads R2).
- The R2 JSON store is the new **source of truth**; `hosted_curation` derives
  current state and materializes it into the curated parquet events partition
  (Option (a) — smallest change to the build).

### Operations exposed
- The GitHub Action exposes **`create` only**. `update` / `delete` are supported
  by the model and available via a local script, but not via the workflow form
  (a workflow_dispatch form can't pick an existing `event_id` cleanly).

### Domain mapping
- `event_type` is a **slug enum**: `dehumidifier_tank_full`,
  `dehumidifier_tank_emptied`, `dehumidifier_installed`, `custom`.
- `data` payload: `{"notes": "<text>"}`, `notes` omitted when empty.
  - `custom` **requires** non-empty notes (a custom event *is* its notes text).
  - the three dehumidifier types allow optional notes.
- Consumers key off the **enum**, not English substrings. `Event` gains the
  `event_type` enum; `tank_estimator` and `tank_drawdown_gauge` match on it.
- `DEHUMIDIFIER_INSTALLED_AT` is no longer hardcoded: it is derived from the
  single/earliest `dehumidifier_installed` event in the log (zero/multiple case
  documented, not heavily guarded).

### Timezone (Appendix B)
- Invariant: **all** canonical timestamps in JSON, curated parquet, and DuckDB
  are UTC instants. `Europe/London` is an ingestion + presentation concern only.
- One shared utility `london_wall_clock_to_utc(naive)` interpreting input as
  `Europe/London` then converting to UTC. DST fall-back resolved with a
  documented, tested **`fold=0`** policy (first / BST occurrence).
- No `timestamp_raw` column in curated parquet — the raw X-Sense CSVs already
  persist untouched in R2 as the audit trail.
- Event input format: `YYYY-MM-DD HH:mm:ss` (space-separated, seconds required),
  interpreted as `Europe/London`, stored as UTC (`...Z`).

### Migration of the 12 existing rows
- One-off `scripts/migrate_events_csv.py` writes each row as a `create` record.
- `effective_at`: CSV naive-local → UTC via `Europe/London`.
- 5 "dehumider tank full" rows → `dehumidifier_tank_full` (typo dropped — the
  enum is the identity now).
- "dehumidifier installed …" row → `dehumidifier_installed`.
- remaining free-text rows → `custom` with `data.notes` = original text verbatim.
- `recorded_at` = actual UTC instant the migration runs. `event_id`/`revision_id`
  freshly generated UUIDv7. `source` = `{"workflow": "csv-migration"}` (run_id /
  git_sha omitted).
- After a **verified** migration: `git rm data/basement_events.csv` and re-add it
  to `.gitignore`.

### The Action
- `.github/workflows/log-event.yml`, `workflow_dispatch`, inputs:
  - `effective_at` — string, required, placeholder `YYYY-MM-DD HH:mm:ss`.
  - `event_type` — choice: `dehumidifier tank full`, `dehumidifier tank emptied`,
    `custom` (the workflow maps display string → slug; `dehumidifier installed`
    is **excluded** as a one-off already migrated).
  - `notes` — string, optional, default empty.
- The job runs `uv run basement log-event …` (CLI, because it is used
  repeatedly), which builds + validates the record, writes the JSON to a local
  file, and prints the destination object key. The workflow uploads it with
  `aws s3 cp` (no boto3). `source` fields come from the GHA context env vars.
- Rebuild is triggered natively via **`workflow_run`**: `basement-site.yml`
  subscribes to `log-event.yml`'s completion and gates the build job on
  `conclusion == 'success'`. `log-event.yml` needs no `actions: write` / token.
  (Caveat: `workflow_run` only fires from the default-branch version of the file.)

### Code placement / naming conventions
- New module `src/basement_analysis/event_store.py`: Pydantic `EventRecord`,
  clock + id-factory injection, key generation, JSON (de)serialization, DuckDB
  derive-current-state query.
- **CLI subcommand vs script rule**: repeated/production use → CLI subcommand
  (`basement log-event`); one-off use → standalone script in `scripts/`
  (`scripts/migrate_events_csv.py`).
- Adopt **Pydantic** as the project standard: add the dependency, use it for all
  new serialization/validation, and convert existing dataclasses to Pydantic
  models.

### Testing
- Fixtures under `tests/data/event_store/` (checked-in `year=YYYY/<revision_id>.json`).
- Reproducibility via an injected clock (`now: Callable[[], datetime]`) and an
  injected UUIDv7 id-factory — no monkeypatching internals — so the write path
  emits byte-identical snapshots.
- Write-path test: build create/update/delete records with frozen clock + ids,
  assert emitted JSON matches committed snapshots.
- Read-path test: point DuckDB at the committed snapshot corpus and assert the
  derive-current-state, single-`event_id` history, and deleted-events queries.

### Rollout
- One-off `curate-ingested-r2 --rebuild-all` after deploy, because sensor/
  weather/rainfall timestamps change from naive-local to UTC and the whole
  curated parquet must be re-derived under the new representation.

## Local build behaviour

A local `basement` build (no `--reuse-curated`) reads events from the **R2**
event store via DuckDB using local R2 creds (the CSV is gone).

## Tickets

See `issues/`:

1. `01-adopt-pydantic.md` — add Pydantic; convert all package dataclasses.
2. `02-utc-timestamp-normalization.md` — shared tz utility + convert pipeline to UTC.
3. `03-event-store-module.md` — `EventRecord`, key gen, DuckDB read, snapshot tests.
4. `04-csv-to-r2-migration.md` — migrate the 12 rows; remove the CSV.
5. `05-consumer-refactor.md` — enum-based `Event`; tank consumers; build read path.
6. `06-github-action.md` — `log-event.yml` + `basement-site.yml` `workflow_run`.

Dependency order: 01 → 02 → 03 → {04, 05} → 06. 04 and 05 both depend on 03;
06 depends on 03 + 05.

---

## Appendix A — Event store design (verbatim, owner-supplied)

> Note: the spec below says "S3"; we use **R2** (S3-compatible). We use
> `uuid.uuid7()` from the Python 3.14 stdlib.

# Prompt: Design an S3 Event Store for GitHub Actions + DuckDB

Design and implement a simple event storage format for events written by GitHub Actions, stored in S3, and later read/processed with DuckDB.

## Requirements

Use the following design decisions:

* Store data in **S3-compatible object storage**.
* Use **JSON** as the canonical storage format.
* Use **one immutable JSON file per event mutation**.
* Partition files by **year only**.
* Use **UUIDv7** for IDs because it is globally unique and time-sortable.
* Preserve full history: updates and deletions must never destroy or overwrite prior records.
* Logical deletion should be represented as a new event record rather than physically deleting previous S3 objects.
* The expected write volume is extremely low, approximately **one event per week**, so small-file optimization is not important.
* DuckDB will be responsible for reading the files and deriving the current state.

## Desired S3 Layout

Use a layout similar to:

```text
s3://<bucket>/events/
  year=2026/
    <uuidv7>.json
    <uuidv7>.json
  year=2027/
    <uuidv7>.json
```

Each filename should use the record's unique `revision_id`, which is a UUIDv7.

Do not partition by month, day, event type, or other dimensions unless there is a strong future reason to change the design.

## Event Model

Distinguish between the identity of the logical event and the identity of each stored mutation.

Each record should contain at least:

```json
{
  "event_id": "UUIDv7",
  "revision_id": "UUIDv7",
  "operation": "create",
  "recorded_at": "2026-08-22T10:15:32Z",
  "effective_at": "2026-09-12T18:00:00Z",
  "event_type": "deployment",
  "data": {},
  "source": {
    "repository": "owner/repository",
    "workflow": "workflow-name",
    "run_id": "123456789",
    "git_sha": "abcdef..."
  }
}
```

### Field semantics

`event_id`
: Stable UUIDv7 identifying the logical event. All later updates or deletion records for the same event reuse this ID.

`revision_id`
: UUIDv7 identifying this specific immutable record. Every stored JSON file gets a new revision ID.

`operation`
: One of:

```text
create
update
delete
```

`recorded_at`
: UTC timestamp representing when this mutation was recorded by the system.

`effective_at`
: Timestamp representing when the underlying event occurs or occurred. This is distinct from when it was written.

`event_type`
: Application-level category for the event.

`data`
: Application-specific event payload.

`source`
: Provenance information identifying the GitHub Actions run that produced the record.

## Update Semantics

Use an append-only model.

Never overwrite an existing S3 object.

For an update:

1. Reuse the existing `event_id`.
2. Generate a new UUIDv7 `revision_id`.
3. Set `operation` to `update`.
4. Write a new JSON object.

Prefer storing a **complete snapshot of the logical event on every update**, rather than storing JSON diffs or patches.

For example:

```json
{
  "event_id": "0198...",
  "revision_id": "0199...",
  "operation": "update",
  "recorded_at": "2026-09-01T14:03:11Z",
  "effective_at": "2026-09-12T18:00:00Z",
  "event_type": "deployment",
  "data": {
    "version": "v1.43.0",
    "environment": "production"
  }
}
```

The storage overhead is insignificant at this event volume, while complete snapshots make DuckDB queries and historical reconstruction substantially simpler.

## Deletion Semantics

Do not physically delete prior event files.

Represent deletion by writing another immutable record:

```json
{
  "event_id": "0198...",
  "revision_id": "019A...",
  "operation": "delete",
  "recorded_at": "2026-10-10T08:22:51Z",
  "event_type": "deployment",
  "source": {
    "repository": "owner/repository",
    "workflow": "workflow-name",
    "run_id": "123456789",
    "git_sha": "abcdef..."
  }
}
```

This should behave as a tombstone.

The latest record determines whether the logical event currently exists, while all previous revisions remain available for audit and historical analysis.

## DuckDB Usage

The storage layout should be directly queryable by DuckDB, for example:

```sql
SELECT *
FROM read_json_auto(
    's3://<bucket>/events/year=*/*.json',
    union_by_name = true
);
```

Provide a query or view for deriving the current state.

Conceptually:

```sql
WITH history AS (
    SELECT *
    FROM read_json_auto(
        's3://<bucket>/events/year=*/*.json',
        union_by_name = true
    )
),
latest AS (
    SELECT *,
           row_number() OVER (
               PARTITION BY event_id
               ORDER BY recorded_at DESC, revision_id DESC
           ) AS rn
    FROM history
)
SELECT *
FROM latest
WHERE rn = 1
  AND operation <> 'delete';
```

Also preserve straightforward access to the complete history:

```sql
SELECT *
FROM read_json_auto(
    's3://<bucket>/events/year=*/*.json',
    union_by_name = true
)
ORDER BY event_id, recorded_at, revision_id;
```

## Design Reasoning

This workload is intentionally optimized for simplicity and auditability rather than high-throughput ingestion.

### Why multiple immutable files?

S3 is object storage, not an appendable filesystem.

Maintaining one large JSON object would require each GitHub Actions run to:

1. download the existing file,
2. modify it,
3. upload the entire file again,
4. deal with concurrent updates and lost-write risks.

Writing a new immutable object for each mutation avoids locking, read-before-write, and concurrency problems.

At approximately one event per week, the number of files is trivial, so there is no meaningful small-file concern.

### Why JSON?

JSON is preferred over Parquet for the canonical event log because:

* individual writes contain only one record;
* GitHub Actions can generate JSON easily;
* records are human-readable and easy to inspect or recover manually;
* schema evolution is relatively forgiving;
* DuckDB can read many JSON files as one relation.

If volume grows substantially in the future, the immutable JSON event log can remain the source of truth while periodically generated Parquet files provide an analytical optimization.

### Why only partition by year?

The expected volume is roughly 52 records per year.

Additional partitions such as month/day/type would add complexity without providing meaningful query pruning.

The year partition provides basic organization and allows future queries to exclude whole years when useful without creating an excessively fragmented S3 hierarchy.

### Why UUIDv7?

UUIDv7 provides:

* globally unique identifiers;
* time ordering;
* convenient sorting and debugging;
* no need for a centralized sequence generator;
* suitability for independently running GitHub Actions jobs.

Use UUIDv7 for both `event_id` and `revision_id`.

### Why separate `event_id` and `revision_id`?

A logical event may change over time.

For example:

```text
event_id=A
  revision=1  create
  revision=2  update
  revision=3  update
  revision=4  delete
```

`event_id` answers:

> Which logical event is this?

`revision_id` answers:

> Which immutable version/change record is this?

This separation makes current-state queries, auditing, and historical reconstruction straightforward.

## Implementation Expectations

Produce a practical implementation suitable for GitHub Actions.

Include:

* a schema or clearly defined record structure somewhere, e.g. a Pydantic model in Python if the records will be written/read with Python;
* UUIDv7 generation;
* UTC timestamp handling;
* S3 object-key generation;
* create/update/delete examples;
* example DuckDB queries or views for:

  * all historical records;
  * current non-deleted events;
  * history for one `event_id`;
  * deleted events.

Prefer a small, understandable implementation over introducing a database, transaction coordinator, manifest service, or complex event-sourcing framework.

The intended architecture is:

```text
GitHub Action
     │
     ├── generate/reuse event_id
     ├── generate UUIDv7 revision_id
     ├── validate JSON
     │
     ▼
immutable JSON object
     │
     ▼
S3
  events/
    year=YYYY/
      <revision_id>.json
     │
     ▼
DuckDB
  ├── complete history
  └── derived current state
```

Treat the immutable JSON objects as the canonical event history. DuckDB views or queries should derive application state from that history rather than modifying the stored records.

### Owner addendum to Appendix A

> Note the above talks about S3 but we're using R2.
> For implementation approach, I want this to mainly be something like a Python
> script so that we can have unit tests for the event structure, and for reading
> events, i.e. I want pytest-snapshot style tests which create a small local
> dataset reproducibly (with the record creation timestamps mocked to be
> constant between runs) and that also creates a small local data set from the
> snapshots which can be used for testing the read path via duckdb. The
> snapshots should be stored somewhere with a semantically meaningful name under
> the tests folder (not the default pytest-snapshot directory). Note I'd prefer
> to use duckdb for reading from R2 but if there's a stronger alternative based
> on what's already in the current codebase we can continue using that.

---

## Appendix B — UTC normalization decision (verbatim, owner-supplied)

# Decision: Normalize all timestamps to UTC

Agreed. Update the design so that **all canonical timestamps in the event and sensor data model are stored as UTC instants**, rather than carrying naive Europe/London wall-clock timestamps through the pipeline.

## X-Sense CSV ingestion

X-Sense CSV exports contain timestamps like:

```text
2026/08/21 23:59
```

These timestamps have **no timezone or UTC offset**, so treat them as naive local wall-clock values from the sensor/export environment.

For this system, assume X-Sense timestamps are in:

```text
Europe/London
```

Interpret the naive CSV timestamp using the `Europe/London` timezone rules, then immediately convert it to UTC during ingestion.

Example:

```text
X-Sense CSV:
2026/08/21 23:59

Interpret as:
2026-08-21T23:59:00+01:00
Europe/London / BST

Canonical UTC:
2026-08-21T22:59:00Z
```

Do **not** hardcode `+00:00` or `+01:00`. Hardcode the IANA timezone name `Europe/London` and allow the timezone database to determine GMT vs BST based on the date.

## Canonical timestamp rule

Use this invariant throughout the system:

> All timestamps in canonical JSON, curated Parquet, and DuckDB represent actual instants in UTC.

That means:

* `recorded_at` is UTC.
* `effective_at` is UTC.
* X-Sense sensor timestamps are converted to UTC during ingestion.
* Curated Parquet timestamps are UTC.
* DuckDB comparisons and joins operate on UTC timestamps.
* Convert UTC to `Europe/London` only at presentation/UI boundaries when a human-readable local time is required.

## Event input

Event entry can continue to accept:

```text
YYYY-MM-DD HH:mm:ss
```

as UK local wall-clock time.

Interpret that input as `Europe/London`, then convert it to UTC before writing the JSON event record.

Example:

```text
Entered:
2026-07-05 00:51:03

Interpret as:
2026-07-05T00:51:03+01:00
Europe/London

Store:
2026-07-04T23:51:03Z
```

The JSON should therefore look like:

```json
{
  "event_id": "UUIDv7",
  "revision_id": "UUIDv7",
  "operation": "create",
  "recorded_at": "2026-08-22T10:15:32Z",
  "effective_at": "2026-07-04T23:51:03Z",
  "event_type": "deployment",
  "data": {}
}
```

Prefer storing canonical timestamps using ISO-8601 UTC with a trailing `Z`.

## Curated sensor data

Change the existing curated sensor model so that timestamps are no longer naive Europe/London wall-clock values.

Instead of:

```text
2026-08-21 23:59:00
```

store the corresponding UTC instant:

```text
2026-08-21 22:59:00+00:00
```

Use an appropriate timestamp-with-timezone representation where supported.

The important semantic rule is that the stored value represents UTC, regardless of the exact physical Parquet/DuckDB timestamp type chosen.

## Joining events to sensor readings

Do all temporal matching on the UTC timeline.

For example:

```text
Event effective_at:
2026-08-21T22:59:00Z

Sensor timestamp:
2026-08-21T22:59:00Z
```

This avoids having to remember which datasets contain naive UK local timestamps and removes DST offsets from downstream matching logic.

## DST fall-back ambiguity

There is one unavoidable source-data limitation.

During the autumn DST transition, a value such as:

```text
2026/10/25 01:30
```

is ambiguous in `Europe/London`, because that local wall-clock time occurs twice:

```text
01:30 BST
01:30 GMT
```

The X-Sense CSV format provides no offset or timezone metadata, so the exporter has already discarded the information required to distinguish those two instants.

Do not introduce a complex model solely to handle this case.

Instead:

* document the ambiguity;
* use one explicit and deterministic `fold`/DST-resolution policy in the parser;
* keep that policy covered by a test;
* allow it to be changed later if better information about X-Sense export behaviour becomes available.

Do not silently rely on an undocumented library default.

## Preserve raw source timestamps

For X-Sense ingestion, preserve the original source timestamp alongside the normalized UTC timestamp where practical.

For example:

```text
timestamp_raw
2026/08/21 23:59

timestamp
2026-08-21T22:59:00Z
```

This provides an audit trail and allows the timezone assumption to be revisited later without needing the original CSV again.

A reasonable curated representation is therefore conceptually:

```text
timestamp_raw    VARCHAR
timestamp        TIMESTAMPTZ / canonical UTC timestamp
temperature_c    DOUBLE
relative_humidity_percent DOUBLE
```

If retaining `timestamp_raw` in the final curated Parquet is undesirable, retain it at least in the raw/staging layer.

> **Owner decision on this point:** do **not** add a `timestamp_raw` column to the
> curated parquet. The raw X-Sense CSVs already persist untouched in R2 and serve
> as the audit trail, allowing the tz assumption to be revisited later.

## Implementation guidance

Create a single utility for interpreting UK wall-clock input rather than duplicating timezone logic.

Conceptually:

```python
from datetime import datetime, timezone
from zoneinfo import ZoneInfo

LONDON = ZoneInfo("Europe/London")

def london_wall_clock_to_utc(value: datetime) -> datetime:
    if value.tzinfo is not None:
        raise ValueError("Expected naive Europe/London wall-clock datetime")

    local = value.replace(
        tzinfo=LONDON,
        # Apply the project's documented fold policy here.
    )

    return local.astimezone(timezone.utc)
```

> **Owner decision on the fold policy:** use `fold=0` (the first / BST occurrence
> of an ambiguous wall-clock time), documented and covered by a test.

Use this same interpretation rule for:

* manually entered event `effective_at` values;
* X-Sense CSV timestamps;
* any other source explicitly documented as UK local wall-clock time.

Keep parsing and timezone interpretation conceptually separate:

```text
string
  ↓
naive datetime
  ↓
interpret as Europe/London
  ↓
timezone-aware instant
  ↓
convert to UTC
  ↓
canonical storage
```

## Overall model

The pipeline should become:

```text
X-Sense CSV
"2026/08/21 23:59"
        │
        │ interpret as Europe/London
        ▼
2026-08-21T23:59:00+01:00
        │
        │ convert
        ▼
2026-08-21T22:59:00Z
        │
        ▼
curated Parquet / DuckDB
```

and:

```text
Event input
"2026-07-05 00:51:03"
        │
        │ interpret as Europe/London
        ▼
2026-07-05T00:51:03+01:00
        │
        │ convert
        ▼
2026-07-04T23:51:03Z
        │
        ▼
JSON event store
        │
        ▼
DuckDB
```

The architectural principle is:

> `Europe/London` is an ingestion and presentation concern. UTC is the internal canonical timeline.

Please update the implementation, schemas, tests, and DuckDB queries accordingly, while keeping the model simple and avoiding unnecessary timezone abstractions beyond this boundary normalization.
