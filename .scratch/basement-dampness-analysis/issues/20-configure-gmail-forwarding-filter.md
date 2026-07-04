# Configure Gmail forwarding filter

Type: task
Status: open
Parent: ../map.md
Blocked by: 18

## Question

What exact Gmail forwarding filter should send X-Sense CSV emails to the ingest mailbox without exposing the personal inbox to the pipeline?

Create the dedicated forwarding setup after the ingest address exists. The filter should match the X-Sense sender/subject and CSV attachments, forward only matching messages, keep Gmail's copy for recovery, and include a manual test/backfill checklist for recent historical CSV emails.
