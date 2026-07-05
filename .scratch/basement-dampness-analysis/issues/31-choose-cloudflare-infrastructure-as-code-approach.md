# Choose Cloudflare infrastructure-as-code approach

Type: research
Status: open
Parent: ../map.md
Blocked by: 27, 34, 35

## Question

What programmatic configuration/deployment approach should manage the Cloudflare resources for the
basement pipeline?

Compare OpenTofu with the Cloudflare provider, Wrangler configuration/deploys, Cloudflare API/CLI
scripts, and any sensible combination of them. Cover Email Routing / Email Workers, R2 buckets,
Worker bindings, scheduled jobs or Workflows, Cloudflare Containers, Pages/static publication, DNS
records, secrets, local dev, CI deploys, import/drift handling, and what should live under
`infra/cloudflare/`.

OpenTofu is explicitly allowed; the decision to avoid AWS SES/S3 does not imply avoiding OpenTofu.
