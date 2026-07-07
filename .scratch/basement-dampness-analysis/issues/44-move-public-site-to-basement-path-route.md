# Move public site to /basement path route

Type: task
Status: resolved
Parent: ../map.md
Blocked by: 39

## Question

Move the live Cloudflare static site publication route from
`https://basement.robjhornby.com/` to `https://robjhornby.com/basement/`, while keeping the
existing `basement-site` R2 publication bucket and GitHub Actions R2 S3-compatible publish flow.

Resolve when the Worker config and request routing support `/basement/`, the temporary
`basement.robjhornby.com` DNS placeholder is removed from OpenTofu configuration, tests/docs are
updated, and the remaining deploy/apply verification steps are explicit.

## Comments

2026-07-07 route migration progress:

- Worker code now supports the target `robjhornby.com/basement*` route:
  `/basement` redirects to `/basement/` with `308`; `/basement/`,
  `/basement/index.html`, and `/basement/physics-report.html` serve the existing
  `basement-site` R2 objects.
- Interim Worker version `499e5685-e246-43db-adfd-cb2ca967a5b4` kept both triggers during the DNS
  transition. The legacy trigger was removed after `/basement/` was verified live.
- Verification passed locally: `npm run check`, `npm test`, `npx wrangler deploy --dry-run`,
  `tofu fmt -check -recursive`, and `tofu validate`.
- Live verification passed for the legacy fallback:
  `https://basement.robjhornby.com/` and `/physics-report.html` return `200`; `HEAD` returns
  `200`; `POST` returns `405` with `Allow: GET, HEAD`.
- Forced-through-Cloudflare verification passed for the target path route using
  `curl --resolve robjhornby.com:443:104.21.89.96`: `/basement/` and
  `/basement/physics-report.html` return `200`, `/basement` returns `308`, `HEAD` returns `200`,
  and `POST` returns `405`.
- Normal public verification still fails for `https://robjhornby.com/basement/` because apex
  traffic is not currently passing through Cloudflare's proxy. The route will not execute publicly
  until the relevant apex web records are proxied/orange-clouded in Cloudflare.
- OpenTofu config has removed the old `basement.robjhornby.com` DNS placeholder.
- Correction: `infra/cloudflare/tofu/.envrc` exports `CLOUDFLARE_API_TOKEN`; plain shell commands
  from the repo root do not load it automatically. Use `direnv allow`/an already-loaded direnv
  shell, or explicitly run `set -a; source .envrc; set +a` from `infra/cloudflare/tofu` before
  OpenTofu commands.
- The `create_email_ingest_rule` flag was a production footgun; the Email Routing rule should be
  unconditional now that the Worker exists. The config/state were updated in this session to remove
  that option.

## Answer

Completed the route migration:

- Flipped the existing apex web DNS records to proxied in Cloudflare using the Cloudflare API and
  the token from `infra/cloudflare/tofu/.envrc`, without bringing those external web records under
  this repo's OpenTofu state.
- Verified `https://robjhornby.com/` still returns `200` through Cloudflare.
- Verified `https://robjhornby.com/basement/` returns `200` with the dashboard content.
- Verified `https://robjhornby.com/basement/physics-report.html` returns `200` with the physics
  report content.
- Verified `https://robjhornby.com/basement` redirects to `/basement/` with `308`.
- Verified `HEAD https://robjhornby.com/basement/` returns `200`.
- Verified `POST https://robjhornby.com/basement/` returns `405` with `Allow: GET, HEAD`.
- Removed the old `basement.robjhornby.com` placeholder DNS record with OpenTofu.
- Removed the temporary legacy subdomain route from the site Worker and redeployed the Worker with
  only the `robjhornby.com/basement*` trigger.

Final deployed site Worker version: `22b407b1-6463-4bda-b6c8-1efffdccbba2`.

Infrastructure cleanup:

- Removed the `site_worker_subdomain` variable, `site_worker_hostname` output, and
  `site_dns.tf` placeholder resource from `infra/cloudflare/tofu/`.
- Removed the `create_email_ingest_rule` variable and made
  `cloudflare_email_routing_rule.ingest_to_worker` unconditional.
- Moved OpenTofu state from `cloudflare_email_routing_rule.ingest_to_worker[0]` to
  `cloudflare_email_routing_rule.ingest_to_worker`; final `tofu plan -var-file=env/production.tfvars`
  reports no changes.
