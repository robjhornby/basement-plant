# Single private pipeline bucket. Prefixes, object keys, content hashes, and
# manifests are application concerns owned by the email-ingest Worker and the
# Python parser/analysis path, not by infrastructure.
resource "cloudflare_r2_bucket" "pipeline" {
  account_id = var.account_id
  name       = var.pipeline_bucket_name
  location   = var.r2_location
}

# Dedicated publication bucket. The public-facing Worker binds only to this
# bucket so routing bugs cannot expose raw email, CSV, manifest, or Parquet
# objects from the private pipeline bucket.
resource "cloudflare_r2_bucket" "site" {
  account_id = var.account_id
  name       = var.site_bucket_name
  location   = var.r2_location
}
