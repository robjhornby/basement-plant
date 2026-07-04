# Provision email-to-S3 ingest infrastructure

Type: task
Status: open
Parent: ../map.md
Blocked by: 12, 14

## Question

What scriptable infrastructure should be created to receive forwarded X-Sense CSV emails and store raw email objects privately in S3?

Implement or specify the OpenTofu/Terraform resources and helper commands for AWS SES inbound receiving in `eu-west-2`, the private S3 raw email store, IAM/bucket permissions, Cloudflare DNS records for the ingest subdomain/address, and a verification path that proves a forwarded email with CSV attachments lands in S3. Keep secrets out of the repo and document local environment/profile assumptions.
