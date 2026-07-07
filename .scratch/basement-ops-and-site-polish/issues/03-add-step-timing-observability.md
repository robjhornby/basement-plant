# Add step-timing observability and a build-info record

Type: task
Parent: ../map.md

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
