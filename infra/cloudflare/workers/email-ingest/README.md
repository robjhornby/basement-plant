# basement-email-ingest Worker

TypeScript Email Worker that receives the daily X-Sense CSV export email via Cloudflare Email
Routing and lands it in the private `basement-pipeline` R2 bucket using the same object-key layout
and manifest shape as the Python batch parser (`src/basement_analysis/raw_email_ingest.py`), so
hosted and local ingest are interchangeable.

## What it writes

```text
raw-emails/source=x-sense/received_date=YYYY-MM-DD/raw_sha256=<raw_sha256>.eml
csv/source=x-sense/export_date=YYYY-MM-DD/attachment_sha256=<csv_sha256>/<safe_filename>.csv
manifests/ingest/source=x-sense/received_date=YYYY-MM-DD/raw_sha256=<raw_sha256>.json
manifests/rejections/source=x-sense/received_date=YYYY-MM-DD/raw_sha256=<raw_sha256>.json
```

Behavior (see `src/ingest.ts`):

- The raw MIME message is read fully, SHA-256 hashed, and stored under a content-addressed key
  before any validation, so raw evidence is never lost.
- The same bytes are parsed with `postal-mime`. Accepted emails must match the current X-Sense
  shape: exact subject, exactly three CSV attachments, and each CSV must contain the
  `Time`, `Temperature_Celsius`, and `Relative Humidity_Percent` columns with no blank required
  values.
- Accepted emails get content-addressed CSV objects plus an ingest manifest. Anything else gets a
  rejection manifest (with `validation_errors`) under `manifests/rejections/` — the SMTP delivery
  is still accepted, nothing is bounced back to X-Sense/Gmail, and the raw `.eml` allows a later
  Python backfill (`uv run basement ingest-emails`) to reprocess.
- Idempotence is content-addressed: redelivery of identical raw bytes is a no-op
  (`duplicate_raw_sha256`), and identical CSV content arriving in a different raw email (for
  example a Gmail forward) is recorded as `duplicate_content_hash` without rewriting objects.
  There is no database; manifests are the audit state.

Known, intentional divergence from the Python batch parser: the Worker is stricter (subject and
attachment-count checks) and writes rejects to `manifests/rejections/` where the Python backfill
records every email under `manifests/ingest/`. Object keys and manifest fields are otherwise
identical; the accept-path tests assert key-for-key equality against output captured from the
Python parser on the same sample email.

## Local development and tests

```bash
npm install
npm run check   # tsc --noEmit
npm test        # vitest with @cloudflare/vitest-pool-workers (local R2 simulation)
```

The tests use the real X-Sense sample email at
`data/email/Your Temperature and Relative Humidity Data Export (Please Do Not Reply).eml`
(repo `data/` is local-only/gitignored, so tests need a machine with that sample present).

Note: `@cloudflare/vitest-pool-workers` may warn that its bundled runtime supports an older
compatibility date than `wrangler.jsonc` requests and fall back; this is harmless for these tests.

Manual local email smoke test (Wrangler's local email routing path):

```bash
npx wrangler dev
curl -s -X POST 'http://localhost:8787/cdn-cgi/handler/email?from=support@x-sense.com&to=basement-ingest@robjhornby.com' \
  -H 'Content-Type: application/octet-stream' \
  --data-binary '@../../../../data/email/Your Temperature and Relative Humidity Data Export (Please Do Not Reply).eml'
```

## Deploying (human steps; nothing here is deployed automatically)

Prerequisites: a Cloudflare API token with R2 Write, Workers Scripts Write, Zone DNS Write, and
Zone Email Routing Write for `robjhornby.com` (or use `npx wrangler login`). No Worker secrets are
required — the Worker only uses the R2 binding.

1. Apply durable resources:

   ```bash
   cd infra/cloudflare/tofu
   cp env/example.tfvars env/production.tfvars   # fill in account_id and zone_id
   direnv allow .
   # or: set -a; source .envrc; set +a
   tofu init
   tofu plan  -var-file=env/production.tfvars
   tofu apply -var-file=env/production.tfvars
   ```

   OpenTofu owns the R2 buckets and the Email Routing rule. Email Routing enablement and MX/SPF
   setup remain one-time dashboard actions documented in `../../tofu/README.md`.

2. Deploy this Worker after changing its code:

   ```bash
   cd infra/cloudflare/workers/email-ingest
   npm ci
   npx wrangler deploy
   ```

3. Point the source at the ingest address: configure X-Sense to send the daily export to
   `basement-ingest@robjhornby.com`, or add a Gmail forwarding filter for the X-Sense export
   emails to that address (Gmail keeps its copy for recovery).

4. Verify: send/forward one export email, watch `npx wrangler tail basement-email-ingest` for the
   `email_ingest` log line, and confirm the manifest object exists (dashboard, or
   `npx wrangler r2 object get basement-pipeline/<manifest key> --pipe`).
