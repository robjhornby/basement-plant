terraform {
  required_version = ">= 1.8.0"

  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 6.0"
    }

    cloudflare = {
      source  = "cloudflare/cloudflare"
      version = "~> 5.0"
    }
  }
}

provider "aws" {
  region = var.aws_region
}

provider "cloudflare" {}

data "aws_caller_identity" "current" {}

locals {
  ingest_email_address  = "${var.ingest_local_part}@${var.ingest_domain}"
  raw_email_bucket_name = coalesce(var.raw_email_bucket_name, "basement-x-sense-raw-email-${data.aws_caller_identity.current.account_id}")
  receipt_rule_name     = "${var.project_name}-store-raw-x-sense-email"
  receipt_rule_set_name = "${var.project_name}-inbound"
  ses_receipt_rule_arn  = "arn:aws:ses:${var.aws_region}:${data.aws_caller_identity.current.account_id}:receipt-rule-set/${local.receipt_rule_set_name}:receipt-rule/${local.receipt_rule_name}"
}

resource "aws_s3_bucket" "raw_email" {
  bucket = local.raw_email_bucket_name

  tags = {
    Project = var.project_name
    Purpose = "x-sense-raw-email-ingest"
  }
}

resource "aws_s3_bucket_public_access_block" "raw_email" {
  bucket = aws_s3_bucket.raw_email.id

  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

resource "aws_s3_bucket_ownership_controls" "raw_email" {
  bucket = aws_s3_bucket.raw_email.id

  rule {
    object_ownership = "BucketOwnerEnforced"
  }
}

resource "aws_s3_bucket_server_side_encryption_configuration" "raw_email" {
  bucket = aws_s3_bucket.raw_email.id

  rule {
    apply_server_side_encryption_by_default {
      sse_algorithm = "AES256"
    }
  }
}

resource "aws_s3_bucket_versioning" "raw_email" {
  bucket = aws_s3_bucket.raw_email.id

  versioning_configuration {
    status = "Enabled"
  }
}

data "aws_iam_policy_document" "allow_ses_puts" {
  statement {
    sid = "AllowSESPuts"

    principals {
      type        = "Service"
      identifiers = ["ses.amazonaws.com"]
    }

    actions = ["s3:PutObject"]

    resources = [
      "${aws_s3_bucket.raw_email.arn}/${var.raw_email_object_prefix}*",
    ]

    condition {
      test     = "StringEquals"
      variable = "AWS:SourceAccount"
      values   = [data.aws_caller_identity.current.account_id]
    }

    condition {
      test     = "StringEquals"
      variable = "AWS:SourceArn"
      values   = [local.ses_receipt_rule_arn]
    }
  }
}

resource "aws_s3_bucket_policy" "allow_ses_puts" {
  bucket = aws_s3_bucket.raw_email.id
  policy = data.aws_iam_policy_document.allow_ses_puts.json
}

resource "aws_ses_domain_identity" "ingest" {
  domain = var.ingest_domain
}

resource "cloudflare_dns_record" "ses_domain_verification" {
  zone_id = var.cloudflare_zone_id
  name    = "_amazonses.${var.ingest_domain}"
  type    = "TXT"
  content = aws_ses_domain_identity.ingest.verification_token
  ttl     = 300
  comment = "SES domain verification for basement X-Sense email ingest"
}

resource "aws_ses_domain_identity_verification" "ingest" {
  domain = aws_ses_domain_identity.ingest.domain

  depends_on = [
    cloudflare_dns_record.ses_domain_verification,
  ]
}

resource "cloudflare_dns_record" "ingest_mx" {
  zone_id  = var.cloudflare_zone_id
  name     = var.ingest_domain
  type     = "MX"
  content  = "inbound-smtp.${var.aws_region}.amazonaws.com"
  priority = 10
  ttl      = 300
  comment  = "Route basement X-Sense ingest mail to Amazon SES inbound receiving"
}

resource "aws_ses_receipt_rule_set" "main" {
  rule_set_name = local.receipt_rule_set_name
}

resource "aws_ses_receipt_rule" "store_raw_x_sense_email" {
  name          = local.receipt_rule_name
  rule_set_name = aws_ses_receipt_rule_set.main.rule_set_name
  recipients    = [local.ingest_email_address]
  enabled       = true
  scan_enabled  = true
  tls_policy    = "Require"

  s3_action {
    bucket_name       = aws_s3_bucket.raw_email.bucket
    object_key_prefix = var.raw_email_object_prefix
    position          = 1
  }

  depends_on = [
    aws_s3_bucket_policy.allow_ses_puts,
    aws_ses_domain_identity_verification.ingest,
  ]
}

resource "aws_ses_active_receipt_rule_set" "main" {
  rule_set_name = aws_ses_receipt_rule_set.main.rule_set_name

  depends_on = [
    aws_ses_receipt_rule.store_raw_x_sense_email,
  ]
}
