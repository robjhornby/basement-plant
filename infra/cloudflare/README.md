# Cloudflare Infrastructure

Durable Cloudflare infrastructure for the basement analysis belongs here, not under `.scratch/`.

The target hosted path is documented in
[Cloudflare Email To R2 Static Site Architecture](../../docs/architecture/cloudflare-email-r2-static-site.md).

Current contents:

- `tofu/`: OpenTofu root for durable Cloudflare resources — the private `basement-pipeline` R2
  bucket, the private `basement-site` publication bucket, the site DNS record, and the
  ingest-address-to-Worker routing rule. See `tofu/README.md` for apply ordering and provider
  gaps.
- `workers/email-ingest/`: Wrangler-managed TypeScript Email Worker that receives X-Sense CSV
  emails, stores immutable raw `.eml` evidence, extracts CSV attachments, and writes ingest and
  rejection manifests. See `workers/email-ingest/README.md` for tests and deploy steps.
- `workers/site/`: Wrangler-managed TypeScript GET-only Worker that serves generated HTML from
  the `basement-site` R2 bucket on `basement.robjhornby.com`.

Expected future contents:

- `scripts/` only for imports, smoke tests, fixture uploads, Pages direct upload, or provider/API
  gaps that are not cleanly declarative yet.
- Python code that later turns accepted CSV inputs into Parquet before the GitHub Actions analysis
  runner reads them.

Do not add AWS SES/S3 resources for this project unless the Cloudflare-only direction is explicitly
reversed. OpenTofu remains acceptable for Cloudflare resources if it proves to be the right fit.
