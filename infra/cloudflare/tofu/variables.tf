variable "account_id" {
  description = "Cloudflare account ID that owns the R2 bucket and Workers."
  type        = string
}

variable "zone_id" {
  description = "Cloudflare zone ID for the email-receiving zone (robjhornby.com)."
  type        = string
}

variable "zone_name" {
  description = "Zone apex domain used to build the ingest email address."
  type        = string
  default     = "robjhornby.com"
}

variable "pipeline_bucket_name" {
  description = "Name of the single private R2 pipeline bucket (raw emails, CSVs, manifests, parquet)."
  type        = string
  default     = "basement-pipeline"
}

variable "site_bucket_name" {
  description = "Name of the private R2 bucket holding generated static site HTML."
  type        = string
  default     = "basement-site"
}

variable "r2_location" {
  description = "R2 location hint for project buckets."
  type        = string
  default     = "WEUR"
}

variable "ingest_address_local_part" {
  description = "Local part of the dedicated ingest address (local-part@zone_name)."
  type        = string
  default     = "basement-ingest"
}

variable "email_ingest_worker_name" {
  description = "Deployed name of the email-ingest Worker (must match wrangler.jsonc name)."
  type        = string
  default     = "basement-email-ingest"
}

variable "site_worker_subdomain" {
  description = "Subdomain used for the public basement site Worker route."
  type        = string
  default     = "basement"
}

variable "create_email_ingest_rule" {
  description = <<-EOT
    Create the Email Routing rule that sends the ingest address to the Worker.
    Leave false for the first apply: the rule can only reference a Worker that is
    already deployed, so the order is tofu apply -> wrangler deploy -> set this
    true -> tofu apply again.
  EOT
  type        = bool
  default     = false
}
