# Cloudflare Email To R2 Static Site Architecture

## Current Direction

Run the hosted ingestion, storage, and publication path on Cloudflare infrastructure, with
GitHub Actions providing the free-plan Python analysis runner:

```text
X-Sense daily CSV email
  -> Cloudflare Email Routing / Email Worker
  -> R2 raw email object
  -> R2 extracted CSV objects and ingest manifests
  -> Python parser/analysis path
  -> R2 derived Parquet objects
  -> GitHub Actions Python/uv analysis job
  -> R2 generated static site objects
  -> Cloudflare Worker route
```

The email source remains central. The ingest address may receive mail directly from X-Sense if that
is configurable, or from a Gmail forwarding rule if Gmail remains the mailbox that receives the
daily export. From the ingest address onward, the durable pipeline should be Cloudflare-owned.

## Storage Shape

Use a private pipeline R2 bucket for ingest and analytical data:

- `raw-emails/`: original received `.eml` objects.
- `csv/`: extracted CSV attachments, named by date, sensor identity, and content hash.
- `parquet/`: derived Parquet files used by analysis.
- `manifests/`: small JSON manifests for idempotence and audit state if deterministic object keys
  are not enough.

Use a separate private site R2 bucket for publication:

- `index.html`: generated dashboard.

The separation is deliberate blast-radius reduction: the public-facing Worker binds only to the
site bucket, so a routing bug cannot expose raw email, CSV, manifest, or Parquet objects.

Do not add a database by default. Prefer deterministic object keys, attachment content hashes, and
manifest objects for idempotence. Add D1/Durable Objects/Queues only if a concrete coordination
problem appears.

## Ingestion Shape

Use a dedicated Email Routing address on `robjhornby.com`, configured as a variable rather than
hard-coded infrastructure state. `basement-ingest` is the default local part unless the source-email
setup ticket chooses a better address. X-Sense can send directly to that address if its export flow
supports it; otherwise Gmail should forward only matching X-Sense daily CSV emails to the same
address while keeping Gmail's copy for recovery.

The first ingest runtime should be a small TypeScript Email Worker deployed with Wrangler, not a
Python analysis worker. Its job is to land immutable evidence and minimal derived ingest state:

```text
Cloudflare Email Routing rule
  -> email-ingest Worker
  -> raw .eml object
  -> extracted CSV attachment objects
  -> ingest manifest JSON object
```

The Email Worker should parse the raw MIME message with `postal-mime`, validate the current X-Sense
shape narrowly, and avoid physical analysis or Parquet generation. Derived Parquet remains owned by
the Python parser/analysis path so local and hosted processing stay equivalent.

Recommended object keys:

```text
raw-emails/source=x-sense/received_date=YYYY-MM-DD/raw_sha256=<raw_sha256>.eml
csv/source=x-sense/export_date=YYYY-MM-DD/attachment_sha256=<csv_sha256>/<safe_filename>.csv
manifests/ingest/source=x-sense/received_date=YYYY-MM-DD/raw_sha256=<raw_sha256>.json
manifests/rejections/source=x-sense/received_date=YYYY-MM-DD/raw_sha256=<raw_sha256>.json
parquet/<existing local curated dataset layout>
```

The manifest should store the raw object key, raw SHA-256, message headers used for audit and
dedupe (`Message-ID`, `Date`, `From`, `To`, `Subject`), attachment keys and SHA-256 values, parser
version, validation result, and any rejection reason. R2 object custom metadata may duplicate small
lookup fields, but the JSON manifest is the durable audit record.

Use content-addressed keys and R2 conditional writes for idempotence. Duplicate raw emails and
duplicate attachments should become no-op writes plus manifest evidence, not database rows. If a
later hosted trigger needs coordination, prefer scanning manifests or adding a narrow queue before
adding D1 or Durable Objects.

## Execution Shape

The hosted analysis job is a GitHub Actions workflow in the public
`robjhornby/basement-plant` repository. It runs `uv run basement --reuse-curated` with DuckDB
reading `s3://basement-pipeline/parquet` directly through R2's S3-compatible endpoint, then writes
the rendered `index.html` file to the dedicated `basement-site` bucket using R2 S3-compatible
credentials scoped to the pipeline and site buckets. The local physics/metrology report remains a
private opt-in render and is not published.

This replaces the rejected Cloudflare Container path: Containers require the Workers Paid plan,
and free Workers cannot host the Python/DuckDB analysis workload.

## Publication Shape

Publish static artifacts as R2 objects behind a small GET-only Worker route. The Worker binds to
the `basement-site` bucket on `robjhornby.com/basement*` and serves only:

- `/basement` -> `/basement/` (`308`)
- `/basement/` and `/basement/index.html` -> `index.html`

Pages and Workers static assets are intentionally not used because they couple daily content
publishes to a Wrangler/Node code deploy. The Worker code deploy is rare; daily publication is just
R2 object writes by the analysis runner.


## Deployment Shape

Cloudflare resources should use the split-control model decided during wayfinding:

- OpenTofu under `infra/cloudflare/tofu/` owns durable account/zone resources such as R2 buckets,
  DNS, Email Routing rules where provider support is clean, and later durable coordination
  resources only when a concrete need appears.
- Wrangler owns deployable runtime projects under `infra/cloudflare/workers/<name>/`, including
  Worker source, compatibility dates/flags, bindings, local development, and deploys.
- Narrow scripts under `infra/cloudflare/scripts/` are allowed for imports, smoke tests, fixture
  uploads, Pages direct upload, and provider/API gaps. Desired state should move into OpenTofu or
  Wrangler when possible.

## Superseded Direction

The previous AWS SES plus S3 plan is superseded. Keep its issue history as design context, but do
not create AWS resources for this effort. This does not rule out OpenTofu for Cloudflare resources.

## References

- Cloudflare Email Workers: https://developers.cloudflare.com/email-service/api/route-emails/email-handler/
- Cloudflare Python Workers: https://developers.cloudflare.com/workers/languages/python/
- Cloudflare Python package support: https://developers.cloudflare.com/workers/languages/python/packages/
- Cloudflare R2 Workers API: https://developers.cloudflare.com/r2/api/workers/workers-api-reference/
- Cloudflare R2 uploads from Workers: https://developers.cloudflare.com/r2/objects/upload-objects/
- Cloudflare Containers: https://developers.cloudflare.com/containers/
