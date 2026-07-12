# Verify and deploy Frutiger Aero redesign

Type: task
Status: claimed
Parent: ../map.md
Blocked by: 19, 20, 21, 23

## Question

Run the final production verification and deploy the Frutiger Aero redesign.

Resolve when:

- The generated site is checked in a real browser at desktop and mobile widths for first fold,
  full page, chart interaction, and no console errors.
- Page weight is measured, including HTML, chart payloads, and same-origin image derivatives; any
  unexpectedly large asset is called out and either fixed or explicitly accepted.
- The page makes no external requests.
- R2 publication includes the expected HTML and image objects and excludes the public physics
  report.
- The live `https://robjhornby.com/basement/` route is smoke-tested after deploy for status,
  cache headers, ETags/304 behavior, chart render, and asset loading.

## Comments

2026-07-12 deploy-day status (pre-deploy verification confirmed by Rob; release executed, two
blockers found in the live smoke test):

Done and verified:

- PR #4 merged to main (merge commit `8def243`); `basement-site.yml` dispatch run
  [29191999225](https://github.com/robjhornby/basement-plant/actions/runs/29191999225) green in
  1m1s, publishing `index.html` (1.83 MB), the seven `assets/frutiger-aero/` objects
  (largest: `tall-scene-2048.webp` at 188 KB), `manifest.json`, and `build-info.json` to
  `basement-site`.
- Live `https://robjhornby.com/basement/` smoke test: HTTP/2 200,
  `cache-control: public, max-age=600, no-transform`, ETag present, `If-None-Match` answers a
  bodyless 304, title "Watch a basement dry", uPlot inlined; the only `http(s)://` string in the
  page is the vendored uPlot banner comment — no external requests.

Blocked (both actions denied by the permission classifier; need Rob):

1. **Deployed site Worker is stale (pre-ticket-17/21 allowlist).** All
   `assets/frutiger-aero/*` routes 404 live — the redesign page renders without its scene/floor/
   dehumidifier images — and `physics-report.html` is *served* (200) instead of 404. Fix:
   `npx wrangler deploy` in `infra/cloudflare/workers/site/` (repo code already has the correct
   allowlist: index + seven asset paths, everything else 404).
2. **Stale `physics-report.html` (661 KB) is back in the `basement-site` bucket**, uploaded
   2026-07-12 06:43 — after ticket 21's cleanup, presumably by a local full-site sync during
   ticket 23 verification. Fix:
   `aws s3 rm s3://basement-site/physics-report.html --endpoint-url "$R2_ENDPOINT_URL"`
   (Worker deploy alone also closes the route, but the object should still go).

Remaining before resolve: run the two fixes, then re-verify asset 200s/content types, report
route 404, and a browser pass at desktop + mobile widths with images actually loading.
