# Provision email-to-S3 ingest infrastructure

Type: task
Status: resolved
Parent: ../map.md

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

Created a scratch-contained OpenTofu package for the first remote raw-email landing path:

[Basement Email Ingest Infrastructure](../infra/email-ingest/README.md)

The implemented shape is:

`Gmail filtered forward -> basement-ingest@ingest.robjhornby.com -> SES inbound eu-west-2 -> private S3 raw .eml objects under raw/x-sense/`

Artifacts:

- [main.tf](../infra/email-ingest/main.tf) defines AWS, Cloudflare, SES, S3, and IAM/bucket-policy resources.
- [variables.tf](../infra/email-ingest/variables.tf) locks this workflow to `eu-west-2`, defaults the ingest address to `basement-ingest@ingest.robjhornby.com`, and keeps bucket naming configurable.
- [outputs.tf](../infra/email-ingest/outputs.tf) exposes the forwarding address, SES MX target, bucket, prefix, and SES receipt rule names.
- [terraform.tfvars.example](../infra/email-ingest/terraform.tfvars.example) documents the one required local value, `cloudflare_zone_id`.
- [README.md](../infra/email-ingest/README.md) records the provisioning and verification commands.

The module creates:

- SES domain identity for `ingest.robjhornby.com`;
- Cloudflare TXT record for SES verification;
- Cloudflare MX record pointing `ingest.robjhornby.com` at `inbound-smtp.eu-west-2.amazonaws.com`;
- a private, public-access-blocked, versioned, SSE-S3 encrypted raw email bucket;
- a bucket policy allowing only `ses.amazonaws.com` from the specific receipt rule ARN and AWS account to write under `raw/x-sense/`;
- an SES receipt rule set, one TLS-required receipt rule for `basement-ingest@ingest.robjhornby.com`, spam/malware scanning enabled, and S3 delivery as the first action;
- activation of that SES receipt rule set in `eu-west-2`.

Operator assumptions:

- `tofu` is installed locally.
- AWS credentials come from `AWS_PROFILE` or the normal AWS SDK environment.
- Cloudflare credentials come from `CLOUDFLARE_API_TOKEN`.
- The Cloudflare token can edit DNS records in the `robjhornby.com` zone.
- Local `*.tfvars`, state, plans, provider cache, and downloaded raw emails stay ignored by the package `.gitignore`.

Verification path:

1. Apply the OpenTofu package from `../infra/email-ingest`.
2. Check SES DNS with `dig +short TXT _amazonses.ingest.robjhornby.com` and `dig +short MX ingest.robjhornby.com`.
3. Check SES identity verification with `aws ses get-identity-verification-attributes --region eu-west-2 --identities ingest.robjhornby.com`.
4. Send or forward one representative X-Sense email with CSV attachments to the `ingest_email_address` output.
5. Confirm raw `.eml` object arrival with `aws s3 ls "s3://${BUCKET}/${PREFIX}" --region eu-west-2 --recursive`.
6. Download one landed object and run it through the raw-email parser prototype before treating the path as proven.

Important caveats:

- Post-resolution validation on `2026-07-05`: `tofu fmt -recursive`, `tofu init`, and `tofu validate` passed with OpenTofu `1.12.3`, `hashicorp/aws` `6.53.0`, and `cloudflare/cloudflare` `5.21.1`.
- I could not run `tofu plan` because this shell does not have `terraform.tfvars`, `AWS_PROFILE`, or `CLOUDFLARE_API_TOKEN` configured.
- This module activates its SES receipt rule set in `eu-west-2`; if the AWS account already has an active SES receiving rule set there, import or merge that state before applying.
- The existing parser prototype still reads its checked-in sample path. A new follow-up ticket, [Parameterize raw email parser input source](26-parameterize-raw-email-parser-input-source.md), captures the production step to accept a local raw-email folder or S3 prefix.

Source references used:

- AWS SES receiving setup prerequisites: https://docs.aws.amazon.com/ses/latest/dg/receiving-email-setting-up.html
- AWS SES MX record guidance: https://docs.aws.amazon.com/ses/latest/dg/receiving-email-mx-record.html
- AWS SES `eu-west-2` inbound endpoint: https://docs.aws.amazon.com/general/latest/gr/ses.html
- AWS SES S3 action permission policy shape: https://docs.aws.amazon.com/ses/latest/dg/receiving-email-permissions.html
- AWS SES S3 delivery concepts and 40 MB S3 receipt limit: https://docs.aws.amazon.com/ses/latest/dg/receiving-email-concepts.html
- Cloudflare Terraform DNS record resource: https://github.com/cloudflare/terraform-provider-cloudflare/blob/main/docs/resources/dns_record.md
