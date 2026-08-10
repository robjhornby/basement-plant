# Incremental curation — watermark-driven CSV ingest, read R2 directly

Labels: ready-for-agent

Grounds out the "incremental-load" thread in `STATUS.md`. Rob picked **Option A** (DuckDB
reads R2 directly; drop the bulk download step) on 2026-08-08. No breaking R2 migration is
required — the watermark comes free from the existing parquet.

## Problem Statement

The nightly hosted build (`.github/workflows/basement-site.yml`, `curate-ingested-r2` →
`hosted_curation.curate_accepted_email_csvs`) rebuilds the curated Parquet from scratch every
run:

1. `aws s3 sync` downloads **every** ingest manifest and **every** sensor CSV from R2 to the
   runner (the slow, ever-growing "Download accepted ingest manifests and CSVs" step —
   ~150 objects and climbing, and it re-downloads the whole history nightly).
2. Python re-parses **every** staged CSV into `SensorReading`s.
3. Those are merged with the sensor readings already in the existing R2 parquet and
   **deduplicated by (location, timestamp)** (`merge_sensor_readings`).
4. The full parquet is rewritten and pushed back with `s3 sync --delete`.

Steps 1–3 do work proportional to the **entire** history every night, but step 3's dedup
discards all of it except the handful of genuinely-new readings. The cost grows without bound
as the dataset accumulates; nothing about the design is incremental.

## Solution

Make curation **incremental** and **R2-native**:

- The existing R2 parquet is already the full merged history. Read it once and take the
  **watermark** = the maximum sensor-reading timestamp in it.
- Download and parse **only** the accepted CSVs whose partition `export_date` is at or after
  `watermark.date() − OVERLAP_DAYS` (default `OVERLAP_DAYS = 2`). Everything older is already
  in the parquet.
- Merge the (small) newly-parsed readings into the existing readings with the **same
  dedup-by-(location, timestamp)** as today, then write and publish as today. The overlap plus
  dedup make re-ingesting the last couple of days harmless and idempotent.
- Read the object store (manifests + CSVs) **directly from R2** via the DuckDB S3 config
  already used for the curated parquet (`curated_dataset.configure_r2_access`). The separate
  bulk `aws s3 sync` download step in the workflow is **deleted**.

No new parquet columns and no R2 data migration: the watermark is derived, not stored.

### Why this is correct

`merge_sensor_readings` is a set-union keyed by (location, timestamp). Given the existing
parquet `E` and any superset-of-new CSV batch `N` that includes every reading later than the
watermark, `merge(E, N)` equals `merge(E, all_CSVs)` — the readings only in old CSVs are
already in `E`, and dedup collapses the overlap. So an incremental run and a full rebuild
produce the **same** curated parquet. This equivalence is the primary test (see issue 01).

### The one assumption, and its escape hatch

Selecting by `export_date >= cutoff` is safe **unless** an accepted CSV with an `export_date`
older than the cutoff carries a reading newer than the watermark and was never previously
ingested (e.g. an old export that failed, then got re-accepted weeks later). With daily,
reliable X-Sense emails this does not occur. If it ever does, the robust fix is a **ledger of
already-ingested CSV object keys** persisted in R2 (the "extra metadata" anticipated when this
was scoped) so selection is by "not-yet-seen key" rather than by date. That ledger is **out of
scope now** — documented here as the next step if and only if the date assumption is observed
to break (matches the owner's "one data-justified fix at a time" discipline).

## User Stories

1. As the owner, I want the nightly job to stop re-downloading the entire CSV history so the
   build stays fast and cheap as data accumulates.
2. As the owner, I want each run to fetch and parse only CSVs newer than what's already
   curated, appending them to the existing parquet.
3. As the owner, I want the object store read straight from R2 (no local mirror step), since
   the pipeline already reaches R2 through DuckDB.
4. As the owner, I want an incremental run to produce byte-for-byte the same curated parquet a
   full rebuild would, so incrementalism never silently drops or corrupts data.
5. As the owner, I want a `--rebuild-all` path that ignores the watermark and re-parses the
   whole history, so a future change to CSV parsing or derived columns (e.g. the
   `absolute_humidity_g_m3` formula) can be back-applied to all rows in one deliberate run.
6. As the owner, I want the whole thing testable against a **local** object-store fixture (no
   network), so CI/tests don't depend on R2.

## Implementation Decisions

### Object-store root accepts s3:// or a local dir

`curate-ingested-r2` gains `--object-store-root` (accepting `s3://bucket` **or** a local path,
parsed like the curated root via `parse_curated_data_location`), replacing the local-only
`--object-store-dir`. The manifests live under `<root>/manifests/ingest/...` and CSVs under
`<root>/csv/source=x-sense/export_date=YYYY-MM-DD/attachment_sha256=.../<file>.csv`, exactly as
in R2 today. When the root is `s3://`, reads use `configure_r2_access`; when it's a local dir,
reads use the filesystem (this is the test path).

### Watermark and cutoff

- `watermark` = `max(reading.timestamp for reading in existing_dataset.sensor_readings)`. If the
  existing parquet has **no** sensor readings (cold start), there is no watermark → ingest
  **all** accepted CSVs (equivalent to `--rebuild-all`).
- `OVERLAP_DAYS = 2` (module constant; the one tunable). `cutoff_date = (watermark.date() −
  OVERLAP_DAYS)`.
- Selection: an accepted CSV is parsed iff its `export_date` partition value (parsed from the
  object key) is `>= cutoff_date`. `--rebuild-all` bypasses the cutoff and parses every accepted
  CSV.

### Accepted-CSV gate is preserved

Which CSVs are eligible is still decided by the ingest manifests (`status == "accepted"`,
attachment `status == "extracted"`, `csv_object_key` present) — see
`accepted_csv_object_keys`. Only manifests whose partition `received_date >= cutoff_date` need
to be read for an incremental run (received_date tracks export_date within a day); `--rebuild-all`
reads all manifests. The gate logic itself is unchanged; only its input source (R2 vs local
mirror) and the date-bounding are new.

### Reading manifests and CSVs from R2

Prefer the tool already in the codebase: DuckDB with `configure_r2_access`. DuckDB can glob and
read both the manifest JSON (`read_json_auto` over the recent `received_date=` partitions) and
the CSVs (`read_csv` over the recent `export_date=` partitions) directly from `s3://`. The
implementer may instead keep the existing Python CSV/JSON parsing and fetch just the recent
objects, **provided** no new heavyweight dependency is added and the local-fixture test path
still works. Whatever the mechanism, the parsed `SensorReading` shape and
`sensor_location_for_filename` mapping are unchanged.

### Weather / rain fetch unchanged

`merged_sensor_readings` still spans the full history (existing + new), so `dataset_start` /
`dataset_end` and the weather/rain fetch-and-merge are unaffected. Do not touch them.

### `--rebuild-all` flag

`curate-ingested-r2 --rebuild-all` ignores the watermark and parses every accepted CSV (still
merged/deduped against the existing parquet, so it's safe to run anytime). This is the
documented way to back-apply a parsing change to history. A hard reset (drop the R2 parquet
first) remains an option Rob can do by hand — noted, not automated.

### Observability

Keep the phase-timing structure. Add/rename phases so an incremental run's log makes the saving
visible: report how many CSVs were **selected** vs how many accepted CSVs exist, and the
watermark/cutoff used. Extend the `curate-ingested-r2` timing counts with e.g.
`selected_csv_count` and `watermark` alongside the existing counts.

## Testing Decisions

- **Equivalence test (primary):** build a local object-store fixture with several days of
  synthetic accepted CSVs. Assert that (a) a full rebuild from empty and (b) an incremental run
  seeded with a parquet that already covers the first days, then handed the same object store,
  produce **identical** curated sensor parquet (same rows). This proves incremental == full.
- **Selection test:** given a watermark, assert only CSVs with `export_date >= cutoff` are
  parsed (e.g. via `selected_csv_count` / the staged set), and that older ones are skipped.
- **Idempotence test:** running the incremental curation twice with no new CSVs is a no-op on
  the sensor rows.
- **Cold-start test:** empty existing parquet ingests all accepted CSVs.
- **`--rebuild-all` test:** with a non-empty watermark, `--rebuild-all` still parses every
  accepted CSV.
- **Accepted-gate test:** a manifest that is not `accepted` (or an attachment not `extracted`)
  is excluded, unchanged from today.
- All tests run against a **local** object-store fixture — no network, no R2 credentials.

## Out of Scope

- The ingested-CSV-key **ledger** in R2 (the robust alternative to date-based selection) — only
  if the date assumption is observed to break.
- Any change to the ingest Worker, the manifest format, or the CSV format.
- Any change to weather/rain fetching, event handling, the site render, or the estimator.
- Incrementalising weather/rain (they're API-bounded and already merged; not the bottleneck).
- Retiring `aws-cli` from the workflow's **publish** steps (only the download step goes).

## Further Notes

- Related prior scoping: `.scratch/basement-ops-and-site-polish/issues/04-assess-pipeline-efficiency-from-timings.md`
  (pipeline efficiency from timings) and `03-add-step-timing-observability.md`.
- The events fix (un-ignoring `data/basement_events.csv`) that unblocked the build is a separate,
  already-landed change (LOG 2026-08-08 hosted-build) — independent of this work.
- Repo is public; nothing here changes what the site publishes.
