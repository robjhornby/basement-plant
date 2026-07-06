# Wire durable production forwarding of the daily X-Sense email to the ingest address

Type: task
Status: open
Parent: ../map.md
Blocked by:

## Question

The email→R2 ingest path is deployed and verified
([Deploy and smoke-test the email ingest path end to end](40-deploy-and-smoke-test-email-ingest-path.md)),
but nothing yet delivers the *daily* X-Sense export to `basement-ingest@robjhornby.com` on its own.
The smoke test used a one-off manual Gmail forward with the subject hand-edited back to the exact
accepted value.

Decide and wire the durable mechanism. The Worker accepts only messages whose subject is *exactly*
`Your Temperature and Relative Humidity Data Export (Please Do Not Reply)` with exactly three valid
CSV attachments, so the mechanism must preserve the original subject (no `Fwd:` prefix) and the
attachments.

Two candidate approaches:

1. **Gmail filter auto-forward** — a filter matching the X-Sense sender/subject that forwards to
   `basement-ingest@robjhornby.com`. Gmail filter-forwarding re-sends with the original subject
   intact (no `Fwd:`) and keeps attachments. Requires adding + verifying the forwarding address in
   Gmail settings first.
2. **Point X-Sense directly** at `basement-ingest@robjhornby.com` (change or add the export
   recipient in the X-Sense app), removing Gmail from the path entirely.

Resolve by choosing one, setting it up, and confirming (via the R2 manifests) that a real daily
email is ingested without manual intervention. Record which approach was chosen and any config
location (Gmail filter, X-Sense export settings) later operations depend on.
