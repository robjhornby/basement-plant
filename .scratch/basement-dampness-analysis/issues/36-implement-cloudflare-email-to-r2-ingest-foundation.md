# Implement Cloudflare email-to-R2 ingest foundation

Type: task
Status: open
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
