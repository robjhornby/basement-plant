# Add Cache-Control to the site Worker

Type: task
Parent: ../map.md
Status: resolved

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

## Answer

The `basement-site` Worker now sends `Cache-Control: public, max-age=600, no-transform` and
answers conditional requests with bodyless 304s. Deployed (version `6bffcb0b`) and verified live
2026-07-09.

- **Freshness policy**: `max-age=600` — 10 minutes, the middle of the agreed 5–15 range; no
  `immutable`, so browsers revalidate after expiry. `no-transform` is preserved per the issue 06
  note so Cloudflare keeps the R2 ETag intact.
- **Edge cache decision**: browser-only caching, deliberately no `caches.default` / `cf` fetch
  options — R2 Class B reads are free-tier-fine, traffic is tiny, and edge caching would add
  purge/invalidation complexity for a page that changes nightly. Revisit only if R2 read volume
  ever matters.
- **Revalidation made real**: a live probe showed `If-None-Match` previously returned a full 200
  with the 1.14 MB body. The Worker now passes `onlyIf: request.headers` to `SITE_BUCKET.get` and
  returns a bodyless 304 when the ETag matches, so post-expiry revalidation costs ~0 bytes.
- **Tests**: 8 Worker tests pass, including new 304-on-match and full-body-on-stale-ETag cases.
- **Live verification**: `curl -sI https://robjhornby.com/basement/` shows the new header on both
  pages; repeating with `If-None-Match: <etag>` returns `304` with `size_download=0`.

Code: commit `19ff303` (plus a test-hostname cleanup to `example.test` made in review).

## Comments

2026-07-08 note from issue 06: the site Worker now sends `Cache-Control: no-transform` so
Cloudflare preserves the R2 `etag` header at the edge. This ticket still needs to choose and add
the actual freshness policy; preserve `no-transform` when adding the future `max-age`.

2026-07-09 progress (code done, deploy pending): committed as `19ff303` on `main`, not yet
deployed — the sandbox denied `wrangler deploy` to production, so the deploy + live `curl -sI`
verification needs the user (or an explicitly authorized session) to run
`npm run deploy` in `infra/cloudflare/workers/site/`.

Decisions taken, for the eventual Answer:

- `Cache-Control: public, max-age=600, no-transform` — 10 minutes, middle of the agreed 5–15
  range; `no-transform` preserved per the issue 06 note; no `immutable`, so revalidation applies.
- Browser-only caching, deliberately no edge cache (`caches.default` / `cf` options): R2 Class B
  reads are free-tier-fine, traffic is tiny, and edge caching would add purge/invalidation
  complexity for a page that changes nightly.
- Revalidation made real, not just permitted: a live probe showed `If-None-Match` returned a full
  200 with the 1.14 MB body, so the Worker now passes `onlyIf: request.headers` to R2 and returns
  a bodyless 304 when the ETag matches.
- Typecheck and all 8 Worker tests pass, including new 304-match and stale-ETag-full-body cases.

Live verification once deployed: `curl -sI https://robjhornby.com/basement/` should show the new
`cache-control`, and repeating the request with `If-None-Match: <etag>` should return `304` with
`size_download=0`.
