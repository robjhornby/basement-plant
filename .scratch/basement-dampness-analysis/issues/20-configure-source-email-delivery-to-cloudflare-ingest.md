# Configure source email delivery to Cloudflare ingest

Type: task
Status: resolved
Parent: ../map.md
Blocked by: 29, 36, 40

## Question

What exact source-email setup should deliver daily X-Sense CSV emails to the Cloudflare ingest
address without exposing the personal inbox to the processing pipeline?

Prefer direct X-Sense delivery to the Cloudflare Email Routing address if the X-Sense export flow
allows it. If Gmail remains the practical recipient, configure a Gmail forwarding filter that
matches the X-Sense sender/subject and CSV attachments, forwards only matching messages, keeps
Gmail's copy for recovery, and includes a manual test/backfill checklist for recent historical CSV
emails.

(The later duplicate
[Wire durable production email forwarding](41-wire-durable-production-email-forwarding.md) added the
post-deployment constraints: the Worker accepts only the exact subject
`Your Temperature and Relative Humidity Data Export (Please Do Not Reply)` with exactly three valid
CSV attachments, so the mechanism must preserve the original subject — no `Fwd:` prefix — and the
attachments.)

## Answer

Decision (user, 2026-07-06): **point X-Sense directly** at `basement-ingest@robjhornby.com` as the
durable automated delivery mechanism — change/add the export recipient in the X-Sense app so the
daily export goes straight to Cloudflare Email Routing, keeping the personal Gmail inbox out of the
processing pipeline entirely. No Gmail filter auto-forward will be set up.

Interim, while setting up and manually testing: the user forwards emails by hand. Operational
caveat for that period — a manual Gmail forward carries a `Fwd:` subject prefix, which the Worker
rejects (`subject_mismatch`); either hand-edit the subject back to the exact accepted value before
forwarding (as the [ticket 40](40-deploy-and-smoke-test-email-ingest-path.md) smoke test did), or
accept that the message lands as raw `.eml` + rejection manifest in R2, from which it is fully
recoverable. Nothing is lost either way.

Remaining user checklist (small, no further investigation needed):

1. In the X-Sense app, set/add `basement-ingest@robjhornby.com` as the data-export recipient.
2. After the next daily export, confirm unattended ingestion via the R2 manifests: a new
   `manifests/ingest/…json` accepted manifest (plus raw `.eml` and three CSV objects) in
   `basement-pipeline` with no manual forwarding involved.

Config locations later operations depend on: the export recipient lives in the X-Sense app's data
export settings; there is no Gmail filter or Gmail forwarding-address verification to maintain.
