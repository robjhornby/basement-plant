# Deploy and smoke-test the email ingest path end to end

Type: task
Status: resolved
Parent: ../map.md
Blocked by: 36

## Question

Run the manual apply/deploy steps from
[Implement Cloudflare email-to-R2 ingest foundation](36-implement-cloudflare-email-to-r2-ingest-foundation.md)
and confirm a real email lands raw/CSV/manifest objects in the `basement-pipeline` bucket:

1. `tofu init && tofu apply` for the R2 bucket and Email Routing settings/DNS (needs
   `CLOUDFLARE_API_TOKEN`, account/zone ids in `env/production.tfvars`).
2. `npx wrangler deploy` for `infra/cloudflare/workers/email-ingest/` (needs `wrangler login`).
3. Second `tofu apply` with `-var=create_email_ingest_rule=true` to create the routing rule.
4. Manually send/forward the checked-in sample X-Sense email to
   `basement-ingest@robjhornby.com`; verify with `wrangler tail` and by listing the raw, CSV, and
   manifest objects.

Known risks to watch (from the ticket's Answer): Email Routing enablement on a never-enabled zone
may need a one-time dashboard action, and the Worker-action routing rule shape has not been
exercised against the live API — fall back to a narrow API script if the provider rejects it.

Requires the human's Cloudflare credentials — run in a user-attended session.

## Answer

The Cloudflare email-to-R2 ingest path is deployed and verified end to end against live
infrastructure. A real forwarded X-Sense email lands raw `.eml`, three extracted CSVs, and an
`accepted` ingest manifest in the private `basement-pipeline` R2 bucket; a non-matching email lands
raw `.eml` plus a `subject_mismatch` rejection manifest and is never bounced.

What is now live:

- **R2 bucket** `basement-pipeline` (WEUR), tofu-managed.
- **Worker** `basement-email-ingest` deployed (`https://basement-email-ingest.robjhornby.workers.dev`),
  `PIPELINE_BUCKET` → `basement-pipeline`.
- **Email Routing rule** (tofu-managed): `to: basement-ingest@robjhornby.com` → the Worker.
- **Ingest address**: `basement-ingest@robjhornby.com`.

Object layout confirmed in production (matches `raw_email_ingest.py`):

- `raw-emails/source=x-sense/received_date=YYYY-MM-DD/raw_sha256=<sha>.eml`
- `csv/source=x-sense/export_date=YYYY-MM-DD/attachment_sha256=<sha>/<file>.csv`
- `manifests/ingest/…json` (accept) / `manifests/rejections/…json` (reject)

Smoke-test evidence (received_date 2026-07-06): accept produced 3 CSVs @ 1440 rows each
(export_date 2026-07-04, raw_sha `dbcbdbf3…`); reject produced raw + manifest with
`status: subject_mismatch` (raw_sha `22b44a5a…`).

Deviations from the original apply plan (all forced by scoped-API-token / provisioning gaps the
ticket flagged, and all resolved via one-time dashboard actions):

- **R2 required a one-time dashboard enable** before the API would create buckets
  (`10042 Please enable R2`).
- **Email Routing enablement + MX/SPF DNS is not tofu-manageable.** The
  `/email/routing`, `/email/routing/enable`, and `/email/routing/dns` endpoints return
  `403 Authentication error` for a scoped API token — even a *read*, and even after the zone is
  enabled (the `Email Routing Rules` permission covers only `/email/routing/rules`). So
  `cloudflare_email_routing_settings` and `cloudflare_email_routing_dns` were **removed** from
  `infra/cloudflare/tofu/email_routing.tf`; Email Routing is enabled once in the dashboard, which
  also adds the `route{1,2,3}.mx.cloudflare.net` MX + SPF records. The routing **rule** stays in
  tofu (that endpoint is token-reachable). Documented in `infra/cloudflare/tofu/README.md`.
- Token scopes that work: Account · Workers R2 Storage · Edit; Zone · DNS · Edit; Zone · Email
  Routing Rules · Edit. Held in `infra/cloudflare/tofu/.envrc` (direnv, gitignored). Worker deploy
  uses `wrangler login` (OAuth), not this token.

Idempotence confirmed content-addressed (raw sha + CSV content hash); the forwarded copy carried a
new Gmail `Message-ID`, which the Worker does not depend on.

Not yet wired (see follow-up): durable production forwarding of the daily X-Sense email to the
ingest address. The smoke test used a manual Gmail forward with the subject edited back to the exact
accepted subject; ongoing ingestion needs a mechanism that preserves that exact subject (a Gmail
filter-forward, which drops the `Fwd:` prefix, or pointing X-Sense directly at the address).
