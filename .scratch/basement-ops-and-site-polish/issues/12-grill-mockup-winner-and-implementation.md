# Grill the mockup winner and implementation shape

Type: grilling
Parent: ../map.md
Status: resolved
Blocked by: 11, 16

## Question

Close the human-in-the-loop design loop: with the user's mockup reactions recorded (issue 11),
run a `/grilling` session to pick the winning direction (or the hybrid) and pin the
implementation shape, then graduate the redesign implementation work out of the map's fog into
concrete task tickets.

To settle:

- Which mockup (or combination) wins, and which specific elements from the losers survive.
- Implementation mechanics: stays in the Python render layer with inlined assets, or introduces a
  frontend build step (this decision was explicitly deferred from the quick wins) — and if a build
  step arrives, how it fits the "publish = write HTML objects to R2" model and the GitHub Actions
  runner.
- Scope slicing into autonomous implementation tickets sized one session each, with blocking
  edges, created as new child issues of this map.

Implementation work already decided by the direction grill (issue 10) that the slicing must
carry, whatever the winning skin:

- Unpublish the physics report: hosted builds stop writing it to R2, the existing R2 object is
  removed, and the dashboard link is gone; the report stays a locally rendered artifact.
- Mobile touch zoom/scrub on the uPlot charts (custom touch handlers or a small plugin).
- The page-spec changes: hero readouts + three-chart lineup, dropped components (metric cards,
  hypothesis panels, daily-trends chart, period table), "<measure> / <unit>" dedicated y-axes,
  footer freshness line ("Data to {latest reading time}") plus plain-words sources, and the
  no-unexplained-abbreviations copy rule.
- Same-origin image assets (theme art) uploaded to R2 alongside the HTML if the winning skin
  needs them — no build step either way (decided in issue 10; revisit only if the winning
  mockup proves impossible without one).

Resolve when the winner and mechanics are recorded in the answer, the implementation tickets
exist and are wired, and the redesign entry in the map's Not-yet-specified fog is cleared.

## Comments

**2026-07-11 (agent)** — Unblocked: tickets 11 and 16 are both resolved. The winner
question is already answered: during ticket 16's reaction round User accepted the
round-3 extreme aero build and said he'd like to "move on to updating the real site
to use this frutiger aero theme" — so the grill's remaining work is the first
bullet's tail (which instrument-panel elements, if any, survive) and the
implementation shape: mechanics (Python render layer with the five keeper assets in
`prototypes/site-redesign-mockups/assets/` served same-origin from R2 — production
weight/format/serving was explicitly parked here by ticket 11), the carried
decisions listed above (report unpublish, touch zoom/scrub, page-spec changes), and
the slicing into one-session tickets. The mockup's `build_mockups.py` /
`process_assets.py` are the reference implementations to port.

**2026-07-11 (agent, with User)** — Winner confirmed: the production redesign should
use the round-3 Frutiger Aero theme, not a hybrid; no visible instrument-panel skin
elements survive. User also added an upscaled scene asset at
`prototypes/site-redesign-mockups/assets/upscalemedia-tall-scene.webp` and wants to
use it if feasible. Inspection: the upscaled scene is 2048x3072 and 1.9 MB; the
current derived scene is 1024x1536 and 84 KB, so production slicing needs an explicit
image-weight/derivative policy.

**2026-07-11 (agent, with User)** — Production image policy settled: use the
upscaled tall scene as the source asset, but do not ship the 1.9 MB source to every
visitor by default. The implementation should generate responsive/compressed
same-origin derivatives for the live page, preserving the improved source while
keeping first-load weight deliberate.

**2026-07-11 (agent, with User)** — Implementation slicing accepted with chart and
asset amendments. The dashboard chart set changes to: basement-only conditions
(relative humidity + temperature) first; then all three rooms plus outdoor data for
absolute humidity with rainfall, temperature, and relative humidity. The rainfall
axis should be hidden/suppressed while rainfall values remain visible on hover.
User also regenerated the dehumidifier without the bad drop shadow at
`prototypes/site-redesign-mockups/assets/dehumidifier-no-shadow.png`; production
must process that source to WebP and use it instead of the old shadowed asset.

## Answer

Resolved 2026-07-11.

The winner is the accepted round-3 Frutiger Aero theme, not a hybrid. No visible
instrument-panel skin elements carry into production; only the already-agreed data
discipline remains: readable charts, hover units, live legends, and clear controls.

Implementation mechanics stay in the Python static-site renderer. There is no frontend
build step, CDN, or external request path. Theme art ships as same-origin R2 assets
alongside the generated HTML. The upscaled tall scene
(`prototypes/site-redesign-mockups/assets/upscalemedia-tall-scene.webp`, 2048x3072,
1.9 MB) is the production source, but implementation must generate responsive/compressed
derivatives instead of serving that source to every visitor by default. The no-shadow
dehumidifier source (`dehumidifier-no-shadow.png`) replaces the earlier shadowed
dehumidifier image.

The production chart lineup is:

1. Basement conditions: basement sensor relative humidity and temperature only.
2. Absolute humidity: basement, bedroom, living room, outdoor, plus rainfall with the
   rainfall axis visually suppressed but hover values retained.
3. Temperature: basement, bedroom, living room, outdoor.
4. Relative humidity: basement, bedroom, living room, outdoor.

Graduated implementation tickets:

- [Production Frutiger Aero asset pipeline](17-production-frutiger-aero-asset-pipeline.md)
- [Reshape dashboard chart lineup for redesign](18-reshape-dashboard-chart-lineup-for-redesign.md)
- [Port Frutiger Aero redesign render](19-port-frutiger-aero-redesign-render.md)
- [Add mobile touch chart interactions](20-add-mobile-touch-chart-interactions.md)
- [Unpublish public physics report](21-unpublish-public-physics-report.md)
- [Verify and deploy Frutiger Aero redesign](22-verify-and-deploy-frutiger-aero-redesign.md)
