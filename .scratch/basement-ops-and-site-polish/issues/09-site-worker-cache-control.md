# Add Cache-Control to the site Worker

Type: task
Parent: ../map.md

## Question

End the deliberate no-cache-policy deferral from the previous map: with interactive plots making
the page heavier, add a modest cache policy to the `basement-site` Worker.

Resolve when:

- The Worker sets an explicit `Cache-Control` (agreed direction: short `max-age` in the 5–15
  minute range — content updates at most daily, so err simple; no cache-busting machinery).
- The choice of whether to also use the Cloudflare edge cache (`caches.default` / `cf` fetch
  options) versus browser-only caching is made deliberately and noted in the answer — R2 Class B
  reads are free-tier-fine today, so edge caching is optional, not required.
- Worker tests cover the header; deploy is verified live with `curl -sI`.

Note: coordinates with the dashboard toggles ticket (issue 06) — once Email Address Obfuscation
is off, the Worker's `etag` header becomes visible and conditional requests start working; the
`Cache-Control` chosen here should play well with that (e.g. `max-age` + revalidation rather than
`immutable`).

## Comments

2026-07-08 note from issue 06: the site Worker now sends `Cache-Control: no-transform` so
Cloudflare preserves the R2 `etag` header at the edge. This ticket still needs to choose and add
the actual freshness policy; preserve `no-transform` when adding the future `max-age`.
