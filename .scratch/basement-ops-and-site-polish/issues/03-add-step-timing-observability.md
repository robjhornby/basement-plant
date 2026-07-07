# Add step-timing observability and a build-info record

Type: task
Parent: ../map.md
Status: resolved

## Question

Make it possible to answer "which parts of the pipeline are slowest?" and "is the site fresh?"
without guesswork (agreed scope: timings plus a build-info/freshness record; no alerting).

Resolve when:

- The Python CLI phases (CSV load, weather/rain fetch, curated-parquet write, DuckDB read,
  summary build, render, publish inputs) log wall-clock durations in both local and GitHub
  Actions runs, using stdlib logging with simple structured output — no new heavyweight
  dependencies.
- The GitHub Actions run surfaces those timings legibly (job summary or clearly grouped log
  lines).
- Each hosted build writes a small build-info record (e.g. `site/build-info.json` in the site
  bucket or alongside the parquet): run timestamp, row counts merged, newest sensor reading
  timestamp, per-phase durations. Whether/how the site displays freshness stays in fog — this
  ticket only guarantees the record exists.
- The timings from one real nightly/dispatch run are pasted into this ticket's answer, so the
  efficiency assessment (issue 04) starts from data.

## Answer

Implemented and verified on 2026-07-08. Landed on `main` via
https://github.com/robjhornby/basement-plant/pull/2 (merge commit `e041c78`), with a green
`workflow_dispatch` run:
https://github.com/robjhornby/basement-plant/actions/runs/28905833847.

What changed:

- Added `src/basement_analysis/observability.py` with a stdlib `PhaseRecorder`, per-command
  timing JSON records, build-info writing, and markdown rendering for GitHub Actions summaries.
- `curate-ingested-r2` now records phases for existing Parquet load, accepted CSV staging/load,
  sensor merge, Open-Meteo fetch, Environment Agency rainfall fetch, and curated Parquet write.
- `build-site` now records phases for curated Parquet load (or local CSV/API/Parquet rebuild
  phases), summary build, render, and site write; it also writes `build-info.json` containing
  generated time, newest sensor timestamp, row counts, and all command timing records.
- `.github/workflows/basement-site.yml` now writes timings under `build/timings`, uploads
  `build-info.json` to the `basement-site` R2 bucket, and appends a timings markdown report to
  `$GITHUB_STEP_SUMMARY`.
- Tests cover timing record round-trips, malformed timing records, build-info JSON, markdown
  rendering, the `timings-summary` command, and the `build-site` CLI integration.

Verification:

- `uv run pytest` — 32 passed.
- `uv run ruff check .` — passed.
- `uv run ruff format --check .` — passed.
- `uv run pyright` — 0 errors.
- GitHub Actions dispatch run `28905833847` — success in 42s, including publish and job-summary
  timing step.

Published `build-info.json` from the dispatch run:

```text
generated_at: 2026-07-07T23:28:13+00:00
newest_sensor_reading: 2026-07-06T23:59
sensor_row_count: 583,981
weather_hour_count: 3,456
rain_reading_count: 2,677
```

Dispatch timing sample for issue 04:

| Command | Phase | Duration (s) |
| --- | --- | ---: |
| `curate-ingested-r2` | load-existing-curated-parquet | 6.020 |
| `curate-ingested-r2` | stage-accepted-csvs | 0.002 |
| `curate-ingested-r2` | load-staged-sensor-csvs | 0.115 |
| `curate-ingested-r2` | merge-sensor-readings | 0.389 |
| `curate-ingested-r2` | fetch-open-meteo-weather | 0.740 |
| `curate-ingested-r2` | fetch-environment-agency-rainfall | 5.155 |
| `curate-ingested-r2` | write-curated-parquet | 0.864 |
| `build-site` | load-curated-parquet | 7.107 |
| `build-site` | build-summary | 0.478 |
| `build-site` | render-site | 0.031 |
| `build-site` | write-site | 0.001 |

Timed phases total: `curate-ingested-r2` 13.285s, `build-site` 7.617s. Job wall-clock total:
42s. Counts: 9 accepted CSV objects, 12,960 staged sensor rows, 583,981 existing/merged sensor
rows, 3,456 weather hours, 2,677 rain readings.
