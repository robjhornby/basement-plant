# Prototype Cloudflare Container DuckDB analysis job

Type: prototype
Status: resolved
Parent: ../map.md
Blocked by: 31

## Question

Can a Cloudflare Container run the required Python plus DuckDB analysis workflow against Parquet
objects in R2, under realistic deployment, startup, CPU, memory, disk, cost, and orchestration
constraints?

Build the smallest Cloudflare Container prototype, or a locally simulated equivalent that maps
closely to Cloudflare Containers, that runs normal Python with `uv`, imports DuckDB, reads plain
partitioned Parquet directly from R2 through an R2/S3-compatible path, generates representative
static publication artifacts, writes those artifacts back to R2, and identifies how a minimal
Worker control plane would trigger it. Do not include final public static-site publication,
scheduling, retries, alerts, or advanced orchestration in this prototype unless they are required
to prove the runtime path. Use the result to decide whether Containers are the hosted analysis
compute surface, or whether the project should fall back to another Cloudflare-only option.

## Answer

Prototype asset:
[Cloudflare Container DuckDB Analysis Prototype](../../../../prototypes/cloudflare-container-duckdb-analysis/NOTES.md).

Decision:

Use Cloudflare Containers as the provisional hosted analysis compute surface for the next hosted
path. The local simulation did not expose a Python, `uv`, DuckDB, or curated-Parquet query blocker,
and the Worker/Container control-plane shape matches Cloudflare's current Container model closely
enough to continue. Do not yet create durable production Container infrastructure until
[Smoke test Cloudflare Container analysis job with real R2](37-smoke-test-cloudflare-container-analysis-job-with-real-r2.md)
proves the deployed path.

What was built:

- A throwaway prototype under `prototypes/cloudflare-container-duckdb-analysis/`.
- A normal Python/`uv` batch job that imports DuckDB, reads the production curated Hive-style
  Parquet layout, generates representative `index.html` and `manifest.json` site artifacts, and
  can write those artifacts to either a local R2-shaped tree or real R2 through S3-compatible
  credentials.
- A tiny HTTP trigger mode (`POST /run`) so a Worker-owned Container can invoke the same job.
- A Dockerfile using a normal Linux Python image with `uv`.
- A Wrangler/TypeScript control-plane sketch where `AnalysisContainer` extends Cloudflare's
  Container Durable Object class and a Worker forwards trigger requests to a named container.

What was verified in this session:

- `uv run python prototype.py`
- `uv run python prototype.py --help`
- `uv run python prototype.py --serve --port 8097`, then
  `curl -sS -X POST http://127.0.0.1:8097/run`

The local run queried the existing curated dataset:

- 571,021 sensor rows
- 7 event rows
- 3,384 weather hours
- 2,680 rain readings
- sensor window `2026-02-13 19:46:00` to `2026-07-03 12:00:00`

Generated prototype artifacts:

- `prototypes/cloudflare-container-duckdb-analysis/build/site-output/site/prototypes/container-analysis/index.html`
- `prototypes/cloudflare-container-duckdb-analysis/build/site-output/site/prototypes/container-analysis/manifest.json`

What remains unverified:

- Docker image build and container startup, because the Docker CLI is installed but the daemon was
  not running in this session.
- Real R2 direct Parquet reads and R2 site-artifact writes, because no R2 credentials were used.
- `npx wrangler dev` local Worker-to-Container routing.
- A deployed Cloudflare Container smoke test, including startup behavior, logs, image size, memory,
  disk, CPU, and cost controls.

Current Cloudflare documentation supports the direction: Containers are available on Workers Paid,
run normal language runtimes and Linux-like/filesystem workloads, are controlled from Worker code,
use instance types from `lite` through `standard-4`, can be developed locally through Wrangler with
a Docker-compatible engine, and can access R2 either through Worker binding outbound handlers or
through R2's S3-compatible API.
