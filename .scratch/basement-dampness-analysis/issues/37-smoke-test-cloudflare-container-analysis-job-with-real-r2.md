# Smoke test Cloudflare Container analysis job with real R2

Type: task
Status: open
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

