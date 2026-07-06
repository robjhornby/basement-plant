# Smoke test Cloudflare Container analysis job with real R2

Type: task
Status: resolved
Parent: ../map.md
Blocked by: 32

## Question

Using the throwaway prototype from
[Prototype Cloudflare Container DuckDB analysis job](32-prototype-cloudflare-container-duckdb-analysis-job.md),
run the smallest real Cloudflare/R2 smoke test needed before promoting an `analysis-container`
Worker project into durable infrastructure.

Prove or reject:

- Docker image build from `prototypes/cloudflare-container-duckdb-analysis/Dockerfile`.
- Local Worker-to-Container routing with `npx wrangler dev` and `POST /run`.
- Direct DuckDB reads from real R2 partitioned Parquet via the S3-compatible endpoint.
- Static artifact writes back to an R2 prefix.
- One deployed Cloudflare Container run on the smallest plausible instance type, starting with
  `basic` unless the local artifact sizes already require more.
- Startup time, logs, image size, memory, disk, CPU, and rough cost controls are acceptable for a
  daily basement analysis batch job.

Resolve with whether to promote the prototype into `infra/cloudflare/workers/analysis-container/`,
adjust the Container shape, or fall back to an external normal-Python runner while keeping Workers
focused on ingestion and R2 state.

## Comments

### 2026-07-06 — local legs all pass; deployed/R2 legs blocked on account access

Everything provable without Cloudflare credentials passed this session (details in
[Cloudflare Container DuckDB Analysis Prototype](../../../prototypes/cloudflare-container-duckdb-analysis/NOTES.md),
"Smoke test results"):

- **Docker image build**: passes — ~14 s build, 277 MB image.
- **Containerized batch run** against curated Parquet: passes — identical summary to the local
  `uv` run (571,021 sensor rows), under 1 s.
- **HTTP trigger mode**: passes — `POST /run` in ~160 ms, ~92 MiB idle RSS, comfortably inside
  the `basic` instance type (likely `lite`-compatible).
- **`npx wrangler dev` Worker-to-Container routing**: passes — cold `POST /run` runs the full
  analysis in 2.4 s, warm in ~50 ms. Required enabling Docker Desktop's Rosetta amd64 emulation
  (now enabled on this machine); wrangler builds containers for `linux/amd64` and the image
  segfaults under plain QEMU on Apple Silicon.
- The prototype Dockerfile now bakes a 2.3 MB curated-Parquet snapshot into the image so a
  deployed smoke test can run before R2 credentials/bucket exist.

Still blocked, needs the account owner (none of this is scriptable without an interactive
`wrangler login` and billing decisions):

1. `npx wrangler login` on this machine (browser OAuth), and confirm the account has the
   **Workers Paid** plan — Containers require it (~$5/month minimum).

### 2026-07-06 (later) — parquet in R2; deploy blocked on Workers Paid; user reconsidering Containers vs free plan

Progress this session:

- `wrangler login` is done and the curated Parquet snapshot (28 files, 2.3 MB) is uploaded to
  `basement-pipeline` under the `parquet/` prefix (user approved), mirroring the local
  Hive-partitioned layout. The DuckDB-over-R2 read leg now only needs S3 credentials.
- `npx wrangler deploy` built the amd64 image but failed with 401 Unauthorized on
  `GET /accounts/{account_id}/containers/me` — the account is not enrolled for Containers,
  which requires the **Workers Paid** plan (~$5/month). This is the concrete cost trigger.
- On learning that Containers alone force the paid plan, the user asked to re-examine free-plan
  alternatives before committing, explicitly including rewriting analysis in Rust compiled to
  WASM for free Workers. Confirmed limits (Cloudflare docs, 2026-07-06): free Workers get
  **10 ms CPU per invocation** (HTTP and cron alike), 128 MB memory; paid gets 30 s default /
  5 min HTTP, and **15 min CPU for cron intervals >= 1 hour**.
- Alternatives analysis delivered in-session; the standout free option is a scheduled/dispatched
  GitHub Actions runner executing the unchanged `uv` analysis against R2 — the ticket's named
  "external normal-Python runner" fallback. Rust-in-Worker was assessed as a poor fit (fixed
  10 ms budget vs growing dataset, loses Python/`uv` runtime parity and the MetroloPy stack).
- R2 API token creation steps were handed to the user (Object Read & Write scoped to
  `basement-pipeline`, account token, creds into the gitignored root `.envrc`).

Ticket stays claimed. Next session: run `PROTOTYPE_MODE=r2` once creds exist, and resolve per
the user's compute decision — promote Containers (paid) or fall back to the external runner
(free) with Workers keeping ingestion/state/publication.

## Answer

**Fall back to an external normal-Python runner — specifically a GitHub Actions workflow —
instead of promoting the Container prototype.** The user chose this explicitly once the smoke
test surfaced that Cloudflare Containers are the only part of the design requiring the Workers
Paid plan (~$5/month).

What the smoke test established:

- All local legs pass (see earlier comments): Docker image build, containerized batch run
  identical to the local `uv` run, HTTP trigger mode within `basic` instance limits, and
  `wrangler dev` Worker-to-Container routing.
- The deployed leg is hard-blocked at account enrollment: `wrangler deploy` builds and then
  401s on `GET /accounts/{account_id}/containers/me`. Containers require Workers Paid; the
  account is on Free and the user prefers to stay there.
- The curated Parquet snapshot (28 files, 2.3 MB) is uploaded to `basement-pipeline` under
  `parquet/`, so the DuckDB-over-R2 read leg needs only S3 credentials. That validation moves
  to the GitHub Actions runner ticket, since it is identical for any external runner.
- Free Workers (10 ms CPU per invocation, incl. cron) were assessed and rejected for hosting
  the analysis itself, including a Rust/WASM rewrite: a fixed 10 ms budget against a growing
  dataset, and it would abandon the Python/`uv` runtime parity decision from
  [Grill hosted processing stack decision](34-grill-hosted-processing-stack-decision.md) plus
  the MetroloPy uncertainty stack.

Consequences:

- Hosted analysis compute is a GitHub Actions workflow (scheduled, optionally
  `repository_dispatch`-triggered by the email-ingest Worker) running the unchanged `uv`
  analysis: read `parquet/` from R2 via S3 credentials, write the rendered site back to R2.
  Implementation is [Implement GitHub Actions analysis runner](42-implement-github-actions-analysis-runner.md).
- Workers stay free-plan and keep ingestion, R2 state, and site publication
  ([Implement site publication bucket and Worker](39-implement-site-publication-bucket-and-worker.md) is unaffected).
- The Container prototype stays under `prototypes/cloudflare-container-duckdb-analysis/` as a
  proven-up-to-enrollment record; nothing was deployed, so there is nothing to tear down. If
  $5/month ever becomes acceptable, the Container path resumes from that prototype (and Workers
  Paid would also unlock 15-minute-CPU hourly+ cron Workers as a middle option).
2. R2 pipeline bucket + S3-compatible credentials. The bucket is being created under
   [Implement Cloudflare email-to-R2 ingest foundation](36-implement-cloudflare-email-to-r2-ingest-foundation.md)
   (in flight). Then create an R2 API token scoped to that bucket (dashboard → R2 → Manage API
   tokens) and export `R2_ENDPOINT_URL` / `R2_ACCESS_KEY_ID` / `R2_SECRET_ACCESS_KEY` /
   `R2_BUCKET` for the prototype's `PROTOTYPE_MODE=r2` path.
3. Re-invoke this ticket. The remaining automated steps are: upload curated Parquet to the R2
   prefix, run `uv run python prototype.py` in `r2` mode (real DuckDB-over-R2 reads + artifact
   writes), `npx wrangler deploy` from `prototypes/cloudflare-container-duckdb-analysis/`, one
   deployed `POST /run`, capture startup time/logs/cost observations, then tear the deployment
   down and resolve with the promote/adjust/fall-back decision.

