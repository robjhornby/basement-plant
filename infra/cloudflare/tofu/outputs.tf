output "pipeline_bucket_name" {
  description = "R2 bucket the email-ingest Worker binds to (wrangler.jsonc bucket_name)."
  value       = cloudflare_r2_bucket.pipeline.name
}

output "site_bucket_name" {
  description = "R2 bucket the site Worker binds to and the analysis runner publishes HTML into."
  value       = cloudflare_r2_bucket.site.name
}

output "ingest_email_address" {
  description = "Address X-Sense (or the Gmail forwarding rule) should send daily exports to."
  value       = local.ingest_email_address
}
