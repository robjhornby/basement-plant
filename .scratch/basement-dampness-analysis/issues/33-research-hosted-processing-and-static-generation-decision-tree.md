# Research hosted processing and static generation decision tree

Type: research
Status: resolved
Parent: ../map.md
Blocked by: 28

## Question

What is the right decision tree for the hosted basement data-processing and static dashboard/report
generation stack now that Python DuckDB does not work in a standard Cloudflare Python Worker?

Research and broaden the option space before asking the user to choose. Cover at least:

- what Python packages can realistically run in Cloudflare Python Workers today, including whether
  Polars, PyArrow, Pandas, NumPy, DuckDB, MetroloPy, and the existing `basement_analysis`
  dependencies can run under Pyodide/Emscripten constraints;
- what could run in JavaScript/TypeScript Workers, including DuckDB-Wasm, Arquero, plain JS
  transforms, WASM asset limits, R2 access, bundle size, memory, CPU, and local-dev friction;
- what Cloudflare Containers change, including startup/scale-to-zero behavior, CPU, memory, disk,
  networking, R2 access patterns, secrets, cost, deployment maturity, and operational complexity;
- whether Cloudflare Pages builds, Workflows, Queues, Durable Objects, Browser Rendering, D1, or
  another Cloudflare surface changes the design;
- whether keeping hosted processing very small and doing heavier generation locally, in CI, or in a
  scheduled external runner would be a better tradeoff despite the Cloudflare-only preference;
- how the choice affects CSV extraction, CSV-to-Parquet conversion, processing state, analytical
  model code reuse, static publication artifacts, reproducibility from the local `uv run basement`
  path, and later blog/article-grade explanations.

Produce a markdown research asset with a decision tree, not just a comparison table. Each branch
should state the capability test, likely answer, tradeoffs, risks, and what prototype or user
decision should follow. The result should prepare an informed grilling session rather than settle
the architecture silently.

## Answer

Research asset:
[Hosted processing and static generation decision tree](../research/33-hosted-processing-static-generation-decision-tree.md).

Summary:

- Standard Cloudflare Python Workers are not the natural hosted analysis path for this project.
  They are Pyodide-based, beta, Worker-limited, and only support pure Python or Pyodide-supported
  packages; current Pyodide packages do not match the repo's local DuckDB/Polars/NumPy pins, and
  MetroloPy was not present in the Pyodide package list checked on `2026-07-05`.
- JavaScript/TypeScript Workers are a good fit for email ingestion, CSV extraction, deterministic
  R2 object keys, manifests, small summaries, orchestration triggers, and maybe a smaller hosted
  static artifact. They should not silently become a second implementation of the physical
  analysis/reporting model.
- DuckDB-Wasm in Workers is possible enough to prototype only if the user chooses a
  Workers-first route, but its multi-asset Wasm deployment model, package size, and 128 MB Worker
  memory limit make it risky as the default hosted analysis engine.
- Cloudflare Containers are the only Cloudflare-hosted option found that plausibly preserves the
  normal `uv run basement` Python/DuckDB/Polars path, at the cost of Docker image deployment,
  Durable Object/container lifecycle, paid-plan requirements, and more operational surface.
- Workflows, Queues, Durable Objects, D1, Pages/static assets, R2, and Browser Run support the
  pipeline but do not replace the core compute decision. R2 remains the right artifact store;
  D1 should remain optional state, not the default analytical store.

The next step should be a grilling checkpoint, not immediate infrastructure work. The key user
tradeoff is whether preserving exact `uv run basement` behavior matters more than keeping hosted
processing small and Cloudflare-native.
