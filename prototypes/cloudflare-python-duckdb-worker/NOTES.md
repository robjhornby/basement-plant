# Cloudflare Python DuckDB Worker Prototype

Status: throwaway prototype for
`Verify Python DuckDB on Cloudflare Workers`.

## Question

Can a Cloudflare-hosted Python Worker import `duckdb`, read a representative Parquet object from
R2 or an R2-like fixture, and return a tiny analytical summary inside Workers constraints?

## Commands

```bash
cd prototypes/cloudflare-python-duckdb-worker
uv run python scripts/build_fixture.py
uv run pywrangler dev
```

In another terminal, seed the local R2 bucket if the Worker starts:

```bash
npx wrangler r2 object put basement-python-duckdb-prototype/fixtures/basement-sensor.parquet \
  --file fixtures/basement-sensor.parquet --local
curl http://localhost:8787/
```

## Result

Python DuckDB is not viable in Cloudflare Python Workers for this project as of `2026-07-05`.

The fixture generation worked locally:

```bash
uv run python scripts/build_fixture.py
```

That produced `fixtures/basement-sensor.parquet`, confirming the representative Parquet file and
DuckDB query shape are valid in normal local Python.

The Cloudflare Python Worker startup failed before serving requests:

```text
uv pip compile ... --python cpython-3.13.2-emscripten-wasm32-musl \
  --extra-index-url https://index.pyodide.org/0.28.3 --no-build ...

No solution found when resolving dependencies:
Because only duckdb<=1.5.4 is available and duckdb==1.5.4 has no usable wheels,
we can conclude that duckdb>=1.5.4 cannot be used.
```

An exact probe of the hinted pre-release also failed:

```text
Because duckdb==1.6.0.dev280 has no usable wheels and you require
duckdb==1.6.0.dev280, we can conclude that your requirements are unsatisfiable.
```

This matches Cloudflare's Python Worker model: Python Workers run on Pyodide/Wasm, and packages
must be pure Python, PyEmscripten wheels, or included in Pyodide. The normal DuckDB Python package
does not currently satisfy that target in the Python Worker resolver.

## Verdict

Do not implement the hosted analysis step as a Python Worker importing `duckdb`.

The smallest Cloudflare-only fallback to verify next is a Cloudflare Container running normal
Python plus DuckDB, controlled by a Worker/Durable Object and reading/writing R2 through the S3 API
or signed/internal fetches. That keeps the pipeline on Cloudflare while avoiding the 128 MB
Worker-isolate and Pyodide package constraints.

DuckDB-Wasm in a JavaScript Worker remains a possible research path only with a Worker-specific
custom build. The official browser-oriented `@duckdb/duckdb-wasm` package expects additional JS
worker/Wasm assets, while Cloudflare Workers have tight bundle, memory, and runtime constraints.
