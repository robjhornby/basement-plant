# Trim frontend text and remove prototype-style language

Type: task
Parent: ../map.md
Status: resolved

## Question

Make the current dashboard read like a small finished product rather than an analyst's working
document, without changing the underlying analysis.

The user's direction: reduce the amount of text on the frontend, and remove "local" and
prototype-style language (e.g. framing like "local static site", caveat-heavy prose blocks,
work-in-progress phrasing) from the rendered pages.

Resolve when:

- `index.html` leads with the data: headline metrics and charts, with explanatory prose cut or
  collapsed to short labels/captions; long-form explanation stays on (or moves to) the physics
  report page, which is linked, not inlined.
- No rendered page describes itself as local, prototype, provisional, or similar; wording is
  neutral product language. (Uncertainty caveats that are analytically load-bearing stay, but as
  concise annotations, not paragraphs.)
- The changes live in the render layer (`static_site.py` / `summaries.py` presentation fields),
  page-output tests are updated, and a local build is visually checked.

Notes: this is the first arm of the site quick wins agreed on the map; it can land independently
of the uPlot work (issue 08) but the two will touch the same templates, so coordinate if run in
parallel.

## Answer

The dashboard render now reads as a published page rather than a local prototype:

- `index.html` title and H1 are `Basement Dampness` / `Basement dampness`.
- The old prototype scope paragraph was removed; the page now leads with metric cards, then a
  single `Physics and metrology report` link, then hypothesis cards and charts.
- Header metadata is concise source/status copy: generated time plus STH51, Open-Meteo, and
  Environment Agency sources.
- The physics report intro is neutral product copy, and rendered caveat wording no longer says
  `local`, `prototype`, `provisional`, `work-in-progress`, or `house-local`.
- Regression tests assert cards appear before hypothesis prose and that the removed wording is
  absent from the rendered dashboard/report HTML.

Verification:

- `uv run basement` rebuilt `build/basement-site/index.html` and `physics-report.html`.
- Browser screenshots: `output/playwright/ticket-07-dashboard.png` and
  `output/playwright/ticket-07-dashboard-mobile.png`.
- `uv run ruff format --check .`
- `uv run ruff check .`
- `uv run pyright`
- `uv run pytest`

No new wayfinding tickets surfaced from this pass.
