# Cloudflare infrastructure-as-code approach

Research date: 2026-07-06

## Question

What programmatic configuration and deployment approach should manage the Cloudflare resources for
the basement pipeline?

## Recommendation

Use a split-control model under `infra/cloudflare/`:

- OpenTofu under `infra/cloudflare/tofu/` owns stable account and zone infrastructure.
- Wrangler config files live under `infra/cloudflare/workers/<worker-name>/` with each deployable
  Worker/Container project and own code deployment, bindings, compatibility flags, local
  development, and versioned Worker runtime configuration.
- Small scripts under `infra/cloudflare/scripts/` are allowed only for operational gaps: imports,
  smoke tests, object seeding, Pages direct uploads, and any Email Routing or Container operation
  that is not yet cleanly handled by OpenTofu or Wrangler.

Do not make either OpenTofu or Wrangler the only tool. Cloudflare's own Workers IaC docs explicitly
allow managing only part of a Worker lifecycle in Terraform and using Wrangler or other deployment
tools for versions and deployments. That fits this project: durable resources need drift control,
while Worker/Container builds need the toolchain Cloudflare optimizes for development and deploys.

## Why this split

### OpenTofu is the right owner for durable infrastructure

OpenTofu should manage resources whose desired state should be reviewable and drift-detectable:

- R2 buckets for raw email, extracted CSV, curated Parquet, manifests, and generated site artifacts.
- Email Routing zone enablement/DNS where provider support is sufficient.
- Email Routing rules if the Terraform resource can express the required Worker action cleanly.
- DNS records and custom domains for `robjhornby.com` publication.
- Pages project configuration if using Pages Git integration or a stable Pages project.
- Worker routes/custom domains when they are infrastructure rather than deploy-time details.
- Workflows, Queues, Durable Objects, or D1 only if later tickets introduce a real coordination
  need.

Cloudflare documents the Terraform provider as a way to define, version, and roll back Cloudflare
configuration in source control. OpenTofu can use providers declared with source addresses and
version constraints, so the Cloudflare provider can be used from `tofu` in the normal way.

Important limitation: Cloudflare's R2 Terraform example says the Cloudflare provider manages
buckets only; CORS/lifecycle-style bucket configuration needs another route, such as the AWS
provider against the S3-compatible API, if those features become necessary. Do not add that until a
real bucket setting requires it.

### Wrangler is the right owner for deployable Worker/Container projects

Wrangler should manage:

- Worker source bundling and deploys.
- `wrangler dev` local development and local binding state.
- Worker bindings such as R2 bucket bindings, service bindings, container bindings, and declared
  secrets.
- Compatibility dates and flags, including Python Worker flags if a small Python Worker remains.
- Cron triggers if the trigger belongs to the Worker deployment lifecycle.
- Container-enabled Worker deployment, Docker/image build hooks, and local Container development.
- Version upload/deploy flows and CI deployment commands.

Cloudflare's current Workers docs treat Wrangler configuration as the source of truth for Worker
configuration when using Wrangler, including the warning that dashboard changes can be overwritten
by the next deploy. Worker versions include bundled code, static assets, bindings, and compatibility
settings, while storage resource state is outside Worker versioning. That boundary is exactly why
durable resources should not be hidden inside deploy-time scripts.

Prefer `wrangler.jsonc` for new Worker projects. Cloudflare currently recommends JSONC for new
projects, and some newer Wrangler features may only be available there. The existing prototype uses
`wrangler.toml`; treat that as prototype evidence, not a production convention.

### Scripts should stay narrow

Use scripts for:

- `tofu import` and `cf-terraforming` assisted import of existing DNS or Cloudflare resources.
- CI wrappers around `tofu fmt`, `tofu validate`, `tofu plan`, `wrangler deploy`, and smoke tests.
- R2 fixture/object upload or cleanup for local and staging tests.
- Pages direct upload if the project chooses prebuilt static assets uploaded from a trusted build
  environment instead of Pages Git integration.
- API calls for a Cloudflare feature that is not yet reliable through the provider or Wrangler.

Every script should be idempotent where practical and should say which declarative gap it fills.
If a script starts carrying desired-state configuration, promote that configuration into OpenTofu or
Wrangler.

## Resource-by-resource decision

### Email Routing and Email Workers

Use OpenTofu for Email Routing DNS/settings and possibly rules. The Cloudflare Terraform API docs
list `cloudflare_email_routing_settings`, `cloudflare_email_routing_dns`,
`cloudflare_email_routing_rule`, catch-all, and destination-address resources. Email Routing also
has dashboard onboarding semantics and verified destination-address flows, so expect a one-time
manual verification step if forwarding is used.

For the ingest address that sends mail to a Worker, prefer a programmatic route. First try the
Terraform Email Routing rule if it can represent the Worker action with the deployed Worker tag or
script identifier. If that proves awkward, use the Email Routing API in a small script and document
the rule as script-managed. Do not hide email routing in the dashboard as the steady-state answer.

The Worker itself should be a Wrangler project. Cloudflare documents the `email()` handler for
incoming mail and local email routing tests through `wrangler dev`.

### R2

Use OpenTofu for bucket creation and retention-critical bucket names. Use Wrangler bindings in the
Worker projects to attach those buckets to code. Object keys, manifests, and partition paths belong
in application code/tests, not OpenTofu.

Use R2 S3 credentials only for non-Worker clients such as local tools, DuckDB, or a Container if the
binding/API route is not enough. R2 S3 credentials have their own token flow and should be stored in
developer or CI secret stores, not in the repo.

### Workers, bindings, schedules, and Workflows

Use Wrangler for ordinary Worker deployments and binding declarations. Use OpenTofu only for
separate durable resources that a Worker binds to, or when a resource needs cross-project drift
control.

If Workflows become part of the design, OpenTofu can manage the `cloudflare_workflow` resource, but
the Worker code that implements the Workflow should still be deployed through Wrangler unless a
later prototype proves Terraform deployment is less painful.

### Cloudflare Containers

Treat Containers as a Worker project with Docker/container assets managed beside the code. Keep
Durable Object/container configuration in Wrangler unless later provider support makes an
OpenTofu-owned resource boundary clearer. The next prototype should prove build, deploy, R2
read/write, secrets, logs, and repeatability before the production infrastructure shape is frozen.

### Pages/static publication

Use one of two paths:

- If publication is coupled to generated static assets from the hosted analysis job, use a script or
  CI step for Pages Direct Upload with Wrangler, because Cloudflare positions Direct Upload for
  prebuilt assets from custom build systems.
- If publication should be a stable Git-linked site, create/manage the Pages project through
  OpenTofu and let Cloudflare builds publish from the repository.

Worker static assets are also viable if the static site naturally belongs to the same Worker deploy,
but that couples report publication to Worker versions. Keep Pages Direct Upload as the first
publication default for a generated static report unless a later ticket chooses otherwise.

### DNS records and custom domains

Use OpenTofu. Import existing records before managing them so `tofu plan` does not accidentally
replace unrelated zone state. Keep the scope tight to the basement subdomain/records unless the user
explicitly wants broader `robjhornby.com` DNS managed here.

### Secrets

Do not store secrets in OpenTofu variables, Wrangler config, or checked-in files. Use Wrangler
secrets for Worker runtime secrets and CI/provider secret stores for `CLOUDFLARE_API_TOKEN`,
`CLOUDFLARE_ACCOUNT_ID`, R2 S3 credentials, and OpenTofu state backend credentials. Cloudflare's
Workers docs explicitly direct secrets through Wrangler secret handling and CI secret stores.

## Proposed `infra/cloudflare/` layout

Start small:

```text
infra/cloudflare/
  README.md
  tofu/
    versions.tf
    providers.tf
    variables.tf
    locals.tf
    r2.tf
    email_routing.tf
    dns.tf
    pages.tf
    outputs.tf
    env/
      example.tfvars
  workers/
    email-ingest/
      wrangler.jsonc
      src/
      tests/
      fixtures/
    analysis-container/
      wrangler.jsonc
      Dockerfile
      src/
  pages/
    README.md
    deploy-site.sh
  scripts/
    import-existing.sh
    set-secrets.sh
    smoke-email-route.sh
    smoke-r2.sh
```

If the repo later needs separate state files, split by Cloudflare's account/zone/product guidance:
`infra/cloudflare/tofu/account/`, `infra/cloudflare/tofu/zones/robjhornby.com/`, and
`infra/cloudflare/tofu/products/basement/`. Do not introduce that complexity before the first
managed resources exist.

## CI and local workflow

Local:

- `tofu -chdir=infra/cloudflare/tofu fmt`
- `tofu -chdir=infra/cloudflare/tofu validate`
- `tofu -chdir=infra/cloudflare/tofu plan -var-file=env/local.tfvars`
- `npx wrangler dev` in each Worker project
- local email tests through the documented `/cdn-cgi/handler/email` endpoint

CI:

- Run `tofu fmt -check` and `tofu validate` on every change.
- Run `tofu plan` for infrastructure changes, with apply remaining manual until the first deployed
  loop is stable.
- Deploy Workers with Wrangler using scoped `CLOUDFLARE_ACCOUNT_ID` and `CLOUDFLARE_API_TOKEN`
  secrets.
- Upload/update Worker secrets through Wrangler secret flows or `--secrets-file` from CI secret
  material, not from committed files.

## Import and drift handling

Before OpenTofu manages existing zone resources, import them. Cloudflare documents `cf-terraforming`
for generating Terraform config and import commands; the import step is manual today. Use it only
for the resources this project will own, then review the generated config instead of accepting a
zone-wide dump.

After import:

- Keep OpenTofu as source of truth for managed DNS/R2/Email Routing/Pages resources.
- Keep Wrangler config as source of truth for Worker deployments.
- Avoid dashboard edits except for one-time verification flows; if a dashboard edit is necessary,
  copy the resulting desired state back into the relevant config immediately.

## Decision

Adopt the split-control model now. The next implementable infrastructure ticket should create
`infra/cloudflare/tofu/` for OpenTofu-managed foundation resources and
`infra/cloudflare/workers/email-ingest/` as the first Wrangler project. Container production shape
should wait for the Cloudflare Container prototype.

## Sources

- Cloudflare Terraform overview: <https://developers.cloudflare.com/terraform/>
- Cloudflare Terraform best practices: <https://developers.cloudflare.com/terraform/advanced-topics/best-practices/>
- Cloudflare Terraform import docs: <https://developers.cloudflare.com/terraform/advanced-topics/import-cloudflare-resources/>
- Cloudflare Workers IaC docs: <https://developers.cloudflare.com/workers/platform/infrastructure-as-code/>
- Wrangler configuration docs: <https://developers.cloudflare.com/workers/wrangler/configuration/>
- Worker versions and deployments: <https://developers.cloudflare.com/workers/versions-and-deployments/>
- Worker secrets docs: <https://developers.cloudflare.com/workers/configuration/secrets/>
- Worker best practices: <https://developers.cloudflare.com/workers/best-practices/workers-best-practices/>
- R2 Terraform docs: <https://developers.cloudflare.com/r2/examples/terraform/>
- R2 Workers usage docs: <https://developers.cloudflare.com/r2/api/workers/workers-api-usage/>
- R2 authentication docs: <https://developers.cloudflare.com/r2/api/tokens/>
- Email Routing Terraform resources: <https://developers.cloudflare.com/api/terraform/resources/email_routing/>
- Email Routing Worker API: <https://developers.cloudflare.com/email-service/api/route-emails/email-handler/>
- Email Routing local development: <https://developers.cloudflare.com/email-service/local-development/routing/>
- Email Routing setup docs: <https://developers.cloudflare.com/email-service/get-started/route-emails/>
- Cloudflare Containers overview: <https://developers.cloudflare.com/containers/>
- Cloudflare Containers local development: <https://developers.cloudflare.com/containers/local-dev/>
- Cloudflare Pages Direct Upload: <https://developers.cloudflare.com/pages/get-started/direct-upload/>
- Cloudflare Pages Direct Upload with CI: <https://developers.cloudflare.com/pages/how-to/use-direct-upload-with-continuous-integration/>
- Cloudflare Pages Terraform resources: <https://developers.cloudflare.com/api/terraform/resources/pages>
- Cloudflare Wrangler GitHub Action: <https://github.com/cloudflare/wrangler-action>
- OpenTofu provider requirements: <https://opentofu.org/docs/language/providers/requirements/>
