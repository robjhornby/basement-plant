# Choose Cloudflare infrastructure-as-code approach

Type: research
Status: resolved
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

## Answer

Research asset:
[Cloudflare infrastructure-as-code approach](../research/31-cloudflare-infrastructure-as-code-approach.md).

Decision:

Use a split-control model.

- OpenTofu under `infra/cloudflare/tofu/` should own durable account/zone resources: R2 buckets, DNS,
  Email Routing settings/DNS/rules where provider support is clean, Pages project/static-domain
  configuration if needed, and later durable orchestration resources only when a concrete need
  appears.
- Wrangler should own each deployable Worker/Container project under
  `infra/cloudflare/workers/<worker-name>/`: source bundling, deploys, compatibility dates/flags,
  bindings, local dev, schedules that belong to a Worker, secrets declarations, and
  Container-enabled Worker deployment mechanics.
- Scripts under `infra/cloudflare/scripts/` should stay narrow: imports, smoke tests,
  fixture/object uploads, Pages Direct Upload, and documented API gaps. If a script starts carrying
  steady desired state, promote that state into OpenTofu or Wrangler.

`infra/cloudflare/` should start with `README.md`, `tofu/`, `workers/email-ingest/`,
`workers/analysis-container/` later, optional `pages/`, and narrow `scripts/` helpers. The first
OpenTofu root should include `versions.tf`, `providers.tf`, `variables.tf`, `locals.tf`, `r2.tf`,
`email_routing.tf`, `dns.tf`, optional `pages.tf`, `outputs.tf`, and `env/example.tfvars`.

Open risks:

- Email Routing to a Worker may need a short API script if the Terraform rule shape cannot cleanly
  express the Worker action after the Worker exists.
- R2 bucket CORS/lifecycle-style settings are not covered by the Cloudflare provider bucket example;
  add the AWS/S3-compatible provider path only if a real bucket setting needs it.
- Container production configuration should wait until the Container prototype proves build,
  deploy, R2 access, secrets, logs, and repeatability.
