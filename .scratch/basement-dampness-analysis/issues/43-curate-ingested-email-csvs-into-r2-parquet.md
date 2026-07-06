# Curate ingested email CSVs into R2 Parquet

Type: task
Status: open
Parent: ../map.md
Blocked by: 42

## Question

The GitHub Actions runner from
[Implement GitHub Actions analysis runner](42-implement-github-actions-analysis-runner.md)
rebuilds the site from the curated Parquet snapshot that was uploaded once from a local build.
New daily X-Sense emails land as raw `.eml` + CSV objects + manifests in `basement-pipeline`
(via the email-ingest Worker), but nothing curates them into `parquet/`, so the published site
does not yet track new data.

Extend the hosted pipeline so scheduled runs curate before they render:

- Read accepted-manifest CSV objects from R2, parse them with the existing sensor-CSV parser,
  and merge them into the partitioned `parquet/` layout idempotently (manifests/content hashes
  decide what is new; no database, per the standing preference).
- Refresh Open-Meteo and EA rainfall data for the extended date window inside the runner
  (`--refresh-weather` semantics; decide caching between runs).
- Decide where curation happens: an earlier step in the same workflow versus a separate
  workflow, and whether the local `write_curated_dataset` (currently local-directory-only)
  grows an R2 write path or writes locally then syncs up.
- Reconsider `repository_dispatch` from the email-ingest Worker once curation exists, so a new
  email triggers curate-plus-publish instead of waiting for the daily cron.

Resolve when a day's real emailed CSVs flow to the published site with no local machine
involved.
