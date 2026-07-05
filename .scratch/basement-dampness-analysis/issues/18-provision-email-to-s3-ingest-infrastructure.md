# Provision email-to-S3 ingest infrastructure

Type: task
Status: resolved
Parent: ../map.md

Superseded by: 27

## Question

What scriptable infrastructure should be created to receive forwarded X-Sense CSV emails and store raw email objects privately in S3?

This is later-phase remote ingestion work. Do not start it until the local CSV-to-static-site
pipeline is useful, the raw email processing-state prototype exists, and the user has reviewed the
prototype outcome.

The feedback checkpoint is now resolved: assume the real sample email shape is representative, use
the exact current X-Sense subject/attachment pattern for the first production pass, and let
production reveal whether forwarded copies preserve `Message-ID`.

Implement or specify the OpenTofu/Terraform resources and helper commands for AWS SES inbound receiving in `eu-west-2`, the private S3 raw email store, IAM/bucket permissions, Cloudflare DNS records for the ingest subdomain/address, and a verification path that proves a forwarded email with CSV attachments lands in S3. Keep secrets out of the repo and document local environment/profile assumptions.

## Answer

Superseded direction as of `2026-07-05`: the project should not proceed with AWS SES or S3. The
current hosted target is Cloudflare Email Routing/Email Workers receiving the daily X-Sense CSV
emails, R2 storing raw emails plus extracted CSV/Parquet files, and Cloudflare-hosted automation
generating/publishing the static site. See [Adopt Cloudflare-only email/R2/static-site pipeline](27-adopt-cloudflare-only-email-r2-static-site-pipeline.md).

The earlier scratch-contained OpenTofu package for AWS SES/S3 was removed rather than promoted,
because it contradicted the Cloudflare-only direction and was in the wrong place for durable
infrastructure. Future infrastructure should live under `infra/cloudflare/`.
