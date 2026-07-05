# Hosted processing and static generation decision tree

Research date: 2026-07-05

## Question

What hosted basement data-processing and static dashboard/report generation stack should be
considered now that the previous prototype showed normal Python DuckDB is not viable in a standard
Cloudflare Python Worker?

This is decision-tree research for the next grilling checkpoint, not a final architecture decision.

## Current local baseline

The local production baseline is `uv run basement`, which imports `duckdb>=1.5.4`,
`numpy>=2.5.1`, and `polars>=1.42.1` from `pyproject.toml`. It builds static HTML pages through
`src/basement_analysis/static_site.py` and `src/basement_analysis/summaries.py`.

That matters because there are two different kinds of hosted solution:

- Preserve the existing Python analysis path and run it in a normal Linux/Python environment.
- Reimplement or narrow hosted work so Workers only ingest, validate, summarize, orchestrate, or
  publish small artifacts.

## Decision tree

### 1. Must hosted analysis run the existing Python stack unchanged?

Capability test: can the hosted runtime run `uv`, normal CPython package wheels, DuckDB Python,
Polars, NumPy, and later possible MetroloPy work with the same semantics as the local path?

Likely answer: only Cloudflare Containers satisfy this directly. Standard Cloudflare Python
Workers do not.

Evidence:

- Cloudflare Python Workers are in beta and require the `python_workers` compatibility flag.
  Cloudflare's package docs say Python Workers support pure Python packages from PyPI and packages
  included in Pyodide; packages that are neither pure Python nor supported in Pyodide require a
  support request.
  Source: <https://developers.cloudflare.com/workers/languages/python/> and
  <https://developers.cloudflare.com/workers/languages/python/packages/>
- Workers limits still apply: paid Workers have 128 MB isolate memory, 10 MB compressed Worker
  size, 1 second startup time, and default 30 seconds CPU configurable up to 5 minutes.
  Source: <https://developers.cloudflare.com/workers/platform/limits/>
- Current Pyodide package list includes `duckdb 1.5.1`, `numpy 2.4.3`, `polars 1.33.1`,
  `pandas 3.0.2`, `pyarrow 22.0.0`, `scipy 1.18.0`, `matplotlib 3.10.8`, and `ipython 9.12.0`.
  It did not show a `metrolopy` package entry. Those are not the repo's current local pins.
  Source: <https://pyodide.org/en/stable/usage/packages-in-pyodide.html>
- The previous prototype failed because `duckdb>=1.5.4` and the hinted `duckdb==1.6.0.dev280`
  had no usable wheel for `cpython-3.13.2-emscripten-wasm32-musl`.
  Source: [Verify Python DuckDB on Cloudflare Workers](../issues/28-verify-python-duckdb-on-cloudflare-workers.md)

Tradeoffs:

- Python Worker plus Pyodide could be useful only if the project deliberately pins/reworks around
  Pyodide's package set, avoids the current local version requirements, and proves memory/bundle
  behavior. That would make hosted behavior diverge from `uv run basement`.
- Containers preserve the local programming model and normal dependency resolution, but add Docker
  images, Durable Object/container lifecycle, container cold start, explicit R2 transfer patterns,
  and paid-plan operational complexity.

Risk:

- A Python Worker might import some relevant packages today but still fail at the combined
  workload because package versions, Wasm memory, Worker bundle size, filesystem behavior, and
  startup time are all material.

Follow-up:

- If preserving `uv run basement` behavior is the priority, prototype
  [Prototype Cloudflare Container DuckDB analysis job](../issues/32-prototype-cloudflare-container-duckdb-analysis-job.md)
  after the infrastructure-as-code ticket is resolved.
- Do not spend more effort on Python Workers unless the user explicitly accepts a Pyodide-specific
  hosted analysis variant.

### 2. Can a JavaScript/TypeScript Worker own hosted processing?

Capability test: can a Worker do the daily email/CSV parsing, dedupe/state updates, small
aggregations, and publication without full DuckDB/Polars/Python analysis?

Likely answer: yes for ingestion, validation, manifest updates, and small static/JSON artifacts;
no for a faithful full replacement of the current physical analysis/reporting path.

Evidence:

- Workers have direct R2 bindings for object `get`, `put`, `delete`, and lexicographic `list`,
  including paginated listing and stream/arrayBuffer object reads.
  Source: <https://developers.cloudflare.com/r2/api/workers/workers-api-reference/>
- Workers limits are tight for analytical runtimes: 128 MB memory per isolate, 10 MB compressed
  script size on paid plans, 1 second startup, 6 simultaneous outgoing connections, and CPU limits
  as above.
  Source: <https://developers.cloudflare.com/workers/platform/limits/>
- Arquero is a JavaScript table transformation library for array-backed data tables, with filtering,
  aggregation, windows, joins, reshaping, and Arrow column support. The current npm package is small
  compared with DuckDB-Wasm.
  Source: <https://idl.uw.edu/arquero/> and <https://www.npmjs.com/package/arquero>

Tradeoffs:

- This is the simplest Cloudflare-native path if hosted work is kept small.
- It creates a second implementation of analytical transforms if it tries to replace the Python
  path. That risks divergence in physics, caveats, uncertainty handling, and report text.
- It fits deterministic object keys and small manifest objects well.

Risk:

- Once JS Workers do more than parsing/state/small summaries, the project will have two analytical
  implementations to test and explain.

Follow-up:

- Use JS/TS Workers for the email-to-R2 ingest path regardless of the heavy-analysis decision.
- Consider a JS-only hosted processor only if the user accepts a smaller hosted dashboard and keeps
  full report generation local or in a separate normal-Python runner.

### 3. Can DuckDB-Wasm make a Worker analytical enough?

Capability test: can a JS Worker bundle or load DuckDB-Wasm, read R2 CSV/Parquet, run the necessary
queries, and publish static artifacts inside Worker memory, bundle, and startup limits?

Likely answer: possible enough to prototype, not safe enough to assume.

Evidence:

- DuckDB-Wasm deployment needs multiple components: the main TypeScript/JavaScript library, a JS
  Worker component, a WebAssembly module, and any relevant extensions. The DuckDB docs describe
  different Wasm/worker variants and extension hosting concerns.
  Source: <https://duckdb.org/docs/lts/clients/wasm/deploying_duckdb_wasm.html>
- The current `@duckdb/duckdb-wasm` npm package reports an unpacked size of about 149 MB via
  `npm view @duckdb/duckdb-wasm dist.unpackedSize`, which does not directly equal compressed Worker
  bundle size but signals asset and deployment friction.
  Source: <https://www.npmjs.com/package/@duckdb/duckdb-wasm>
- Worker memory is 128 MB including WebAssembly allocations.
  Source: <https://developers.cloudflare.com/workers/platform/limits/>

Tradeoffs:

- It preserves some SQL/Parquet ergonomics without Containers.
- It is not the same as the normal Python DuckDB path, does not preserve Polars/Python report code,
  and will require careful worker/wasm asset handling.
- It may be more attractive for a client-side static dashboard exploration path than for the
  server-side hosted analysis job.

Risk:

- Memory and startup behavior can fail even if bundling succeeds. R2 object buffering can also
  exceed isolate memory if implemented naively.

Follow-up:

- Prototype only if the grilling checkpoint chooses a "stay in Workers at all costs" branch.
- The prototype should be minimal: fetch one small R2 object, run one aggregate, and write one JSON
  artifact.

### 4. Do Containers solve the heavy hosted analysis job?

Capability test: can Cloudflare run a normal container image with Python, DuckDB, Polars, local
package tooling, R2 access, and enough memory/disk for a daily batch job?

Likely answer: yes, with meaningful operational complexity.

Evidence:

- Cloudflare Containers run code in any programming language, full filesystem/runtime/Linux-like
  environments, and existing container images as part of apps built on Workers.
  Source: <https://developers.cloudflare.com/containers/>
- Container instance types range from `lite` at 1/16 vCPU, 256 MiB memory, and 2 GB disk through
  `standard-4` at 4 vCPU, 12 GiB memory, and 20 GB disk.
  Source: <https://developers.cloudflare.com/containers/platform-details/limits/>
- Containers are controlled from Workers code, with `sleepAfter` style lifecycle control in the
  documented examples. They require Durable Object bindings/migrations in the Worker configuration.
  Source: <https://developers.cloudflare.com/containers/>

Tradeoffs:

- Best fit for preserving `uv run basement`, normal DuckDB, Polars, PyArrow, and later possible
  MetroloPy/report-generation work.
- Keeps hosted processing Cloudflare-owned while avoiding Pyodide and Worker isolate limits.
- Adds Docker build/deploy, image size management, startup/lifecycle behavior, secret handling, and
  R2 object transfer choices. Container disk should be treated as ephemeral scratch unless docs and
  prototype prove otherwise for a specific pattern.

Risk:

- Overkill if daily processing can be reduced to a tiny summary. Operational surface can dominate
  the project before the analysis itself is stable.

Follow-up:

- If the user chooses fidelity/reuse over minimal Cloudflare-native simplicity, continue with
  [Prototype Cloudflare Container DuckDB analysis job](../issues/32-prototype-cloudflare-container-duckdb-analysis-job.md).
- The prototype should prove: normal `uv run basement`-like execution in an image, R2 read/write,
  publication output, secrets/config, cold start, logs, and repeatability.

### 5. Do Workflows, Queues, Durable Objects, D1, Pages, static assets, or Browser Run change the answer?

Capability test: do these surfaces provide heavy analytical compute, or do they mainly orchestrate,
coordinate, persist state, and publish outputs?

Likely answer: they mostly support the chosen compute branch. They do not remove the need to choose
between small Worker processing, Container analysis, or external/local normal-Python analysis.

Evidence and implications:

- Workflows provide durable multi-step execution, retries, sleeps, event waits, and persisted state,
  but each step still inherits Worker-style limits. Step payload/result limits are small enough that
  R2 object keys should be passed, not bulk data.
  Source: <https://developers.cloudflare.com/workflows/> and
  <https://developers.cloudflare.com/workflows/reference/limits/>
- Queues provide delivery, buffering, batching, retries, delays, dead-letter queues, and pull
  consumers. They can trigger work but do not provide a larger analysis runtime by themselves.
  Source: <https://developers.cloudflare.com/queues/> and
  <https://developers.cloudflare.com/queues/platform/limits/>
- Durable Objects are useful for stateful coordination and strongly consistent attached storage.
  They are a natural control plane for Containers, but not a bulk analytical engine.
  Source: <https://developers.cloudflare.com/durable-objects/>
- D1 is managed serverless SQLite for Workers/Pages. It is suitable for small relational state but
  not a replacement for the R2 object lake or Parquet-oriented analysis.
  Source: <https://developers.cloudflare.com/d1/>
- Pages Direct Upload can publish prebuilt static assets with Wrangler. Wrangler Direct Upload
  supports a single folder of assets, with 20,000 file and 25 MiB file limits.
  Source: <https://developers.cloudflare.com/pages/get-started/direct-upload/>
- Worker static assets are also a publication option, with Workers limits listing 100,000 static
  asset files per Worker version on paid plans and 25 MiB individual asset size.
  Source: <https://developers.cloudflare.com/workers/platform/limits/> and
  <https://developers.cloudflare.com/workers/static-assets/>
- Browser Run runs headless Chrome for browser automation, screenshots, PDFs, and scraping. It is
  useful later for PDF/screenshot artifacts, not for the core analysis compute.
  Source: <https://developers.cloudflare.com/browser-rendering/>

Tradeoffs:

- Workflows or Queues can make ingestion and publication reliable, but early implementation can
  probably start with deterministic R2 keys/manifests and add orchestration only when a concrete
  retry/coordination problem appears.
- Pages Direct Upload is a good first publication target if the selected compute branch can call
  Wrangler or the Pages API from a trusted environment. Static assets served by a Worker are also
  viable if the site naturally belongs with the Worker deployment.

Follow-up:

- Keep R2 as the raw/curated/site artifact store and pass object keys between services.
- Avoid D1 by default unless manifests prove insufficient for processing state or audit queries.
- Decide Pages Direct Upload versus Worker static assets in the static-publication ticket, not in
  the heavy-compute decision.

### 6. Should heavy generation stay local, in CI, or in an external scheduled runner?

Capability test: is "Cloudflare-only after email receipt" more important than keeping the
implementation very simple and faithful to local Python?

Likely answer: this is a user preference question, not a technical blocker.

Options:

- Local/manual heavy generation: Cloudflare receives and stores raw/curated data; the owner runs
  `uv run basement` locally and publishes static output. This is simplest and most reproducible but
  not fully automated.
- GitHub Actions or another CI runner: normal Python stack, scheduled or manually triggered, reads
  R2 through credentials, writes Pages/static artifacts. This is operationally familiar and avoids
  Containers, but violates the current Cloudflare-only preference after ingestion.
- Cloudflare Container: fully Cloudflare-owned and faithful to local Python, with more platform
  surface to manage.
- JS Worker only: most Cloudflare-native and low-ops, but likely requires a smaller hosted analysis
  or duplicate analytical implementation.

Risk:

- The project can waste time proving a fully Cloudflare-native runtime before the dashboard/report
  product direction has stabilized. The current map explicitly wants short cycles through visible
  data and plots.

Follow-up:

- The next grilling checkpoint should ask whether the hosted path must be fully Cloudflare-owned
  now, or whether Cloudflare ingestion plus normal-Python generation elsewhere is acceptable as an
  interim.

## Recommended next grilling checkpoint

Ask the user to choose the first prototype branch by answering this tradeoff:

> Is preserving the exact `uv run basement` analysis/report behavior more important than keeping
> hosted processing small and Cloudflare-native?

If yes, proceed toward Containers: Worker/Workflow or Durable Object control plane, Container
running normal Python, R2 for raw/curated/site artifacts, and Pages or Worker static assets for
publication.

If no, proceed toward a small JS/TS Worker path: Email Worker extracts CSVs, writes raw/extracted
objects and manifests to R2, computes only lightweight freshness/summary JSON or minimal static
HTML, and leaves full physical analysis/report generation local, in CI, or for a later Container.

## Practical recommendation for the map

Do not silently harden the architecture here. Keep
[Grill hosted processing stack decision](../issues/34-grill-hosted-processing-stack-decision.md)
as the next frontier ticket. It should decide:

- whether "Cloudflare-only" is a hard rule for heavy analysis now;
- whether code reuse/fidelity to `uv run basement` outranks operational simplicity;
- whether the first hosted dashboard can be smaller than the local report;
- whether Containers are acceptable before durable infra is provisioned;
- whether CI/local generation is allowed as an interim path.

