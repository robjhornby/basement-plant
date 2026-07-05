# Verify Python DuckDB on Cloudflare Workers

Type: prototype
Status: resolved
Parent: ../map.md
Blocked by: 27

## Question

Can a Cloudflare-hosted Python Worker run the required DuckDB workflow against Parquet files in R2
within Cloudflare's runtime, package, CPU, memory, and bundle-size constraints?

Build the smallest deployable or locally simulated Worker that imports the relevant Python packages,
queries one representative Parquet object from R2 or an R2-like fixture, and returns a tiny summary.
If Python DuckDB is not viable, identify the smallest Cloudflare-only fallback, such as DuckDB-Wasm
from a JavaScript/TypeScript Worker or a different Cloudflare compute surface for the heavier
analysis step.

## Answer

Python DuckDB is not viable inside Cloudflare Python Workers for this project as of `2026-07-05`.

Prototype asset:
[Cloudflare Python DuckDB Worker Prototype](../../../../prototypes/cloudflare-python-duckdb-worker/NOTES.md).

What was tested:

- Built a throwaway Python Worker under `prototypes/cloudflare-python-duckdb-worker/`.
- Generated a representative Parquet fixture locally with DuckDB.
- Tried to start the Worker with `uv run pywrangler dev` and `duckdb>=1.5.4`.
- Ran a second dependency-resolution probe using the resolver's hinted DuckDB pre-release.

Result:

- Local DuckDB could create the Parquet fixture, so the data/query shape is not the blocker.
- Cloudflare Python Worker startup failed before serving requests because `duckdb>=1.5.4` had no
  usable wheel for `cpython-3.13.2-emscripten-wasm32-musl`.
- The hinted exact pre-release, `duckdb==1.6.0.dev280`, also had no usable wheel for the same
  target.

Interpretation:

Cloudflare Python Workers run on Pyodide inside the Workers runtime, and Cloudflare package support
depends on pure Python packages, PyEmscripten wheels, or packages included in Pyodide. Current
DuckDB Python packaging does not satisfy that Worker target, so the hosted analysis step should not
depend on `import duckdb` in a Python Worker.

Smallest Cloudflare-only fallback:

Prototype a Cloudflare Container running normal Python plus DuckDB, controlled by a Worker/Durable
Object, with R2 as the raw/curated object store. The container can use the regular DuckDB Python
package and read R2 Parquet via the S3-compatible API or explicit object transfer, while Workers
remain responsible for email ingestion, orchestration, and publication triggers.

DuckDB-Wasm in a JavaScript/TypeScript Worker is not the preferred next fallback unless a
Worker-specific build is chosen deliberately. The official DuckDB-Wasm deployment model expects
separate JS worker and Wasm assets, and Cloudflare Workers still impose 128 MB isolate memory plus
bundle-size constraints.

References:

- Cloudflare Python Workers: https://developers.cloudflare.com/workers/languages/python/
- Cloudflare Python package support: https://developers.cloudflare.com/workers/languages/python/packages/
- Cloudflare Workers limits: https://developers.cloudflare.com/workers/platform/limits/
- Cloudflare Containers: https://developers.cloudflare.com/containers/
- Cloudflare Container limits: https://developers.cloudflare.com/containers/platform-details/limits/
- DuckDB R2 import guide: https://duckdb.org/docs/lts/guides/network_cloud_storage/cloudflare_r2_import.html
- DuckDB-Wasm deployment guide: https://duckdb.org/docs/lts/clients/wasm/deploying_duckdb_wasm.html
