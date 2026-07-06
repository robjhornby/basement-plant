# OpenTofu: durable Cloudflare resources

Owns the durable resources for the basement pipeline: the private `basement-pipeline` R2 bucket,
zone Email Routing enablement/DNS, and the routing rule that sends the ingest address to the
`basement-email-ingest` Worker. Worker code/config is owned by Wrangler under
`../workers/email-ingest/`.

```bash
export CLOUDFLARE_API_TOKEN=...   # R2 Write, Zone DNS Write, Zone Email Routing Write
cp env/example.tfvars env/production.tfvars   # fill in account_id and zone_id
tofu init
tofu fmt -check -recursive
tofu validate
tofu plan  -var-file=env/production.tfvars
tofu apply -var-file=env/production.tfvars
```

Apply ordering: the Email Routing rule (`create_email_ingest_rule`) is gated off by default
because the provider's rule action references the Worker by name and the Worker must already be
deployed. Order is: `tofu apply` -> `wrangler deploy` (in `../workers/email-ingest/`) ->
`tofu apply -var=create_email_ingest_rule=true`.

## Provider support gaps and manual steps

- Email Routing enablement and its MX/SPF DNS records are **not** managed by tofu. The
  `/email/routing` settings/`/enable`/`/dns` endpoints return 403 "Authentication error" for a
  scoped API token (confirmed against the live API — even a read fails, and even after the zone is
  enabled), so `cloudflare_email_routing_settings` and `cloudflare_email_routing_dns` were removed.
  Enable Email Routing once in the dashboard (`robjhornby.com` -> Email -> Email Routing); that
  turns routing on and adds the `route{1,2,3}.mx.cloudflare.net` MX records and SPF TXT record
  automatically. The routing **rule** (`/email/routing/rules`) *is* token-reachable and stays in
  tofu.
- The Worker-action routing rule shape (`actions = [{ type = "worker", value = [<worker name>] }]`)
  validates against the provider schema but has not been exercised against the live API yet
  (no credentials in this environment). If the apply rejects it, fall back to a narrow script
  using the Email Routing rules API and document it under `../scripts/`.
- R2 bucket CORS/lifecycle settings are not covered by `cloudflare_r2_bucket`; none are needed
  yet. If they become necessary, use the S3-compatible API/AWS provider path.
- No state backend is configured (local state). Choose a backend before any second machine or CI
  runs applies.
- Forwarding-style Email Routing destinations (not used here) require Cloudflare's manual
  destination-address verification flow.
