# Evaluate DuckDB/DuckLake dashboard hosting architecture

Type: research
Status: resolved
Parent: ../map.md
Blocked by: 11

Superseded by: 27

## Question

What simple, cheap architecture should turn S3-stored raw emails and local CSV backfills into DuckDB or DuckLake-backed analysis outputs and static publication artifacts on `robjhornby.com`?

Research options that fit the user's learning goal around DuckDB/DuckLake while staying operationally simple. Treat the email path from [Clarify email ingestion and hosting constraints](11-clarify-email-ingestion-and-hosting-constraints.md) as settled: Gmail filtered forwarding to SES inbound in `eu-west-2`, private S3 raw email store, batch/pull Python processing first, OpenTofu-managed AWS/Cloudflare resources, and static generated publication before any live dashboard.

Compare the remaining choices: storage format, DuckDB versus DuckLake role, local/server scheduler, static dashboard/report generation tool, static hosting target, secrets handling, processing-state storage, backup/recovery strategy, and what would be overkill but educational versus necessary.

## Answer

Superseded direction as of `2026-07-05`: do not make DuckDB/DuckLake or AWS S3 the required hosted
state layer. The current direction is Cloudflare Email/R2, derived Parquet in R2, no database by
default, and a feasibility prototype for Python DuckDB on Cloudflare Workers. See
[Adopt Cloudflare-only email/R2/static-site pipeline](27-adopt-cloudflare-only-email-r2-static-site-pipeline.md).

Use a local-first batch architecture:

`private raw S3 + local CSV backfills -> Python batch job -> private DuckDB working database -> optional local DuckLake curated history -> static HTML/JSON/PNG publication -> Cloudflare-hosted static site`

DuckDB should be the required operational store for the next stage. DuckLake should be introduced deliberately, first with a local DuckDB catalog and local/S3-compatible file storage, to learn snapshots, schema evolution, and lakehouse file layout without making it the only state mechanism. Do not add PostgreSQL, a live dashboard server, Lambda/SQS processing, or public DuckDB/DuckLake access until the analysis and dashboard views have stabilized.

Specific choices:

- Store raw SES `.eml` files and extracted attachments privately; export only public-safe static artifacts.
- Use plain DuckDB for ingest state, dedupe, weather cache state, analysis marts, and constraints-backed operational tables.
- Use DuckLake only for curated/history tables where snapshots, time travel, schema evolution, and Parquet-on-object-storage learning are useful.
- Keep processing as one idempotent, manually runnable `uv run` batch command before adding cron or server automation.
- Start publication with Quarto-style static reports; keep Observable Framework as the richer dashboard upgrade once the core views and public JSON/CSV/Parquet outputs are stable.
- Prefer Cloudflare Pages or the existing root-site deploy path for static hosting; avoid an always-on app server.
- Keep AWS/Cloudflare credentials outside the repo and avoid persisting broad object-store secrets inside publishable artifacts.
- Back up the DuckDB working database and any DuckLake catalog after successful batches; treat generated public artifacts as rebuildable.

Research asset: [DuckDB/DuckLake dashboard hosting architecture](../research/12-duckdb-ducklake-dashboard-hosting-architecture.md).

Later scope note: [Refocus roadmap on local CSV-to-static-site first](21-refocus-roadmap-on-local-csv-to-static-site-first.md) keeps the local DuckDB/static-generation path active now, but defers SES, S3, `robjhornby.com`, AWS/Cloudflare setup, and server automation to a later phase.
