# Configure source email delivery to Cloudflare ingest

Type: task
Status: open
Parent: ../map.md
Blocked by: 29

## Question

What exact source-email setup should deliver daily X-Sense CSV emails to the Cloudflare ingest
address without exposing the personal inbox to the processing pipeline?

Prefer direct X-Sense delivery to the Cloudflare Email Routing address if the X-Sense export flow
allows it. If Gmail remains the practical recipient, configure a Gmail forwarding filter that
matches the X-Sense sender/subject and CSV attachments, forwards only matching messages, keeps
Gmail's copy for recovery, and includes a manual test/backfill checklist for recent historical CSV
emails.
