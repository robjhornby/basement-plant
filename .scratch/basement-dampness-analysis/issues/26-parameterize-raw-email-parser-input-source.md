# Parameterize raw email parser input source

Type: task
Status: open
Parent: ../map.md
Blocked by: 29

## Question

How should the raw-email parser/backfill command be changed so it can process raw `.eml` objects
from a local folder or R2-style object prefix instead of only the checked-in prototype sample path?

Use the Cloudflare storage layout from [Adopt Cloudflare-only email/R2/static-site pipeline](27-adopt-cloudflare-only-email-r2-static-site-pipeline.md)
as the remote source shape. Keep the command local-first and batch-oriented: it should be possible
to download a landed R2 object to disk and verify parsing before wiring direct R2 listing into the
production parser.
