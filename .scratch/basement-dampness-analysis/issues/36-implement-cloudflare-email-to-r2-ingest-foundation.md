# Implement Cloudflare email-to-R2 ingest foundation

Type: task
Status: resolved
Parent: ../map.md
Blocked by: 29

## Question

Create the first production-shaped Cloudflare ingest foundation described by
[Design Cloudflare email-to-R2 ingest](29-design-cloudflare-email-to-r2-ingest.md):

- OpenTofu foundation for the private R2 pipeline bucket and Email Routing resources where provider
  support is clean.
- `infra/cloudflare/workers/email-ingest/` Wrangler project for a TypeScript Email Worker with an
  R2 binding and `postal-mime` parsing.
- Local fixture tests using the real checked-in `.eml` sample and Wrangler's local email-routing
  test path where practical.
- Raw `.eml`, extracted CSV, rejection, and ingest manifest writes using the decided object-key
  layout and content hashes.

Do not add D1, Durable Objects, Queues, or hosted Parquet generation unless implementation proves a
specific coordination problem that the manifest/key design cannot handle.

## Answer

Built the first production-shaped Cloudflare email-to-R2 ingest foundation. No D1, Durable
Objects, Queues, or hosted Parquet generation; idempotence is entirely content-addressed keys plus
head-before-put conditional writes.

What was built:

- `infra/cloudflare/tofu/` — OpenTofu root (provider `cloudflare/cloudflare ~> 5.0`, resolved
  5.21.1): private `basement-pipeline` R2 bucket (`r2.tf`), zone Email Routing settings + routing
  DNS (`email_routing.tf`), and the `basement-ingest@robjhornby.com` → Worker routing rule gated
  behind `create_email_ingest_rule` (default false) because the rule can only reference an
  already-deployed Worker. `tofu fmt`/`tofu validate` pass; `env/example.tfvars` documents inputs;
  `tofu/README.md` documents apply ordering and provider gaps.
- `infra/cloudflare/workers/email-ingest/` — Wrangler project (`wrangler.jsonc`, name
  `basement-email-ingest`, R2 binding `PIPELINE_BUCKET` → `basement-pipeline`). `src/ingest.ts`
  hashes the raw MIME bytes (SHA-256), stores the `.eml` under the content-addressed raw key
  before any validation, parses with `postal-mime`, validates the X-Sense shape (exact subject,
  exactly three CSV attachments, required `Time`/`Temperature_Celsius`/
  `Relative Humidity_Percent` columns, non-blank values), writes content-addressed CSV objects and
  a JSON ingest manifest for accepts, and a rejection manifest (with `validation_errors`) under
  `manifests/rejections/` for everything else. Object keys and manifest fields match
  `src/basement_analysis/raw_email_ingest.py` exactly; delivery is never bounced.
- Tests: `test/email-ingest.spec.ts` via vitest + `@cloudflare/vitest-pool-workers` against the
  real local sample `.eml` (`data/email/...` — local-only since `data/` is gitignored). The accept
  test asserts key-for-key equality with ground-truth output captured by running the Python parser
  on the same fixture (raw sha `2fad5a25…`, received_date=2026-07-04, three CSVs with
  export_date=2026-07-03, 1440 rows each). Also covered: `email()` handler wiring, identical-bytes
  redelivery (`duplicate_raw_sha256` no-op), forwarded-duplicate CSV content
  (`duplicate_content_hash`), subject mismatch, invalid CSV columns, and unexpected attachment
  count rejections.

Test results: `npx tsc --noEmit` clean; `npx vitest run` → 1 file, 8/8 passed (~1.7s). Local pool
runtime warns it caps the compatibility date at 2025-09-06 vs the requested 2026-07-01; harmless.

Intentional divergence from the Python batch parser (documented in the Worker README): the Worker
is stricter (subject + exactly-three-attachments checks, per the issue 29 design) and writes
rejects to `manifests/rejections/`, while the Python backfill records every email under
`manifests/ingest/`. Raw evidence plus rejection manifests keep every rejected email fully
reprocessable by `uv run basement ingest-emails`.

Provider-support gaps / open risks (also in `infra/cloudflare/tofu/README.md`):

- Provider v5 `cloudflare_email_routing_settings` only takes `zone_id`; if apply does not activate
  Email Routing on a never-enabled zone, a one-time dashboard enable may be needed.
- The Worker-action rule shape validates against the provider schema but has not been exercised
  against the live API (no credentials in this environment); fallback is a narrow Email Routing
  API script under `infra/cloudflare/scripts/`.
- Local OpenTofu state only; pick a state backend before CI or a second machine applies.

Human follow-up (nothing was deployed; no Wrangler/Cloudflare credentials in this environment):

1. `cd infra/cloudflare/tofu && cp env/example.tfvars env/production.tfvars` (fill `account_id`,
   `zone_id`), `export CLOUDFLARE_API_TOKEN=...`, `tofu init && tofu apply -var-file=env/production.tfvars`.
2. `cd infra/cloudflare/workers/email-ingest && npm ci && npx wrangler deploy` (no Worker secrets
   needed — R2 binding only).
3. `tofu apply -var-file=env/production.tfvars -var=create_email_ingest_rule=true` to create the
   Email Routing rule.
4. Point X-Sense (or a Gmail forwarding filter) at `basement-ingest@robjhornby.com`, then verify
   with `npx wrangler tail basement-email-ingest` and the manifest objects in R2.
