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

The hosted analysis job should remain Cloudflare-owned, but it should not be implemented as a
Python Worker importing `duckdb`. The Python Worker prototype failed during Cloudflare's
Pyodide/Emscripten dependency resolution because no usable DuckDB wheel was available for the
Worker target.

Next, verify a Cloudflare Container fallback: a Worker/Durable Object controls a container image
that runs normal Python plus DuckDB, reads Parquet from R2, feeds the existing `basement_analysis`
analysis/static-site code, and publishes updated static output. This keeps the hosted path on
Cloudflare while avoiding Python Worker package and isolate limits.

DuckDB-Wasm in a JavaScript/TypeScript Worker is a secondary fallback only if a Worker-specific
build proves simple enough. Do not assume the official browser-oriented DuckDB-Wasm package can run
the hosted analysis step in Workers without a separate prototype.

## Publication Shape

Publish static artifacts through Cloudflare Pages or another Cloudflare static asset path. The
published output should be rebuildable from production code plus R2 raw/curated objects.

## Deployment Shape

Cloudflare resources should be managed programmatically from configuration/code. OpenTofu is still
allowed and may be the right tool for DNS, R2 buckets, Email Routing resources, Pages projects, and
other Cloudflare account resources. Wrangler configuration may be better for Worker code, bindings,
local dev, and deploy workflows. The project has not yet chosen the split; decide it explicitly
before creating durable Cloudflare infrastructure.

## Superseded Direction

The previous AWS SES plus S3 plan is superseded. Keep its issue history as design context, but do
not create AWS resources for this effort. This does not rule out OpenTofu for Cloudflare resources.

## References

- Cloudflare Email Workers: https://developers.cloudflare.com/email-service/api/route-emails/email-handler/
- Cloudflare Python Workers: https://developers.cloudflare.com/workers/languages/python/
- Cloudflare Python package support: https://developers.cloudflare.com/workers/languages/python/packages/
- Cloudflare R2 Workers API: https://developers.cloudflare.com/r2/api/workers/workers-api-reference/
- Cloudflare R2 uploads from Workers: https://developers.cloudflare.com/r2/objects/upload-objects/
- Cloudflare Containers: https://developers.cloudflare.com/containers/
