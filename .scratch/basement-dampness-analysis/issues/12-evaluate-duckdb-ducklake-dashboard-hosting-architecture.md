# Evaluate DuckDB/DuckLake dashboard hosting architecture

Type: research
Status: open
Parent: ../map.md
Blocked by: 11

## Question

What simple, cheap architecture should turn S3-stored raw emails and local CSV backfills into DuckDB or DuckLake-backed analysis outputs and static publication artifacts on `robjhornby.com`?

Research options that fit the user's learning goal around DuckDB/DuckLake while staying operationally simple. Treat the email path from [Clarify email ingestion and hosting constraints](11-clarify-email-ingestion-and-hosting-constraints.md) as settled: Gmail filtered forwarding to SES inbound in `eu-west-2`, private S3 raw email store, batch/pull Python processing first, OpenTofu-managed AWS/Cloudflare resources, and static generated publication before any live dashboard.

Compare the remaining choices: storage format, DuckDB versus DuckLake role, local/server scheduler, static dashboard/report generation tool, static hosting target, secrets handling, processing-state storage, backup/recovery strategy, and what would be overkill but educational versus necessary.
