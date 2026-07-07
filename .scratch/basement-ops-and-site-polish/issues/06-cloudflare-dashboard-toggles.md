# Apply the Cloudflare dashboard zone-setting fixes

Type: task
Parent: ../map.md
Status: resolved

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

## Comments

2026-07-08 abandoned-claim check: live headers show the dashboard checklist is not complete yet,
so this ticket is open/unclaimed again rather than reserved by a dead session.

- `curl -sI http://robjhornby.com/` returned `200 OK`, not an HTTPS redirect.
- `curl -sI http://robjhornby.com/basement` returned `308` with
  `Location: http://robjhornby.com/basement/`, still plaintext.
- `curl -sI https://robjhornby.com/basement/` returned `200` without an `etag` header.
- `curl -sI https://www.robjhornby.com/` returned a GitHub Pages `301` to the apex, showing `www`
  still bypasses Cloudflare rather than being proxied.

## Answer

Completed 2026-07-08. The dashboard-only Cloudflare zone settings are now applied, and the live
verification checks pass.

Confirmed behavior:

- `curl -sI http://robjhornby.com/` returns `301 Moved Permanently` with
  `Location: https://robjhornby.com/`.
- `curl -sI http://robjhornby.com/basement` returns `301 Moved Permanently` with
  `Location: https://robjhornby.com/basement`.
- `curl -sI https://robjhornby.com/basement/` returns `200` with
  `etag: "6370c218b554d5b234f2a211db0f040f"` and `cache-control: no-transform`.
- `curl -sI https://www.robjhornby.com/` returns `301` to `https://robjhornby.com/` through
  Cloudflare (`server: cloudflare`), so the `www` CNAME is proxied and the apex redirect still
  has a valid TLS path.

One repo-side adjustment was needed after the manual toggles: Email Address Obfuscation injection
was gone, but Cloudflare still stripped the Worker `etag` until the site Worker sent
`Cache-Control: no-transform`. Added that narrow header in
`infra/cloudflare/workers/site/src/index.ts` and covered it in
`infra/cloudflare/workers/site/test/site.spec.ts`; issue 09 can still choose the later max-age
policy by extending this header rather than replacing it.

Verification:

- `cd infra/cloudflare/workers/site && npm run check` — passed.
- `cd infra/cloudflare/workers/site && npm test` — 6 passed.
- `cd infra/cloudflare/workers/site && npx wrangler deploy --dry-run` — passed.
- `cd infra/cloudflare/workers/site && npx wrangler deploy` — deployed Worker version
  `5ea79c2a-1a27-453c-94fb-978527c9970c`.
