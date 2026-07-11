# Port Frutiger Aero redesign render

Type: task
Parent: ../map.md
Blocked by: 17, 18
Status: resolved

## Question

Port the accepted round-3 Frutiger Aero mockup into the production Python static-site renderer.

Resolve when:

- `static_site.py` renders the Frutiger Aero production dashboard as the public `index.html`:
  fold-first tall scene, title, humidity/temperature orbs, animated scroll hint, all charts just
  below the fold, underwater chart zone, bubbles/goldfish/dragonfly, concrete floor, and
  no-shadow dehumidifier.
- The production dashboard uses the chart lineup from
  [Reshape dashboard chart lineup for redesign](18-reshape-dashboard-chart-lineup-for-redesign.md).
- The page removes metric cards, hypothesis panels, daily-trends chart, period table, and the
  physics-report link from the public dashboard.
- Footer-only metadata remains: `Data to {latest reading time}` plus plain-words sources.
- The render stays in the Python static-site pipeline; no frontend build step, no CDN, no external
  requests.
- CSS is responsive across desktop and mobile without text overlap, horizontal scrolling, or chart
  controls crowding the plot area.
- The prototype files remain reference material only; production code owns its own render and asset
  paths.

## Answer

Reopened and re-resolved 2026-07-11 after screenshot review showed the first pass had only ported
the broad shell, not the full accepted prototype.

What made the first port bad was not a genuine technical blocker. The round-3 prototype was already
plain HTML/CSS/JS; the production work mainly needed careful translation from embedded data-URI art
to same-origin asset paths. The misses were implementation discipline: the prototype-specific
decorative layers and chart-runtime hooks were not carried over, and the generated page was not
checked closely enough against the Playwright screenshots.

Fixed in this pass:

- The full-page underwater art layer now uses the body as its positioning context, so the concrete
  floor and dehumidifier sit at the bottom of the document rather than at the viewport fold.
- The generated dashboard now carries the missing prototype visual layers: aurora ribbons, bokeh,
  stronger orb shadows, Vista glass card bevels, sheen sweeps, gel range buttons, footer glass, the
  floor overlay, and clipped decorative art to prevent mobile horizontal overflow.
- The chart runtime now has the Frutiger Aero chart skin instead of generic uPlot defaults:
  validated Aero role colours, water-fill on the basement relative-humidity hero series,
  droplet-style rainfall bars, bubble-column event markers, Aero grid/axis styling, and per-series
  role metadata while preserving the generic chart style for the private report.
- Regression coverage now guards the Frutiger body class, art/clipping CSS, theme assets, footer
  freshness, removed legacy sections, and the Aero-specific chart drawing hooks.

Verification:

- `uv run pytest tests/test_static_site_summary.py` — 12 passed.
- `uv run pytest` — 40 passed.
- `uv run ruff check .` — passed.
- `uv run pyright` — 0 errors.
- Rendered `build/ticket-19-frutiger-aero-check/index.html` from
  `build/basement-site/curated-data` and checked it through Playwright at 1440x900 and 390x844.
  Screenshots were saved to `output/playwright/ticket-19-frutiger-aero-desktop-recheck.png` and
  `output/playwright/ticket-19-frutiger-aero-mobile-recheck.png`.
- Playwright metrics: desktop `scrollWidth` 1440 / `clientWidth` 1440, mobile `scrollWidth` 390 /
  `clientWidth` 390, four chart cards, no external resources, zero console warnings, and
  floor/dehumidifier bounding boxes at the document bottom on both viewports.
