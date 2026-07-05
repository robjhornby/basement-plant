# Cloudflare Infrastructure

Durable Cloudflare infrastructure for the basement analysis belongs here, not under `.scratch/`.

The target hosted path is documented in
[Cloudflare Email To R2 Static Site Architecture](../../docs/architecture/cloudflare-email-r2-static-site.md).

Expected future contents:

- `tofu/` for durable Cloudflare resources such as R2 buckets, DNS, Email Routing settings, and
  routing rules where provider support is clean.
- `workers/email-ingest/` for the Wrangler-managed TypeScript Email Worker that receives X-Sense
  CSV emails, stores immutable raw `.eml` evidence, extracts CSV attachments, and writes ingest
  manifests.
- `workers/analysis-container/` later, if the Cloudflare Container prototype proves the hosted
  Python plus DuckDB analysis path.
- `scripts/` only for imports, smoke tests, fixture uploads, Pages direct upload, or provider/API
  gaps that are not cleanly declarative yet.
- Cloudflare Email Routing / Email Worker configuration for the ingest address.
- R2 bucket definitions and bindings.
- Email Worker code that stores raw emails, extracts CSV attachments, and writes ingest manifests.
- Python parser/container code that later turns accepted CSV inputs into Parquet and triggers the
  analysis/static-site publication step.
- Cloudflare Pages or static asset publication configuration.

Do not add AWS SES/S3 resources for this project unless the Cloudflare-only direction is explicitly
reversed. OpenTofu remains acceptable for Cloudflare resources if it proves to be the right fit.
