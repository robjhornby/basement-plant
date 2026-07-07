# Curate ingested email CSVs into R2 Parquet

Type: task
Status: resolved
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

## Answer

The hosted pipeline now curates accepted email CSVs into R2 Parquet before every scheduled or
manual site publish. The implementation landed in two commits on `main`:

- `4adf835` (`Curate ingested CSVs before publishing basement site`) added
  `basement curate-ingested-r2`, hosted curation tests, and workflow steps that mirror accepted
  ingest manifests/CSV objects from `basement-pipeline`, merge them with the existing
  `s3://basement-pipeline/parquet` snapshot, refresh Open-Meteo and EA rainfall data, sync the
  rebuilt deterministic Parquet tree back to R2, then render/publish the site from R2.
- `fb1942e` (`Canonicalize hosted sensor CSV labels`) fixed the production Worker filename shape
  (`Thermo-hygrometer_2_Export_Data_...`) and repairs any already-written fallback labels during
  merge. The cleanup run deleted the temporary bad `thermo-hygrometer*` partitions from R2.

The final GitHub Actions run
<https://github.com/robjhornby/basement-plant/actions/runs/28832891336> passed in 48 seconds with
no local machine in the path:

- accepted CSV objects: 3
- staged sensor rows from real emailed CSVs: 4,320
- merged sensor rows: 575,341
- weather hours: 3,408
- rain readings: 2,582
- published site generation visible at `https://robjhornby.com/basement/`: `2026-07-07 00:32`

Architecture decisions made here:

- Curation stays as an earlier step in the same single-flight `basement-site.yml` workflow rather
  than a separate workflow. This keeps ordering explicit: curate Parquet, sync Parquet, render
  from R2, publish HTML.
- The Python writer remains local-directory-only. The runner writes deterministic local Parquet
  under `build/curated-r2-parquet` and uses `aws s3 sync --delete` to publish it to R2. This is
  simpler than adding an R2 writer abstraction and is safe because object keys are deterministic.
- Weather API responses are refreshed during hosted curation (`--refresh-weather`) rather than
  cached across runs. The current run remains comfortably inside the free Actions budget.
- `repository_dispatch` from the Email Worker remains deferred. The daily cron now has a complete
  curate-plus-publish path, and event-driven publishing should only be added if daily latency is
  actually a problem.
