# Cloudflare Container DuckDB Analysis Prototype

Status: throwaway prototype for
`Prototype Cloudflare Container DuckDB analysis job`.

## Question

Can a Cloudflare Container run the Python plus DuckDB analysis shape against partitioned Parquet
objects in R2, generate representative static publication artifacts, and write those artifacts back
to an R2-shaped destination?

## Commands

Run the local simulation from this directory:

```bash
uv run python prototype.py
```

The default command reads the existing curated dataset at
`../../build/basement-site/curated-data` and writes representative site artifacts to:

```text
build/site-output/site/prototypes/container-analysis/index.html
build/site-output/site/prototypes/container-analysis/manifest.json
```

Build the container image when a Docker daemon is available:

```bash
docker build -t basement-analysis-container-prototype .
docker run --rm \
  -v "$PWD/../../build/basement-site/curated-data:/data/curated:ro" \
  basement-analysis-container-prototype \
  --parquet-root /data/curated
```

Run the image in Worker-compatible HTTP trigger mode:

```bash
docker run --rm -p 8080:8080 \
  -v "$PWD/../../build/basement-site/curated-data:/data/curated:ro" \
  basement-analysis-container-prototype \
  --serve --host 0.0.0.0 --port 8080 --parquet-root /data/curated

curl -X POST http://localhost:8080/run
```

Run against real R2 with read/write credentials:

```bash
PROTOTYPE_MODE=r2 \
R2_BUCKET=basement-pipeline \
R2_PARQUET_PREFIX=parquet \
R2_ENDPOINT_URL=https://<ACCOUNT_ID>.r2.cloudflarestorage.com \
R2_ACCESS_KEY_ID=<ACCESS_KEY_ID> \
R2_SECRET_ACCESS_KEY=<SECRET_ACCESS_KEY> \
uv run python prototype.py
```

## Cloudflare control-plane sketch

`wrangler.toml` and `worker/src/index.ts` show the intended Worker-owned Container shape:

- Wrangler owns the deployable Worker/Container project.
- `AnalysisContainer` extends Cloudflare's `Container` Durable Object class.
- A Worker request gets the named `daily-analysis` container and forwards a trigger request to it.
- The actual batch job remains normal Python with `uv`, DuckDB, and R2/S3-compatible credentials.

The sketch is intentionally not wired into durable infrastructure yet.

## Current result

Local `uv` execution proves the normal Python/DuckDB package/runtime path and representative
artifact generation against the production curated Parquet layout. The same job also has a tiny
HTTP trigger mode (`POST /run`) so a Worker-owned Container can invoke it.

The local run generated:

- `build/site-output/site/prototypes/container-analysis/index.html`
- `build/site-output/site/prototypes/container-analysis/manifest.json`

The Docker daemon was not running in this session, so image build, cold start, memory/disk limits
inside a real container, and `wrangler dev`/Cloudflare deployment remain unproven.

## Provisional verdict

Cloudflare Containers remain the right next hosted compute surface if the project keeps the
current priority of Python/`uv` analysis runtime parity. The local prototype did not expose a
Python or DuckDB blocker, and Cloudflare's current Container model is explicitly meant for normal
runtime/filesystem/Linux-like workloads that exceed Worker isolate limits.

Before creating durable Container infrastructure, run the same prototype with:

- a running Docker daemon;
- real R2 credentials scoped to the prototype bucket/prefix;
- `npx wrangler dev` for local Worker/Container routing;
- one deployed Cloudflare Container smoke test on the `basic` instance type.

If the deployed smoke test fails on R2 access, startup time, image size, logs, or cost controls,
fall back to keeping heavy generation in an external normal-Python runner while Workers continue
to own ingestion and R2 state.
