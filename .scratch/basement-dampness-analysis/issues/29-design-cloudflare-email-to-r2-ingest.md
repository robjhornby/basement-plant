# Design Cloudflare email-to-R2 ingest

Type: task
Status: resolved
Parent: ../map.md
Blocked by: 31

## Question

What Cloudflare Email Routing / Email Worker and R2 resources should receive the daily X-Sense CSV
emails, store raw `.eml` objects, extract CSV attachments, write derived Parquet files, and preserve
enough object-key/hash metadata for idempotent reprocessing without a database?

Keep the source-email path explicit: support direct X-Sense delivery to the Cloudflare ingest
address if possible, and Gmail forwarding to that same address if Gmail remains the practical
recipient for X-Sense exports.

## Answer

Use a small Cloudflare Email Routing plus TypeScript Email Worker ingest front end, backed by one
private R2 pipeline bucket and manifest objects. Do not make the Email Worker write Parquet. Its
responsibility is to preserve immutable raw evidence, extract/validate the X-Sense CSV attachments,
write content-addressed CSV objects, and write a manifest that the Python parser/analysis path can
consume later.

Decision:

- OpenTofu owns the durable resources: the private R2 bucket, Email Routing DNS/settings, and the
  route to the Worker if the provider can express it cleanly.
- Wrangler owns `infra/cloudflare/workers/email-ingest/`: TypeScript Worker source, compatibility
  date, R2 binding, local dev/test config, and deployment.
- The ingest address is a dedicated local part on `robjhornby.com`, defaulting to
  `basement-ingest` unless the source-email setup ticket chooses a better address.
- The Worker should read the raw MIME message into an `ArrayBuffer`, compute a raw SHA-256, store
  the `.eml`, parse the same bytes with `postal-mime`, and validate the accepted X-Sense shape:
  current subject pattern, three CSV attachments, and required headers `Time`,
  `Temperature_Celsius`, and `Relative Humidity_Percent`.
- Source delivery remains flexible: X-Sense may send directly to the ingest address; otherwise
  Gmail forwards only matching X-Sense emails to that same address and keeps its own copy for
  recovery.

Use these first object keys:

```text
raw-emails/source=x-sense/received_date=YYYY-MM-DD/raw_sha256=<raw_sha256>.eml
csv/source=x-sense/export_date=YYYY-MM-DD/attachment_sha256=<csv_sha256>/<safe_filename>.csv
manifests/ingest/source=x-sense/received_date=YYYY-MM-DD/raw_sha256=<raw_sha256>.json
manifests/rejections/source=x-sense/received_date=YYYY-MM-DD/raw_sha256=<raw_sha256>.json
parquet/<existing local curated dataset layout>
```

The manifest is the database substitute. It should include raw object key, raw SHA-256, selected
headers (`Message-ID`, `Date`, `From`, `To`, `Subject`), accepted/rejected status, parser version,
attachment filenames, CSV object keys, CSV SHA-256 values, row counts if cheaply available, and
validation errors. R2 custom metadata can duplicate small fields for inspection, but it is not the
canonical state.

Idempotence should come from content-addressed keys and R2 conditional writes. A duplicate email or
forward should become a no-op for already-present raw/CSV objects, while preserving enough manifest
evidence to audit what happened. Do not add D1, Durable Objects, or Queues for the first version;
graduate to one only if parallel processing or retry coordination creates a concrete problem.

Durable architecture update:
[Cloudflare Email To R2 Static Site Architecture](../../../docs/architecture/cloudflare-email-r2-static-site.md).

Follow-up implementation ticket:
[Implement Cloudflare email-to-R2 ingest foundation](36-implement-cloudflare-email-to-r2-ingest-foundation.md).

Sources checked:

- Cloudflare Email Routing can route an address to a Worker, and routing rules can use a Worker as
  the destination: <https://developers.cloudflare.com/email-service/get-started/route-emails/>.
- The Email Worker `email()` handler exposes headers and the raw MIME stream, and Cloudflare's docs
  point to `postal-mime` for MIME parsing:
  <https://developers.cloudflare.com/email-service/api/route-emails/email-handler/>.
- Wrangler supports local email-routing tests via `/cdn-cgi/handler/email` with raw RFC 5322 input:
  <https://developers.cloudflare.com/email-service/local-development/routing/>.
- R2 Worker bindings support `put`, metadata, conditional writes, strong consistency, and listing
  by prefix/cursor:
  <https://developers.cloudflare.com/r2/api/workers/workers-api-reference/>.
