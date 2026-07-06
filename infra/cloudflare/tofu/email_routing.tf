# Email Routing enablement and the routing DNS records (MX + SPF) are NOT
# managed here: the /email/routing settings, /enable, and /dns endpoints are
# not authorizable by a scoped API token (they return 403 "Authentication
# error" even for a read, and even after the zone is enabled). They are a
# one-time dashboard action per zone:
#
#   dash.cloudflare.com -> robjhornby.com -> Email -> Email Routing -> enable
#
# That enables routing and adds the route{1,2,3}.mx.cloudflare.net MX records
# plus the SPF TXT record automatically. The routing RULE below uses the
# /email/routing/rules endpoint, which the token CAN reach, so it stays in
# tofu. See README.md "Provider support gaps and manual steps".

# Route the dedicated ingest address to the email-ingest Worker.
#
# The rule can only reference a Worker that already exists, so it is gated
# behind create_email_ingest_rule: first apply creates bucket + routing DNS,
# then `wrangler deploy` publishes the Worker, then a second apply with
# create_email_ingest_rule=true creates this rule.
resource "cloudflare_email_routing_rule" "ingest_to_worker" {
  count = var.create_email_ingest_rule ? 1 : 0

  zone_id = var.zone_id
  name    = "basement ingest to email-ingest worker"
  enabled = true

  matchers = [{
    type  = "literal"
    field = "to"
    value = local.ingest_email_address
  }]

  actions = [{
    type  = "worker"
    value = [var.email_ingest_worker_name]
  }]
}
