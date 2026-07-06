# Copy to env/production.tfvars (gitignored values welcome) and fill in real IDs.
account_id = "00000000000000000000000000000000"
zone_id    = "00000000000000000000000000000000"

# Defaults shown; override only if the design changes.
# zone_name                 = "robjhornby.com"
# pipeline_bucket_name      = "basement-pipeline"
# site_bucket_name          = "basement-site"
# r2_location               = "WEUR"
# ingest_address_local_part = "basement-ingest"
# email_ingest_worker_name  = "basement-email-ingest"
# site_worker_subdomain     = "basement"

# Flip to true after the first `wrangler deploy` of the email-ingest Worker.
# create_email_ingest_rule = false
