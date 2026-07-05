# Adapt analysis to local partitioned Parquet DuckDB path

Type: task
Status: open
Parent: ../map.md

## Question

Adapt the local analysis path so the production analysis can use plain partitioned Parquet files
queried through DuckDB as its primary analytical input shape, before the Cloudflare Container
prototype tries to read equivalent Parquet objects from R2.

Keep this local-first and implementation-focused:

- derive a local curated Parquet dataset from the existing X-Sense CSV and event inputs;
- use deterministic, Cloudflare/R2-friendly object-style paths and Hive-style partitioning where
  useful;
- query the Parquet dataset through DuckDB rather than loading all analytical input from CSV files;
- preserve the existing generated dashboard/report behavior as much as practical while allowing
  prototype code to change where it improves the hosted-ready shape;
- keep Python plus `uv` as the development and execution model;
- avoid Iceberg/R2 Data Catalog for now.

Resolve with the local Parquet layout, the DuckDB query boundary, any remaining CSV-only fallback
behavior, and the command/tests that prove the static site can be generated from the curated
Parquet path.
