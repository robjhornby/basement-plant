# Design Cloudflare email-to-R2 ingest

Type: task
Status: open
Parent: ../map.md
Blocked by: 31

## Question

What Cloudflare Email Routing / Email Worker and R2 resources should receive the daily X-Sense CSV
emails, store raw `.eml` objects, extract CSV attachments, write derived Parquet files, and preserve
enough object-key/hash metadata for idempotent reprocessing without a database?

Keep the source-email path explicit: support direct X-Sense delivery to the Cloudflare ingest
address if possible, and Gmail forwarding to that same address if Gmail remains the practical
recipient for X-Sense exports.
