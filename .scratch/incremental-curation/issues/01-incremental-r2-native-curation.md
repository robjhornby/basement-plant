# Incremental, R2-native curation core

Type: task
Parent: ../PRD.md
Status: ready-for-agent

## Question

Make `hosted_curation.curate_accepted_email_csvs` (and its `curate-ingested-r2` CLI) read the
object store directly from R2 and ingest only CSVs newer than the existing curated parquet,
per `../PRD.md` ("Solution", "Implementation Decisions"). Do not touch the workflow YAML — that
is issue 02.

Resolve when:

- `curate-ingested-r2` accepts `--object-store-root` (an `s3://bucket` URL **or** a local
  directory, parsed with `parse_curated_data_location`), replacing the local-only
  `--object-store-dir`. Manifests/CSVs are read from `<root>/manifests/ingest/...` and
  `<root>/csv/source=x-sense/export_date=.../.../<file>.csv`. `s3://` roots use
  `curated_dataset.configure_r2_access`; local roots read the filesystem (the test path).
- A **watermark** = max sensor-reading timestamp in the existing curated parquet is computed.
  With `OVERLAP_DAYS = 2` (a module constant, the one tunable), only accepted CSVs whose
  `export_date >= watermark.date() − OVERLAP_DAYS` are downloaded and parsed. An empty existing
  parquet (cold start) ingests all accepted CSVs.
- The accepted-CSV gate is preserved (manifest `status == "accepted"`, attachment
  `status == "extracted"`, `csv_object_key` present). For an incremental run only manifests
  with `received_date >= cutoff_date` need reading; `--rebuild-all` reads all.
- Newly-parsed readings are merged into the existing readings with the **unchanged**
  `merge_sensor_readings` dedup-by-(location, timestamp), then written and returned as today.
  `SensorReading` shape and `sensor_location_for_filename` are unchanged.
- A `--rebuild-all` flag ignores the watermark and parses every accepted CSV (still
  merged/deduped against the existing parquet).
- Weather/rain fetch is untouched (`dataset_start`/`dataset_end` still span the full merged
  history).
- Timings/counts extended so the saving is visible: report the watermark/cutoff and
  `selected_csv_count` vs the total accepted count (alongside the existing counts on
  `HostedCurationResult` and the CLI timing record).
- Tests, all against a **local** object-store fixture (no network):
  - **Equivalence (primary):** full rebuild from empty vs incremental run seeded with a parquet
    covering the earlier days produce **identical** curated sensor rows.
  - **Selection:** only `export_date >= cutoff` CSVs are parsed; older skipped.
  - **Idempotence:** a second incremental run with no new CSVs changes no sensor rows.
  - **Cold start:** empty existing parquet ingests all accepted CSVs.
  - **`--rebuild-all`:** with a non-empty watermark, still parses every accepted CSV.
  - **Accepted gate:** non-accepted manifest / non-extracted attachment excluded (unchanged).
- `ruff` clean, full suite green.

Notes:

- Prefer DuckDB (already the R2 tool via `configure_r2_access`) for reading manifest JSON and
  CSVs from `s3://` by glob over the recent partitions; keeping the existing Python parsing is
  acceptable if no new heavyweight dependency is added and the local-fixture path still works.
- No new parquet columns, no R2 data migration — the watermark is derived.
- The old `--object-store-dir` + bulk-download workflow contract goes away in issue 02; keep
  this issue's CLI change and issue 02's YAML change consistent (same `--object-store-root`).
