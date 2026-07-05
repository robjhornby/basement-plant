# Cloudflare Infrastructure

Durable Cloudflare infrastructure for the basement analysis belongs here, not under `.scratch/`.

The target hosted path is documented in
[Cloudflare Email To R2 Static Site Architecture](../../docs/architecture/cloudflare-email-r2-static-site.md).

Expected future contents:

- OpenTofu, Wrangler, or another explicit config/code based deployment path for Cloudflare
  resources. The tool choice is intentionally undecided until the wayfinder ticket for Cloudflare
  infrastructure-as-code is resolved.
- Cloudflare Email Routing / Email Worker configuration for the ingest address.
- R2 bucket definitions and bindings.
- Worker or Workflow code that stores raw emails, extracts CSV attachments, writes Parquet, and
  triggers the analysis/static-site publication step.
- Cloudflare Pages or static asset publication configuration.

Do not add AWS SES/S3 resources for this project unless the Cloudflare-only direction is explicitly
reversed. OpenTofu remains acceptable for Cloudflare resources if it proves to be the right fit.
