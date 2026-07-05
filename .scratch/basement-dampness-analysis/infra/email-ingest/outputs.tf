output "ingest_email_address" {
  description = "Address to configure as the Gmail forwarding target."
  value       = local.ingest_email_address
}

output "ingest_domain" {
  description = "Dedicated subdomain routed to Amazon SES inbound receiving."
  value       = var.ingest_domain
}

output "ses_inbound_mx_target" {
  description = "MX target for SES inbound receiving in eu-west-2."
  value       = "inbound-smtp.${var.aws_region}.amazonaws.com"
}

output "raw_email_bucket_name" {
  description = "Private S3 bucket that stores raw .eml objects written by SES."
  value       = aws_s3_bucket.raw_email.bucket
}

output "raw_email_object_prefix" {
  description = "Prefix under the raw email bucket where SES writes messages."
  value       = var.raw_email_object_prefix
}

output "ses_receipt_rule_name" {
  description = "SES receipt rule that stores accepted X-Sense emails in S3."
  value       = aws_ses_receipt_rule.store_raw_x_sense_email.name
}

output "ses_receipt_rule_set_name" {
  description = "Active SES receipt rule set managed by this module."
  value       = aws_ses_receipt_rule_set.main.rule_set_name
}
