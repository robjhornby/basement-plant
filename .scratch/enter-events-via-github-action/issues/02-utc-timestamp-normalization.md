# 02 — Normalize all pipeline timestamps to UTC

Status: open
Type: task
Blocked by: 01
Parent PRD: ../PRD.md

## Goal

Make **all** canonical timestamps in the pipeline UTC instants, with
`Europe/London` confined to ingestion and presentation boundaries. See PRD
**Appendix B** for the full verbatim decision — implement it exactly.

## Scope

- Add a single shared utility (per Appendix B):

  ```python
  def london_wall_clock_to_utc(value: datetime) -> datetime: ...
  ```

  interpreting a naive `Europe/London` wall-clock datetime and converting to UTC.
  Hardcode the IANA name `Europe/London` (never a fixed `+00:00`/`+01:00`).
- **DST fall-back policy: `fold=0`** (first / BST occurrence). Documented in the
  utility's docstring and covered by a dedicated test (both a GMT and a BST date,
  plus the ambiguous fall-back hour).
- Convert X-Sense sensor CSV ingestion to UTC at parse time. `parse_local_datetime`
  currently returns naive local — route sensor timestamps through the new utility
  so curated values are UTC.
- Convert weather + rainfall ingestion timestamps to UTC on the same rule.
- Curated parquet timestamps become UTC instants (timestamp-with-timezone /
  canonical UTC representation).
- Push `Europe/London` to **presentation only**: `chart_timestamp_seconds`
  (`static_site.py:149`) and `static_site.py:370` already convert to local — these
  become the *only* places London is applied, now converting from UTC-aware
  timestamps. Audit for any other place assuming naive-local.
- **Do not** add a `timestamp_raw` column to curated parquet (owner decision) —
  the raw X-Sense CSVs in R2 are the audit trail.

## Acceptance criteria

- Invariant holds: every timestamp in JSON, curated parquet, and DuckDB is a UTC
  instant; `Europe/London` appears only at ingestion + presentation boundaries.
- `london_wall_clock_to_utc` is the single source of tz interpretation, reused by
  sensor ingestion (and later by event input in ticket 03).
- `fold=0` policy documented + tested.
- Site output renders the same local wall-clock times as before (presentation
  converts UTC→London), verified against a before/after build.
- Full suite green; pyright strict clean; ruff clean.

## Rollout note (executed in ticket 06 / deploy, recorded here)

Because curated timestamps change representation, a one-off
`curate-ingested-r2 --rebuild-all` is required to re-derive the whole curated
parquet under UTC. Incremental watermark logic must not mix old naive-local and
new UTC parquet — the rebuild is mandatory, not optional.
