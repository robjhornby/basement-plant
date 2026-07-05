# Research hosted processing and static generation decision tree

Type: research
Status: open
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
