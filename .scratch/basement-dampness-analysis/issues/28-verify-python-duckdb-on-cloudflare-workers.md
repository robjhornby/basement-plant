# Verify Python DuckDB on Cloudflare Workers

Type: prototype
Status: open
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
