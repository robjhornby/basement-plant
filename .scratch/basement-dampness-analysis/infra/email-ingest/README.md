# Basement Email Ingest Infrastructure

This OpenTofu package provisions the first remote ingest path:

```text
Gmail filtered forward -> basement-ingest@ingest.robjhornby.com -> SES inbound eu-west-2 -> private S3 raw .eml objects
```

It does not configure Gmail. That remains the next ticket, after the SES address exists and has been verified.

## Local Assumptions

- OpenTofu is installed as `tofu`.
- AWS credentials are supplied by `AWS_PROFILE` or the normal AWS SDK environment.
- The Cloudflare provider reads `CLOUDFLARE_API_TOKEN` from the environment.
- The token can edit DNS records in the `robjhornby.com` zone.
- No secrets are committed. Local `*.tfvars`, state, plans, and `.terraform/` are ignored.
- Commit `.terraform.lock.hcl`; it pins provider selections and contains no credentials.

## Provision

```bash
cd .scratch/basement-dampness-analysis/infra/email-ingest
cp terraform.tfvars.example terraform.tfvars
$EDITOR terraform.tfvars

export AWS_PROFILE=replace-with-aws-profile
export CLOUDFLARE_API_TOKEN=replace-with-cloudflare-token

tofu init
tofu plan -out email-ingest.tfplan
tofu apply email-ingest.tfplan
```

The module creates:

- SES domain identity for `ingest.robjhornby.com`.
- Cloudflare TXT record for SES domain verification.
- Cloudflare MX record from `ingest.robjhornby.com` to `inbound-smtp.eu-west-2.amazonaws.com`.
- Private, versioned, SSE-S3 encrypted raw email bucket.
- Bucket policy allowing only this SES receipt rule to write under `raw/x-sense/`.
- Active SES receipt rule set and one receipt rule for `basement-ingest@ingest.robjhornby.com`.

This module activates its SES receipt rule set in `eu-west-2`. If that AWS account already has an active SES receiving rule set in `eu-west-2`, import or merge it before applying.

## Verify

Check DNS:

```bash
dig +short TXT _amazonses.ingest.robjhornby.com
dig +short MX ingest.robjhornby.com
```

Check SES verification:

```bash
aws ses get-identity-verification-attributes \
  --region eu-west-2 \
  --identities ingest.robjhornby.com
```

Send or forward one representative X-Sense email with CSV attachments to the `ingest_email_address` output, then confirm an object landed in S3:

```bash
BUCKET="$(tofu output -raw raw_email_bucket_name)"
PREFIX="$(tofu output -raw raw_email_object_prefix)"

aws s3 ls "s3://${BUCKET}/${PREFIX}" --region eu-west-2 --recursive
```

Download the newest raw object manually and run it through the raw-email parser prototype before treating the path as proven:

```bash
mkdir -p downloaded
aws s3 cp "s3://${BUCKET}/${PREFIX}<object-key-suffix>" downloaded/sample.eml --region eu-west-2
uv run python ../../prototypes/19-raw-email-csv-processing-state.py
```

The prototype currently reads its checked-in sample path, so productionizing the parser needs a later small change to accept a local raw-email folder or S3 prefix as an argument.

## Source Notes

- AWS SES receiving setup requires domain verification, MX routing, and permissions for receipt-rule actions.
- AWS lists `inbound-smtp.eu-west-2.amazonaws.com` as the SES email receiving endpoint for Europe (London).
- AWS documents S3 receipt-action bucket policies using `ses.amazonaws.com` plus `AWS:SourceAccount` and `AWS:SourceArn`.
- Cloudflare DNS records are managed through `cloudflare_dns_record`, with MX priority specified separately.
