# Authentication comes from the environment, never from checked-in files:
#   export CLOUDFLARE_API_TOKEN=...   (token scoped to R2 + Email Routing + DNS for the zone)
provider "cloudflare" {}
