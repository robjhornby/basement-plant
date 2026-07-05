# Parameterize raw email parser input source

Type: task
Status: open
Parent: ../map.md
Blocked by: 18

## Question

How should the raw-email parser/backfill command be changed so it can process raw `.eml` objects
from a local folder or S3 prefix instead of only the checked-in prototype sample path?

Use the SES/S3 object layout from [Provision email-to-S3 ingest infrastructure](18-provision-email-to-s3-ingest-infrastructure.md)
as the remote source shape. Keep the command local-first and batch-oriented: it should be possible
to download a landed S3 object to disk and verify parsing before wiring direct S3 listing into the
production parser.
