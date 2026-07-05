variable "aws_region" {
  description = "AWS region for SES inbound receiving and the raw email S3 bucket."
  type        = string
  default     = "eu-west-2"

  validation {
    condition     = var.aws_region == "eu-west-2"
    error_message = "This ingest module is intentionally locked to eu-west-2 for the current basement workflow."
  }
}

variable "cloudflare_zone_id" {
  description = "Cloudflare zone ID for robjhornby.com."
  type        = string
}

variable "project_name" {
  description = "Short resource-name prefix."
  type        = string
  default     = "basement"

  validation {
    condition     = can(regex("^[a-z0-9-]+$", var.project_name))
    error_message = "Use lower-case letters, numbers, and hyphens only."
  }
}

variable "ingest_domain" {
  description = "Dedicated receiving subdomain. Do not point the apex domain at SES."
  type        = string
  default     = "ingest.robjhornby.com"

  validation {
    condition     = !strcontains(var.ingest_domain, "@")
    error_message = "Use a domain name, not an email address."
  }
}

variable "ingest_local_part" {
  description = "Local part for the SES recipient address."
  type        = string
  default     = "basement-ingest"

  validation {
    condition     = can(regex("^[a-z0-9._%+-]+$", var.ingest_local_part))
    error_message = "Use a valid lower-case email local part."
  }
}

variable "raw_email_bucket_name" {
  description = "Globally unique S3 bucket name. Defaults to basement-x-sense-raw-email-<account-id>."
  type        = string
  default     = null
}

variable "raw_email_object_prefix" {
  description = "S3 object prefix for raw .eml objects written by SES."
  type        = string
  default     = "raw/x-sense/"

  validation {
    condition     = can(regex("/$", var.raw_email_object_prefix))
    error_message = "The raw email object prefix should end with a slash."
  }
}
