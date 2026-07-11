# Basement ops hardening and site polish wayfinding map

Label: wayfinder:map

## Destination

The hosted pipeline is trustworthy and observable — no silent data loss, HTTPS-only serving,
known nightly-run timings, tidy configuration — and the public site at
`https://robjhornby.com/basement/` is pleasant to view now (less text, interactive one-week-default
plots, no prototype-style language) and deliberately designed later (redesign direction chosen
with the user through mockups). GitHub Pages→Cloudflare hosting consolidation is explicitly out of
scope.

## Notes

This effort follows the resolved `basement-dampness-analysis` map, which proved the hosted
Cloudflare email→R2→Parquet→GitHub-Actions→static-site loop end to end. Analytical/physics work
stays on that map; this map is the "deliberately scoped operations improvements + publication
polish" successor.

Sources this map was charted from:

- The 2026-07-07 implementation review (Cloudflare live-state findings, pipeline code review) —
  see [docs/architecture/architecture-diagrams.md](../../docs/architecture/architecture-diagrams.md)
  for the implemented architecture (deployed pipeline, serving path, local-vs-hosted parity).
- The user's `basement-dampness-analysis/todo.md` items (pipeline efficiency, observability,
  diagrams — done, cooler site design, infra config assessment).

Standing preferences and constraints:

- Stay on the Cloudflare Workers Free plan; keep the database-free R2 object/manifest design.
- OpenTofu owns durable Cloudflare resources, Wrangler owns Worker projects, narrow scripts only
  for gaps (`infra/cloudflare/`). Zone settings (SSL mode, Always Use HTTPS, obfuscation) are
  dashboard-only with current tokens — those become human task checklists, not automation.
- The repo is public: no precise home coordinates, no `data/`, `.envrc`, tfstate/tfvars, or real
  `.eml` files committed; treat anything pushed as published.
- Python: type hints everywhere, full-name `snake_case`, focused modules, Ruff, strict Pyright,
  tests around behavior, `uv` for everything.
- Efficiency work is measure-first: the nightly run is ~1 minute, so instrument before optimizing,
  and only fix what timings show to be slow.
- Site quick wins ship before the bigger redesign; the redesign is human-in-the-loop
  (grilling → mockup prototypes → grilling), the quick wins and ops fixes are autonomous
  stretches. Use `/grilling` and `/domain-modeling` on grilling tickets.
- Interactive plots: vendored uPlot inlined into the generated HTML, data inlined as JSON, no
  build step, no CDN/external requests. The frontend build-step question is deferred to the
  redesign arm.
- 2026-07-08 queue update: the user wants higher-resolution chart aggregates next after seeing the
  first interactive zoomed plots, so that work is ticket 09 and the cache-control ticket moved to
  ticket 15.
- The dashboard is the only design target; the physics report comes off the web entirely
  (locally rendered artifact only — unpublishing is implementation work carried by
  [ticket 12](issues/12-grill-mockup-winner-and-implementation.md)).
- Key review facts: EA rainfall API retains only ~4 weeks (station `270397`); Open-Meteo archive
  covers full history and currently returns no nulls; the pipeline bucket holds stale `site/`
  prefix objects; GitHub disables cron workflows in public repos after 60 days without activity;
  `numeric_sequence` in `static_site.py` coerces `None`→`0.0`.

## Decisions so far

<!-- one line per closed ticket: gist + link -->

- [Fix rain and weather history data loss in hosted curation](issues/01-fix-rain-history-data-loss.md) —
  hosted curation now merges rain/weather partitions (fresh rows win by timestamp) instead of
  replacing them, and null Open-Meteo hours are dropped rather than coerced to 0.0; verified
  against live R2 that pre-API-window rain history survives the nightly run.
- [Pipeline hygiene sweep](issues/02-pipeline-hygiene-sweep.md) — stale `site/` objects deleted
  from `basement-pipeline`; dead `cfat_` token line removed from `.envrc`; workflow actions
  SHA-pinned and a cron keepalive (Actions-API re-enable each run) added, verified with a green
  dispatch run and merged as PR #1; surfaced the Node 20 deprecation bump as
  [ticket 13](issues/13-bump-pinned-actions-node20.md).
- [Add step-timing observability and a build-info record](issues/03-add-step-timing-observability.md) —
  curation/build phases now emit timing records and job-summary markdown; hosted builds publish
  `build-info.json` with freshness, row counts, and timings; PR #2 dispatch run recorded 42s
  wall-clock with curation timing at 13.285s and site-build timing at 7.617s.
- [Assess pipeline efficiency from measured timings](issues/04-assess-pipeline-efficiency-from-timings.md) —
  no optimization ticket is warranted at 42s hosted wall clock / ~21s timed Python phases; keep
  the full rebuild until timings exceed explicit revisit thresholds.
- [Assess infra config spread and environment-variable consolidation](issues/05-assess-infra-config-and-env-vars.md) —
  cross-tool duplication is acceptable where names are frozen or tools cannot share config, but
  cheap Python constant consolidation and removing the tofu `zone_name` default are worth doing
  as [ticket 14](issues/14-mechanical-config-consolidation.md).
- [Apply the Cloudflare dashboard zone-setting fixes](issues/06-cloudflare-dashboard-toggles.md) —
  Full strict HTTPS, Always Use HTTPS, Email Address Obfuscation off, and proxied `www` are now
  live; the site Worker also sends `Cache-Control: no-transform` so R2 ETags survive the edge.
- [Trim frontend text and remove prototype-style language](issues/07-trim-frontend-text-and-language.md) —
  the dashboard now leads with metrics, removes the prototype scope prose, links the physics
  report tersely, and regression-tests against local/prototype/provisional rendered wording.
- [Replace static SVG charts with vendored uPlot interactive charts](issues/08-interactive-uplot-charts.md) —
  dashboard and report charts now render as self-contained uPlot canvases with inline JSON, a
  one-week default range, full-history controls, rain bars, and no external requests.
- [Increase chart aggregate resolution and show within-window spread](issues/09-increase-chart-aggregate-resolution.md) —
  sensor-derived dashboard/report charts now use tiered 10-minute recent and hourly historical
  aggregates with faint min/max bands; compact `<noscript>` fallbacks keep the dashboard at
  1.14 MB.
- [Mechanical config consolidation](issues/14-mechanical-config-consolidation.md) — the EA station
  id and the X-Sense raw-key prefix are now single Python constants (`summaries.py`,
  `raw_email_ingest.py`) reused by modules and tests; the tofu `zone_name` default is gone
  (real value in gitignored tfvars, `example.com` placeholder in the example); TS test fixtures
  use `example.test`, leaving the wrangler route as the only hardcoded domain in code.
- [Bump SHA-pinned workflow actions off deprecated Node 20](issues/13-bump-pinned-actions-node20.md) —
  `actions/checkout` v4.3.1 → v7.0.0 and `astral-sh/setup-uv` v5.4.2 → v8.3.2, SHA-pinned against
  upstream tag refs and merged as PR #3 after a green dispatch run with zero annotations; no
  breaking changes in the skipped majors affect this schedule/dispatch-only workflow.
- [Add Cache-Control to the site Worker](issues/15-site-worker-cache-control.md) — the site
  Worker now sends `public, max-age=600, no-transform` and answers matching `If-None-Match` with
  bodyless 304s via R2 `onlyIf`; browser-only caching, deliberately no edge cache; deployed and
  verified live.
- [Prototype redesign mockups](issues/11-prototype-redesign-mockups.md) — three skins built
  over real data; instrument panel and Frutiger Aero survive ("fantastic"), spring/wet moss
  dropped; reaction round also amended the page spec: hover values carry units and the room
  comparison splits into three single-measure charts (five charts total). Round 2
  (re-resolved 2026-07-11) built the extreme descent skin — sky → shoreline → waterline →
  underwater, orb readouts, water-styled charts — over the five final ChatGPT assets;
  User's reactions ask for composition rework (one tall scene image, fold-first layout,
  simpler underwater, possible basement nod), captured as
  [Refine the extreme aero descent](issues/16-refine-extreme-aero-descent.md).
- [Refine the extreme aero descent](issues/16-refine-extreme-aero-descent.md) — round 3
  accepted and **Frutiger Aero declared the winner**: one tall scene image (sky → hills →
  waterline pinned at 92vh) replaces the stitched scene, fold-first layout with all five
  charts starting just below the fold, gradient + bubbles below the water, concrete floor +
  keyed CGI dehumidifier as the basement nod (brick walls generated but rejected); desktop
  sun crop accepted; five keeper assets, palettes re-validated, instrument page untouched.
- [Grill the site redesign direction](issues/10-grill-site-redesign-direction.md) — 3D is mood
  not spec; three mockup candidates (instrument panel, spring/wet-moss, Frutiger Aero) over one
  fixed page spec: "Watch a basement dry" title, hero readouts + three charts (basement
  RH/temperature/absolute-humidity; basement-vs-outdoor absolute humidity + rainfall;
  basement-vs-bedroom/living-room RH), footer-only freshness and sources, no other prose, no
  metric cards/hypothesis panels/period table; physics report off the web; no build step,
  same-origin image assets allowed; mobile touch zoom/scrub required; no unexplained
  abbreviations.
- [Grill the mockup winner and implementation shape](issues/12-grill-mockup-winner-and-implementation.md) —
  round-3 Frutiger Aero wins without instrument-panel visual hybridization; production stays in
  the Python static-site renderer with same-origin assets, responsive derivatives from the
  upscaled tall scene, the no-shadow dehumidifier, a four-chart final lineup, mobile chart
  interaction hardening, public report unpublishing, and a final verify/deploy gate.
- [Production Frutiger Aero asset pipeline](issues/17-production-frutiger-aero-asset-pipeline.md) —
  the production build now owns the final Frutiger Aero source art, generates responsive WebP
  derivatives plus a manifest, packages those sources, uploads the generated assets to R2, and
  serves only the allowed same-origin asset paths through the site Worker.
- [Unpublish public physics report](issues/21-unpublish-public-physics-report.md) — the hosted
  public site now publishes and serves only the dashboard plus allowed same-origin assets; the
  report route is 404, stale R2 `physics-report.html` cleanup was executed once and verified, and
  local private report rendering remains opt-in via `--include-private-report`.
- [Reshape dashboard chart lineup for redesign](issues/18-reshape-dashboard-chart-lineup-for-redesign.md) —
  the production dashboard chart contract now emits the four final redesign charts in order
  (basement conditions, absolute humidity with hoverable hidden-scale rainfall, temperature,
  relative humidity) with per-series units and focused coverage for titles, series membership,
  units, rain-axis suppression, aggregation bands, and mixed-cadence gaps.
- [Port Frutiger Aero redesign render](issues/19-port-frutiger-aero-redesign-render.md) —
  reopened after screenshot review and re-resolved: production now ports the accepted Frutiger
  Aero prototype details, including full-page floor/dehumidifier positioning, decorative layers,
  Aero chart styling, same-origin theme assets, footer-only freshness/sources, and no old
  metric/hypothesis/period/report-link sections.

- [Add mobile touch chart interactions](issues/20-add-mobile-touch-chart-interactions.md) — the
  shared chart runtime now supports one-finger scrub/tap value reading and two-finger pinch
  zoom/pan, with `touch-action: pan-y` keeping page scroll with the browser; desktop hover,
  wheel zoom/pan, drag-select, and range buttons verified unchanged via a 19-check Playwright
  run at 1440x900 and 390x844 ([script](assets/ticket-20-verify-touch.mjs)).

## Not yet specified

None.

## Out of scope

- Hosting the entire robjhornby.com site on Cloudflare and dropping GitHub Pages — explicitly
  deferred by the user ("not right now"); would be a fresh effort if the destination is ever
  redrawn.
- Alerting, anomaly detection, and failure notifications — carried over from the previous map's
  fog; still waiting until the loop has run unattended for a while.
- Analytical/physics/metrology improvements and publication-grade write-ups — they belong to the
  `basement-dampness-analysis` effort's successor work, not this operations/polish map. The
  direction grill (ticket 10) added two named items to that pile: the drying-rate metric
  (humidity rise-rate after each dehumidifier-off cycle — a net-new feature later, no
  placeholder in the redesign) and research into what the X-Sense sensors actually sense.
- Durable production email forwarding (X-Sense → ingest address) — still tracked as the open
  [Configure source email delivery to Cloudflare ingest](../basement-dampness-analysis/issues/20-configure-source-email-delivery-to-cloudflare-ingest.md)
  ticket on the previous map; not duplicated here.
