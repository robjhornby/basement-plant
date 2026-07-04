# DuckDB/DuckLake dashboard hosting architecture

## Decision

Use a local-first batch architecture:

`private raw S3 + local CSV backfills -> Python batch job -> private DuckDB working database -> optional local DuckLake curated history -> static HTML/JSON/PNG publication -> Cloudflare-hosted static site`

DuckDB should be the required operational store for the next stage. DuckLake should be introduced deliberately, first with a local DuckDB catalog and local/S3-compatible file storage, to learn snapshots, schema evolution, and lakehouse file layout without making it the only state mechanism. Do not add PostgreSQL, a live dashboard server, Lambda/SQS processing, or public DuckDB/DuckLake access until the analysis and dashboard views have stabilized.

## Why this fits

The settled ingestion path from [Clarify email ingestion and hosting constraints](../issues/11-clarify-email-ingestion-and-hosting-constraints.md) already gives the durable raw evidence trail: Gmail filtered forwarding to SES inbound, private S3 raw email storage, and recoverable batch/pull Python processing. The database and publication layer should preserve that shape rather than turn the project into a data platform.

The repo already depends on `duckdb` and `polars` in `pyproject.toml`, and the existing prototype is Python-generated HTML. That points to a Python batch job as the narrowest next step.

## Recommended architecture

### Storage layout

- Keep raw SES `.eml` objects private in S3. This remains the source of truth for emailed measurements.
- Keep local CSV backfills as an explicit input class, not as a special-case replacement for email ingestion.
- Extract email attachments to a private normalized staging area, preferably content-addressed by attachment hash and partitioned by observation date or ingest date.
- Keep a private DuckDB database for ingestion state, parsed measurements, weather cache metadata, intervention events, uncertainty inputs, and analysis marts.
- Export public-safe static artifacts only: HTML, PNG/SVG figures, small JSON data files, and maybe public-safe Parquet later. Do not publish raw emails, raw CSV files, exact device identifiers, exact address/location, operational S3 keys, or processing state.

### DuckDB versus DuckLake

Use DuckDB for required processing state and analysis now:

- DuckDB can run directly from Python, ingest CSV/Parquet/JSON, query Polars/Pandas/Arrow, and persist a local database file.
- DuckDB supports primary key and unique constraints, which are useful for idempotent ingest state such as `s3_object_key`, email `Message-ID`, attachment SHA-256, and source CSV hash.
- DuckDB can read/write Parquet and use the `httpfs` extension for S3-compatible object storage when that becomes useful.

Use DuckLake as an optional curated-history layer:

- DuckLake's core model is a catalog database plus Parquet data files. The simplest setup is a local DuckDB catalog and local file storage.
- For this single-writer project, a DuckDB catalog is enough. DuckLake's own docs recommend DuckDB for single-client local warehousing, SQLite for multiple local clients, and PostgreSQL for multi-user/remote clients.
- DuckLake gives educational value through snapshots, time travel, schema evolution, and data files in object storage.
- Do not use DuckLake as the only ingest-state store because DuckLake currently lacks primary key, unique, foreign key, and check constraints. Keep dedupe and operational state in plain DuckDB or SQLite.

### Batch processing and state

Run one idempotent command such as:

```sh
uv run basement ingest-and-render
```

The command should:

1. List unprocessed S3 raw email objects and local backfill CSVs.
2. Parse emails and attachments into normalized rows.
3. Record processing state in DuckDB with uniqueness on source identifiers and content hashes.
4. Refresh weather caches and analysis marts.
5. Optionally write/update curated DuckLake tables.
6. Render static publication artifacts to a build directory.
7. Back up the private DuckDB database and DuckLake catalog after a successful batch.

Start with a local cron/systemd/launchd job or a cheap private server cron job. Keep the job manually runnable for backfills. A GitHub Actions schedule is possible for public build artifacts, but it is a worse default for private raw data and AWS credentials. Lambda/SQS/S3 event processing is a later refactor, not the first architecture.

### Static report/dashboard generation

Start with Quarto for report-like publication:

- Quarto supports executable Python code blocks in Markdown and produces reproducible HTML reports.
- Quarto websites can publish grouped documents to static hosting.
- This matches the user's interest in publishable, article-grade explanations.

Keep Observable Framework as the likely dashboard upgrade:

- Observable Framework builds a static `dist` directory and supports data loaders written in Python or other languages.
- It is a good fit once the core views are known and the Python pipeline can emit stable public JSON/CSV/Parquet snapshots.
- It adds a Node toolchain, so it should not block the near-term weather-inclusive Python prototype.

### Hosting target

Use static hosting, not a live app server.

Preferred first target: Cloudflare Pages, because the domain is already managed through Cloudflare and Cloudflare Pages supports uploading prebuilt assets with Wrangler or drag-and-drop. A custom subdomain such as `basement.robjhornby.com` is straightforward. Publishing under `robjhornby.com/basement/` depends on how the existing root site is deployed; if the root site build is under local control, copying the basement build into that site's published assets may be simpler than forcing Pages to own only a path.

Alternative: S3/CloudFront or Amplify Hosting. This is viable, but it duplicates CDN/domain work already available through Cloudflare and is not needed for a static basement report.

### Secrets

- Keep AWS and Cloudflare credentials outside the repo.
- Prefer AWS profiles, environment variables, or local secret configuration.
- For DuckDB S3 access, use `credential_chain`-style secret configuration rather than hard-coded keys.
- Avoid persisting broad S3 credentials inside database artifacts that might later be copied or published.

### Backup and recovery

- Raw S3 emails and local CSV backfills are the evidence sources; keep them private and recoverable.
- Enable S3 versioning or equivalent backup on the private raw/curated buckets if cost remains acceptable.
- Treat DuckDB working databases and DuckLake catalogs as rebuildable but worth backing up after each successful batch.
- If using DuckLake, back up the catalog after the batch because DuckLake recovery depends on metadata and data files matching the intended snapshot.
- Generated public artifacts are disposable; rebuild them from private inputs.

## What is overkill now

- PostgreSQL-backed DuckLake catalog: useful for multi-user or remote-client lakehouse work, unnecessary for one batch writer.
- Always-on dashboard server or API: unnecessary until there are interactive queries that cannot be precomputed.
- Lambda/S3/SQS event-driven ingestion: useful later, but batch processing keeps recovery and backfill simpler.
- Public DuckDB-Wasm or public DuckLake access: risky for privacy and unnecessary for the first publishable views.
- Moving curated data from AWS S3 to Cloudflare R2 just because Pages is on Cloudflare: DuckDB can work with S3-compatible storage, but the ingestion path is already AWS-centered.

## Sources

- DuckDB Python API: https://duckdb.org/docs/current/clients/python/overview
- DuckDB Parquet support: https://duckdb.org/docs/current/data/parquet/overview
- DuckDB S3/httpfs support and secrets: https://duckdb.org/docs/current/core_extensions/httpfs/s3api
- DuckDB S3 Parquet export guide: https://duckdb.org/docs/current/guides/network_cloud_storage/s3_export
- DuckDB constraints: https://duckdb.org/docs/current/sql/constraints
- DuckLake introduction: https://ducklake.select/docs/stable/duckdb/introduction
- DuckLake catalog choices: https://ducklake.select/docs/stable/duckdb/usage/choosing_a_catalog_database
- DuckLake storage choices: https://ducklake.select/docs/stable/duckdb/usage/choosing_storage
- DuckLake snapshots: https://ducklake.select/docs/stable/duckdb/usage/snapshots
- DuckLake time travel: https://ducklake.select/docs/stable/duckdb/usage/time_travel
- DuckLake schema evolution: https://ducklake.select/docs/stable/duckdb/usage/schema_evolution
- DuckLake constraints: https://ducklake.select/docs/stable/duckdb/advanced_features/constraints
- DuckLake backup and recovery: https://ducklake.select/docs/stable/duckdb/guides/backups_and_recovery
- Quarto websites: https://quarto.org/docs/websites/
- Quarto Python computations: https://quarto.org/docs/computations/python.html
- Observable Framework getting started: https://observablehq.com/framework/getting-started
- Observable Framework data loaders: https://observablehq.com/framework/data-loaders
- Cloudflare Pages Direct Upload: https://developers.cloudflare.com/pages/get-started/direct-upload/
- Cloudflare Pages custom domains: https://developers.cloudflare.com/pages/configuration/custom-domains/
- AWS S3 static website hosting: https://docs.aws.amazon.com/AmazonS3/latest/userguide/WebsiteHosting.html
