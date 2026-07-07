# Apply the Cloudflare dashboard zone-setting fixes

Type: task
Parent: ../map.md

## Question

Human checklist — these zone settings are unreachable with the local scoped tokens (both the tofu
token and the wrangler OAuth session 403 on zone settings), so they are one-time dashboard
actions, mirroring how Email Routing enablement was handled on the previous map.

At dash.cloudflare.com → robjhornby.com:

1. **SSL/TLS → Overview**: set encryption mode to **Full (strict)**. (GitHub Pages serves valid
   certs for the apex, so strict is safe.)
2. **SSL/TLS → Edge Certificates**: turn **Always Use HTTPS** on. Closes the finding that
   `http://robjhornby.com/` and `http://robjhornby.com/basement/` currently serve full content
   over plaintext with no redirect.
3. **Scrape Shield**: turn **Email Address Obfuscation** off. It is rewriting every HTML response
   and stripping ETags zone-wide (verified: the site Worker's explicit `etag` header and GitHub
   Pages' own ETags both vanish at the edge), so browsers can never revalidate with a 304.
4. **DNS**: switch the `www` CNAME (`robjhornby.github.io`) from DNS-only to **Proxied**, for
   zone consistency (today www bypasses Cloudflare entirely and would miss any future rules).

Verification (agent or human) after toggling:

- `curl -sI http://robjhornby.com/` → 301 to `https://`.
- `curl -sI http://robjhornby.com/basement` → redirects to `https://`.
- `curl -sI https://robjhornby.com/basement/` → response carries an `etag` header.
- `https://www.robjhornby.com/` still redirects to the apex with a valid certificate.

Resolve with the checklist confirmed and the verification results pasted into the answer.
