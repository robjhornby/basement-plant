# Adopt Cloudflare-only email/R2/static-site pipeline

Type: grilling
Status: resolved
Parent: ../map.md

## Question

What hosted architecture should replace the previously planned AWS SES/S3 ingestion path?

## Answer

Use a Cloudflare-only hosted path while keeping daily emailed CSVs as the source:

`X-Sense daily CSV email -> Cloudflare Email Routing / Email Worker -> R2 raw email object -> R2 extracted CSV objects -> R2 derived Parquet objects -> Cloudflare-hosted analysis job -> Cloudflare-published static site`

The ingest email remains central. X-Sense may send directly to the Cloudflare ingest address if the
export workflow supports that; otherwise Gmail can forward matching X-Sense CSV emails to the
Cloudflare ingest address. From receipt onward, storage, processing, and publication should run on
Cloudflare infrastructure.

Do not add a database by default. Use R2 object keys, attachment content hashes, and small manifest
objects for idempotence and audit state unless a concrete coordination problem requires D1, Durable
Objects, Queues, or another state service.

The desired analysis execution model is Python on Cloudflare using DuckDB to query Parquet in R2,
then feeding the existing `basement_analysis` analysis/static-site generator. That is a hypothesis,
not a proven constraint: Python Workers and DuckDB-on-Workers compatibility/performance must be
verified before committing implementation tickets to that shape.

Durable architecture note:
[Cloudflare Email To R2 Static Site Architecture](../../../docs/architecture/cloudflare-email-r2-static-site.md).

Project-structure decision: durable Cloudflare infrastructure belongs under `infra/cloudflare/`,
not `.scratch/`; throwaway prototypes belong under top-level `prototypes/<prototype-name>/`, one
prototype per subdirectory.

Deployment decision: the hosted system should still be programmatic and configuration/code based.
OpenTofu is not ruled out; the project should explicitly choose the best Cloudflare deployment
mechanism, likely some combination of OpenTofu for account resources and Wrangler for Worker code
and bindings.
