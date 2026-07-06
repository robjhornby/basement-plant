# Single private pipeline bucket. Prefixes, object keys, content hashes, and
# manifests are application concerns owned by the email-ingest Worker and the
# Python parser/analysis path, not by infrastructure.
resource "cloudflare_r2_bucket" "pipeline" {
  account_id = var.account_id
  name       = var.pipeline_bucket_name
  location   = var.r2_location
}
