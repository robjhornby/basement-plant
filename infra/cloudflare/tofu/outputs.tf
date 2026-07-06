output "pipeline_bucket_name" {
  description = "R2 bucket the email-ingest Worker binds to (wrangler.jsonc bucket_name)."
  value       = cloudflare_r2_bucket.pipeline.name
}

output "ingest_email_address" {
  description = "Address X-Sense (or the Gmail forwarding rule) should send daily exports to."
  value       = local.ingest_email_address
}
