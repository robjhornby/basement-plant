# Implement GitHub Actions analysis runner

Type: task
Status: claimed
Parent: ../map.md
Blocked by: 37

## Question

Stand up the chosen free-plan hosted analysis compute: a GitHub Actions workflow that runs the
unchanged Python/`uv` analysis against R2 and writes the rendered static site back to R2,
replacing the rejected Cloudflare Container path from
[Smoke test Cloudflare Container analysis job with real R2](37-smoke-test-cloudflare-container-analysis-job-with-real-r2.md).

Scope:

- First, validate the data path locally: with the user-created R2 API token (Object Read &
  Write scoped to `basement-pipeline`), run the container prototype's `PROTOTYPE_MODE=r2` mode —
  real DuckDB reads from the existing `parquet/` prefix and artifact writes back to an R2
  prefix. This is the DuckDB-over-R2 leg deferred from ticket 37 and is identical for any
  external runner.
- Add a workflow under `.github/workflows/` that runs the analysis/static-site job on a daily
  schedule and on `workflow_dispatch`; decide whether to also wire `repository_dispatch` from
  the email-ingest Worker for event-driven publishes now or defer it to the fog.
- Store the R2 S3 credentials as GitHub Actions encrypted secrets; keep names aligned with the
  local `.envrc` (`R2_ENDPOINT_URL`, `R2_ACCESS_KEY_ID`, `R2_SECRET_ACCESS_KEY`, `R2_BUCKET`).
- Decide where the runner writes the rendered site: the dedicated site bucket from
  [Implement site publication bucket and Worker](39-implement-site-publication-bucket-and-worker.md)
  once it exists, with a `basement-pipeline` prefix acceptable as an interim smoke-test target.
  Coordinate the token's bucket scope accordingly (one token covering both buckets, or a second
  token, keeping least privilege).
- Confirm the repo is on GitHub with Actions available, and that a daily run fits comfortably
  in the free minutes budget.

Resolve with a green scheduled/dispatched run that reads real R2 Parquet and publishes site
artifacts to R2, plus any facts later tickets depend on (workflow file path, secret names,
observed run duration).

## Comments

### 2026-07-06 — data path proven, workflow written; blocked on repo publication decision

- **DuckDB-over-R2 validated** (the leg deferred from ticket 37): `PROTOTYPE_MODE=r2` read all
  571,021 sensor rows directly from `s3://basement-pipeline/parquet` in ~4 s with the new
  Object Read & Write token, wrote artifacts to `site/prototypes/container-analysis/`, and the
  manifest read back from R2 correctly.
- **Full workflow body dry-run locally**, step for step: `aws s3 sync` pulled the 28 Parquet
  files from R2, `uv run basement --reuse-curated` built the production site from them
  (identical row counts to a local build), and `aws s3 sync` published the two HTML pages to
  `s3://basement-pipeline/site/basement-site/` (interim prefix until ticket 39's site bucket).
- **Workflow written**: `.github/workflows/basement-site.yml` — daily cron 06:30 UTC plus
  `workflow_dispatch`, `astral-sh/setup-uv` with cache, aws-cli R2 checksum workaround
  (`AWS_REQUEST_CHECKSUM_CALCULATION=when_required`), 15-minute timeout, single-flight
  concurrency group. Secrets expected: `R2_ENDPOINT_URL`, `R2_ACCESS_KEY_ID`,
  `R2_SECRET_ACCESS_KEY`, `R2_BUCKET` (names match the local `.envrc`).
- `repository_dispatch` from the email-ingest Worker is deferred; the daily cron suffices for
  daily emails.
- Surfaced follow-on for resolution time: daily runs currently rebuild from the *uploaded
  snapshot* of curated Parquet; a later ticket must make the hosted pipeline curate newly
  ingested email CSVs (and refreshed weather) into `parquet/` so the site tracks new data.
- **Blocked on the user**: the repo has no GitHub remote. Need a decision to create the GitHub
  repo (name/visibility — note the whole history including `data/*.csv` home sensor data and
  `.scratch/` notes gets pushed) before `git push`, `gh secret set`, first dispatch, and green
  verification.

### 2026-07-07 — DuckDB now reads Parquet straight from R2; user chose a public repo

- The user rejected the sync-down copy as an antipattern, so `basement --curated-data-dir` now
  accepts an `s3://bucket/prefix` location and DuckDB reads the partitioned Parquet directly
  from R2 (httpfs, `s3_endpoint`/keys from `R2_ENDPOINT_URL`, `R2_ACCESS_KEY_ID`,
  `R2_SECRET_ACCESS_KEY`; `s3_url_style=path`, region `auto`). An s3:// location requires
  `--reuse-curated`; rebuilding curated data still needs a local directory and fails with a
  clear message otherwise.
- Ruff, strict Pyright, and all 13 tests pass (new tests cover location parsing, path joining,
  the missing-credentials error, and the s3-rebuild guard). Real end-to-end run:
  `uv run basement --reuse-curated --curated-data-dir s3://basement-pipeline/parquet` renders
  byte-identical HTML to the synced-copy build except the generated-at timestamp.
- `.github/workflows/basement-site.yml` no longer syncs Parquet down; the build step passes the
  s3:// location and the R2_* env vars. `aws s3 sync` remains only for publishing the rendered
  HTML to `site/basement-site/`.
- Repo decision: **public** under `robjhornby`, `.scratch/` stays in for now (GH issues later).
  Pre-publication audit: no `.envrc`/tfstate/tfvars/`.eml`/`data/` ever committed, no secrets or
  account IDs in tracked files, email fixtures synthetic. Conscious disclosures going public:
  home-area coordinates `51.47, -0.97` in `static_site.py` and `.scratch` research notes, the
  `basement-ingest@robjhornby.com` address in tickets, and commit author identity.
- GitHub note for later: scheduled workflows on public repos are auto-disabled after 60 days
  without repo activity; the daily commit-free cron needs occasional activity or a re-enable.
