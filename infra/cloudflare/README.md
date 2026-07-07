# Cloudflare Infrastructure

Durable Cloudflare infrastructure for the basement analysis belongs here, not under `.scratch/`.

The target hosted path is documented in
[Cloudflare Email To R2 Static Site Architecture](../../docs/architecture/cloudflare-email-r2-static-site.md).

Cloudflare OpenTofu authentication is project-local: `tofu/.envrc` exports
`CLOUDFLARE_API_TOKEN`. Agents and humans running `tofu plan` or `tofu apply` should either use
`direnv allow`/an already-loaded direnv shell, or explicitly source `tofu/.envrc` before running
OpenTofu commands. Do not assume a shell in this repo root has that variable loaded.

Current contents:

- `tofu/`: OpenTofu root for durable Cloudflare resources — the private `basement-pipeline` R2
  bucket, the private `basement-site` publication bucket, and the ingest-address-to-Worker routing
  rule. See `tofu/README.md` for apply ordering and provider gaps.
- `workers/email-ingest/`: Wrangler-managed TypeScript Email Worker that receives X-Sense CSV
  emails, stores immutable raw `.eml` evidence, extracts CSV attachments, and writes ingest and
  rejection manifests. See `workers/email-ingest/README.md` for tests and deploy steps.
- `workers/site/`: Wrangler-managed TypeScript GET-only Worker that serves generated HTML from
  the `basement-site` R2 bucket under `https://robjhornby.com/basement/`.

Expected future contents:

- `scripts/` only for imports, smoke tests, fixture uploads, Pages direct upload, or provider/API
  gaps that are not cleanly declarative yet.
- Python code that later turns accepted CSV inputs into Parquet before the GitHub Actions analysis
  runner reads them.

Do not add AWS SES/S3 resources for this project unless the Cloudflare-only direction is explicitly
reversed. OpenTofu remains acceptable for Cloudflare resources if it proves to be the right fit.
