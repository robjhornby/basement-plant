# Drop the bulk download step; point curation at R2

Type: task
Parent: ../PRD.md
Status: blocked-by-01

## Question

Rewrite the nightly workflow (`.github/workflows/basement-site.yml`) to use the incremental,
R2-native curation from issue 01, deleting the bulk CSV download, per `../PRD.md`.

Resolve when:

- The **"Download accepted ingest manifests and CSVs from R2"** step (the `aws s3 sync` of
  `manifests/ingest` and `csv/source=x-sense` into `build/r2-pipeline`) is **removed**.
- The **"Curate accepted email CSVs into Parquet"** step passes
  `--object-store-root "s3://$R2_BUCKET"` (instead of `--object-store-dir build/r2-pipeline`)
  and keeps `--curated-data-dir`, `--timings-dir`, `--refresh-weather`. The R2 credential env
  vars already present on the publish steps are added to this step so DuckDB can reach R2.
- The publish step (`s3 sync build/curated-r2-parquet s3://$R2_BUCKET/parquet --delete`), the
  site-build step, and the site-publish steps are unchanged.
- A manual `workflow_dispatch` run (or a documented dry-run) shows the download step gone and
  the curate step reading only recent CSVs from R2, with the site still building and publishing.

Notes:

- Blocked by issue 01 (the CLI must accept `--object-store-root` first).
- This is the step that visibly answers "the download step is unnecessary/slow" — after this,
  there is no full-history download in the nightly run.
- `aws-cli` stays for the **publish** steps (curated parquet + site HTML/assets to R2); only the
  download step is retired.
