# Cloudflare Email To R2 Static Site Architecture

## Current Direction

Run the hosted ingestion, storage, analysis, and publication path exclusively on Cloudflare
infrastructure:

```text
X-Sense daily CSV email
  -> Cloudflare Email Routing / Email Worker
  -> R2 raw email object
  -> R2 extracted CSV objects
  -> R2 derived Parquet objects
  -> Cloudflare-hosted analysis job
  -> Cloudflare-published static site
```

The email source remains central. The ingest address may receive mail directly from X-Sense if that
is configurable, or from a Gmail forwarding rule if Gmail remains the mailbox that receives the
daily export. From the ingest address onward, the durable pipeline should be Cloudflare-owned.

## Storage Shape

Use R2 as the durable store:

- `raw-emails/`: original received `.eml` objects.
- `csv/`: extracted CSV attachments, named by date, sensor identity, and content hash.
- `parquet/`: derived Parquet files used by analysis.
- `site/`: generated static publication artifacts, if direct Pages upload is not the selected
  deployment mechanism.
- `manifests/`: small JSON manifests for idempotence and audit state if deterministic object keys
  are not enough.

Do not add a database by default. Prefer deterministic object keys, attachment content hashes, and
manifest objects for idempotence. Add D1/Durable Objects/Queues only if a concrete coordination
problem appears.

## Execution Shape

The desired execution model is a Cloudflare-hosted Python analysis job that uses DuckDB to query
Parquet files from R2, feeds the existing `basement_analysis` analysis/static-site code, and
publishes updated static output.

This is not yet proven. Cloudflare supports Python Workers, Email Workers, R2 bindings, and
scheduled Workers, but the exact viability of Python DuckDB inside Cloudflare Workers needs a
prototype because Python Workers run on Pyodide/Wasm and package support/performance limits may
matter. If Python DuckDB is not viable directly, the fallback should still remain Cloudflare-only:

- use a JavaScript/TypeScript Worker with a DuckDB-Wasm package that supports Workers; or
- split the flow so Workers handle email/R2 conversion and another Cloudflare-supported compute
  surface runs the heavier analysis.

## Publication Shape

Publish static artifacts through Cloudflare Pages or another Cloudflare static asset path. The
published output should be rebuildable from production code plus R2 raw/curated objects.

## Superseded Direction

The previous AWS SES plus S3 plan is superseded. Keep its issue history as design context, but do
not promote that OpenTofu package or create AWS resources for this effort.

## References

- Cloudflare Email Workers: https://developers.cloudflare.com/email-service/api/route-emails/email-handler/
- Cloudflare Python Workers: https://developers.cloudflare.com/workers/languages/python/
- Cloudflare Python package support: https://developers.cloudflare.com/workers/languages/python/packages/
- Cloudflare R2 Workers API: https://developers.cloudflare.com/r2/api/workers/workers-api-reference/
- Cloudflare R2 uploads from Workers: https://developers.cloudflare.com/r2/objects/upload-objects/
