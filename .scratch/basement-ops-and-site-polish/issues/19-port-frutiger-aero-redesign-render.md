# Port Frutiger Aero redesign render

Type: task
Parent: ../map.md
Blocked by: 17, 18

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
