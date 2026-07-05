# Grill hosted processing stack decision

Type: grilling
Status: resolved
Parent: ../map.md
Blocked by: 33

## Question

Given the researched decision tree for hosted data processing and static dashboard/report
generation, which architecture should the project pursue next?

Use the research asset from
[Research hosted processing and static generation decision tree](33-research-hosted-processing-and-static-generation-decision-tree.md)
to explain each branch to the user in practical terms before asking for a choice. Ask one question
at a time. Make the tradeoffs explicit: standard Cloudflare Workers versus Python Workers versus
Containers versus Pages/CI/local-heavy generation, package compatibility, operational complexity,
cost, reproducibility, how much Python analysis code can be reused, and how quickly the project can
get back to useful basement dampness analysis.

Resolve with the chosen direction, rejected alternatives, and the next prototype or implementation
tickets that should remain in the map.

## Answer

Chosen direction:

- Preserve analysis runtime parity: hosted and local analysis must share the same Python-oriented
  developer experience and package-management model. The exact current `uv run basement` command
  and current prototype code are allowed to change, but hosted analysis should not become a separate
  TypeScript/backend implementation.
- Use Python plus `uv` for backend analysis. Standard JavaScript/TypeScript Workers may exist only
  as minimal Cloudflare control-plane glue, not as domain analysis code.
- Reject Cloudflare Python Workers as the main analysis runtime because the Pyodide/Emscripten
  package model does not match the desired normal Python/DuckDB/Polars development experience.
- Keep analysis compute on Cloudflare if practical. The next Cloudflare runtime branch is a
  Cloudflare Container running normal Python with `uv`.
- Use plain partitioned Parquet files in R2 as the hosted analytical dataset. Defer Iceberg/R2 Data
  Catalog until deterministic Parquet objects and small manifests become insufficient.
- DuckDB should read Parquet directly from R2 through the R2/S3-compatible path. Do not design the
  hosted path around copying all curated data into the container filesystem before querying.
- The Cloudflare Container prototype should stop at analysis runtime success: DuckDB reads R2
  Parquet, Python generates the expected static publication artifacts, and the job writes generated
  artifacts back to R2. Public static-site publication, scheduling, retries, alerts, and advanced
  orchestration remain later work.

Rejected alternatives:

- Reimplementing backend analysis in TypeScript/JavaScript Workers.
- Treating Cloudflare Python Workers/Pyodide as the production-equivalent analysis runtime.
- Using Iceberg/R2 Data Catalog before the project has a concrete need for catalog snapshots,
  multi-writer commits, schema evolution across many tables, or external lakehouse tooling.
- Treating a local CSV-only pipeline running in a container as the main proof. Local CSV support can
  remain, but the hosted proof should use the future R2/Parquet/DuckDB shape.

Next map changes:

- Add a local-first implementation ticket to adapt the analysis path to plain partitioned Parquet
  queried by DuckDB. This is a preparatory implementation step, not a risk-reduction research spike.
- Keep Cloudflare infrastructure-as-code work blocked behind that local Parquet/DuckDB adaptation,
  so the later Cloudflare Container prototype tests Cloudflare-specific runtime/R2 integration.
- Keep the existing Cloudflare Container prototype ticket, but align it to the chosen scope:
  Python/`uv`, DuckDB reading R2 Parquet directly, and generated artifact write-back to R2.

Reference material used during the decision:

- DuckDB Cloudflare R2 import: https://duckdb.org/docs/current/guides/network_cloud_storage/cloudflare_r2_import
- DuckDB Hive partitioning: https://duckdb.org/docs/current/data/partitioning/hive_partitioning
- DuckDB Iceberg extension: https://duckdb.org/docs/current/core_extensions/iceberg/overview.html
- Cloudflare R2 Data Catalog: https://developers.cloudflare.com/r2/data-catalog/
- Cloudflare Containers: https://developers.cloudflare.com/containers/
