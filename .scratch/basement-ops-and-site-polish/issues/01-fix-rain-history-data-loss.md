# Fix rain and weather history data loss in hosted curation

Type: task
Parent: ../map.md
Status: resolved

## Question

Stop the nightly hosted curation discarding history that the upstream APIs no longer serve.

Facts from the 2026-07-07 review: the EA flood-monitoring API (station `270397`) retains only
~4 weeks of 15-minute readings, and `curate_accepted_email_csvs`
(`src/basement_analysis/hosted_curation.py`) replaces the `rain_readings` and `weather_hours`
partitions wholesale with each fresh API response — `existing_dataset.rain_readings` is loaded but
never merged. The hosted rain dataset is therefore a rolling one-month window and loses a day of
history every night. Rain-correlated ingress is a core analytical hypothesis, so this history
matters.

Resolve when:

- Rain readings merge existing curated rows with fresh API rows, deduplicated by timestamp
  (mirror the `merge_sensor_readings` approach), fresh rows winning on conflict.
- Weather hours get the same merge-don't-replace policy as cheap insurance against a partial
  Open-Meteo response rewriting six months of history (Open-Meteo revisions still propagate
  because fresh rows win).
- `numeric_sequence` in `static_site.py` no longer coerces `None` API values to `0.0` — null
  hours are skipped (or the row dropped), never fabricated as 0°C/0%RH readings.
- Tests cover the merge behavior (old rows outside the API window survive; overlapping rows take
  the fresh value; null API values don't produce readings).
- A local `curate-ingested-r2` run against the R2 mirror confirms rain months present before the
  run are still present after.

## Answer

Fixed on 2026-07-08. The nightly hosted curation now merges rain and weather history instead of
replacing it, and null Open-Meteo hours are dropped instead of fabricated as zeros.

What changed:

- `curate_accepted_email_csvs` (`src/basement_analysis/hosted_curation.py`) now merges
  `existing_dataset.rain_readings`/`existing_dataset.weather_hours` with the fresh API responses
  via new `merge_rain_readings` / `merge_weather_hours` helpers — deduplicated by timestamp,
  fresh rows winning on conflict (so Open-Meteo revisions still propagate), mirroring
  `merge_sensor_readings`.
- `numeric_sequence` in `src/basement_analysis/static_site.py` became
  `nullable_numeric_sequence` returning `list[float | None]`; `fetch_open_meteo_weather` drops
  any hour where any of the five hourly fields is null, so un-backfilled archive hours can never
  land as 0°C/0%RH/0mm readings.
- Tests: `test_hosted_curation.py` covers both merge helpers (old rows outside the API window
  survive; overlapping timestamps take the fresh value) and the end-to-end curation now asserts
  June rain/weather rows survive a July-window API response; `test_static_site_summary.py`
  covers null-hour dropping. Full suite, Ruff, and Pyright all pass.

Verification against live R2 (2026-07-08): before the run the hosted parquet held 2,773 rain
rows spanning 2026-06-08 → 2026-07-07. A local `curate-ingested-r2` run (fresh API fetches,
existing root `s3://$R2_BUCKET/parquet`, mirror `build/ticket-43-r2-pipeline`, output
`build/ticket-01-curated-r2-parquet`) fetched only 2,677 fresh EA readings (2026-06-09 → 2026-07-06 —
the API window has already moved past June 8) yet the merged output still held all 2,773 rows
including the pre-window day. The old replace behavior would have written 2,677 rows and lost
that day. Weather hours (2026-02-13 → 2026-07-06, 3,456 rows) were preserved unchanged. Both
June and July rain months present before the run are present after.
