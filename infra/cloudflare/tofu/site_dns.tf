# Proxied placeholder record so the Wrangler-managed Worker route
# `basement.robjhornby.com/*` receives traffic through Cloudflare.
resource "cloudflare_dns_record" "site_worker_subdomain" {
  zone_id = var.zone_id
  name    = var.site_worker_subdomain
  type    = "A"
  content = "192.0.2.1"
  ttl     = 1
  proxied = true
}
