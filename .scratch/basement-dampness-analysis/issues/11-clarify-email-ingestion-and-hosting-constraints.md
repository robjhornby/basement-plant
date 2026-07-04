# Clarify email ingestion and hosting constraints

Type: grilling
Status: resolved
Parent: ../map.md

## Question

What are the practical constraints around the daily emailed CSVs, storage, automation, credentials, and publishing to `robjhornby.com`?

Ask the user one question at a time about email provider, attachment naming, delivery time, whether the inbox can be accessed by IMAP/API/forwarding, acceptable hosted services, budget ceiling, privacy constraints, domain/DNS control, desired uptime, and tolerance for manual recovery.

## Answer

Use a local-first, AWS-backed ingestion path:

`X-Sense email -> Gmail filter auto-forward -> SES inbound address -> S3 raw email store -> batch Python processing`

The daily CSV emails can be auto-forwarded from Gmail. Gmail supports automatic forwarding and filters, and filters can match attached CSVs using attachment-oriented search terms such as `has:attachment` or `filename:csv`. The forwarding target should be a dedicated ingest address, not the user's personal mailbox.

Use Amazon SES inbound receiving in `eu-west-2` with a dedicated subdomain or address such as `basement-ingest@ingest.robjhornby.com`. The user controls `robjhornby.com` DNS through Cloudflare and prefers scriptable configuration through Cloudflare CLI/API and OpenTofu/Terraform rather than the web UI. SES should save the full raw email object to S3; processing should later parse the raw `.eml` and extract CSV attachments. AWS documentation confirms SES receipt rules can save received messages to S3, with a default maximum received email size of 40 MB.

Provisioning should use OpenTofu/Terraform for AWS and Cloudflare resources, with small Python helper scripts where useful. Secrets and credentials should stay out of the repo and be loaded from local environment, AWS profiles, or equivalent local secret configuration.

The first processing implementation should be batch/pull-based rather than event-driven: a local or server cron job lists new S3 raw email objects, extracts CSV attachments, records processed object keys, and writes normalized data. This is deliberately a simple first step. If live automation later matters, the same raw S3 store and parser can be triggered by S3/SNS/SQS/Lambda or a small worker without changing the ingestion evidence trail.

Uptime should be low-ops and recoverable, not high-availability. If ingestion breaks for a few days, raw emails should remain recoverable from Gmail and/or S3, and a manual backfill command should catch up.

Budget should target near-zero to a few pounds per month for ingestion storage and scheduled processing. Any always-on server or dashboard hosting cost should be separately justified.

Privacy boundary:

- Private: raw emails, raw CSV files as files, exact device IDs, exact ingest address, exact address/location, AWS/Cloudflare credentials, and processing state with operational identifiers.
- Public if useful: raw measurement plots, derived basement metrics, approximate Caversham weather context, and caveated analysis results.

Assume untrusted delivery and naming at first. Do not rely on stable attachment filenames, exact delivery time, or a single non-duplicated forward. Use S3 object key, email `Message-ID`, and attachment content hash for dedupe, and parse CSV content/headers rather than trusting filenames. This assumption can be relaxed later if the actual emails prove consistent.

Publishing to `robjhornby.com` should start as static generated artifacts, not a live dashboard server. Generate HTML/PNG/JSON from the Python analysis pipeline and publish under a path such as `robjhornby.com/basement/`; defer a live API/dashboard server until the analysis has stabilized.

Useful source references:

- Gmail automatic forwarding and filters: https://support.google.com/mail/answer/10957
- Gmail search operators for `has:attachment` and `filename:`: https://support.google.com/mail/answer/7190
- SES inbound email receiving: https://docs.aws.amazon.com/ses/latest/dg/receiving-email.html
- SES S3 receipt action: https://docs.aws.amazon.com/ses/latest/dg/receiving-email-action-s3.html
- SES inbound MX records: https://docs.aws.amazon.com/ses/latest/dg/receiving-email-mx-record.html
- SES endpoints and email receiving regions: https://docs.aws.amazon.com/general/latest/gr/ses.html
