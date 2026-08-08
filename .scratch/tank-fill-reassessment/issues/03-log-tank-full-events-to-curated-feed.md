# Get logged tank-full events into the hosted curated feed

Type: task
Parent: ../PRD.md
Status: ready-for-agent

## Question

The gauge (issue 01) calibrates from logged tank-full events, but the hosted build only sees the
curated `events` dataset in R2 (`source=local_manual`), which currently stops at 2026-07-02 — the
tank-full rows live only in the local `data/basement_events.csv`. Close that gap so the hosted
footer can calibrate.

Resolve when:

- The tank-full rows in `data/basement_events.csv` (Jul 05, 11, 15, 23, 29, and future ones) are
  present in the curated `events` Parquet the hosted site build reads, through whatever path the
  local-manual events already flow (verify how `hosted_curation` / the workflow sources events —
  don't assume).
- Adding a new tank-full line to `basement_events.csv` and rebuilding refreshes the estimate with
  no other manual step — confirm the round trip on a real (or dry-run) build.
- If the curated events genuinely require a schema/pipeline change, that decision and its reason are
  recorded here before implementing.

Note: independent of issues 01/02 — the estimator is testable with events passed directly; this
just makes production data-complete. Sequence it before relying on the live hosted footer.
