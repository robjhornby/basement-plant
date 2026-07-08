# Replace static SVG charts with vendored uPlot interactive charts

Type: prototype
Parent: ../map.md
Status: resolved

## Question

Swap the server-rendered SVG time-series charts for interactive uPlot charts with a one-week
default window, while keeping the publish model (self-contained HTML objects written to R2).

Decisions already made (map Notes): vendored uPlot inlined into the generated HTML, chart data
inlined as JSON, no build step, no CDN/external requests; the frontend build-step question is
deferred to the redesign arm.

Resolve when:

- All dashboard time-series charts (sensor absolute humidity/temperature/RH, weather overlay,
  rainfall) render via uPlot with hover cursor/values and x-axis zoom/pan.
- Charts default to the most recent week of data but can zoom out to the full history (either
  full data inlined with an initial window, or a range control — prototype and pick what feels
  right; note the page is already ~260KB, so check the inlined-JSON weight at full history).
- The generated pages remain fully self-contained (uPlot JS+CSS inlined at render time from a
  pinned, vendored copy in the repo — record the version and license), pass a no-external-request
  check, and degrade to a readable static fallback if JS is disabled only if that comes cheap.
- The rain chart's bar-style rendering survives the migration (uPlot handles bars via paths/plugin;
  if that fights the library, say so in the answer and keep rain as SVG rather than forcing it).
- Render-layer tests updated; local build visually checked in a browser at one-week and zoomed-out
  views.

This is typed prototype because the first pass should be a cheap look-and-feel check (one chart,
real data) before converting all charts — but the ticket resolves with the full conversion landed.

## Answer

Resolved with the full conversion landed.

- Vendored uPlot `1.6.32` under `src/basement_analysis/vendor/uplot/` with the MIT license and
  package metadata; the generated pages inline the vendored CSS/JS and do not request a CDN.
- Replaced dashboard and report SVG chart rendering with uPlot-backed charts fed by inline JSON
  payloads. The SVG renderers remain only as cheap `<noscript>` fallbacks.
- All dashboard time-series charts now render as uPlot canvases with live legends, drag-to-zoom,
  `1w`/`All` range controls, and modifier-wheel x-axis navigation. The default range is the latest
  week while full history remains in the page payload.
- The Environment Agency rainfall chart uses `uPlot.paths.bars`, so the bar-style rain rendering
  survived the migration.
- Render tests now assert the self-contained uPlot contract, inline JSON payloads, bar rendering,
  one-week default configuration, and static fallback presence.

Verification:

- `uv run pytest`
- `uv run ruff format --check .`
- `uv run ruff check .`
- `uv run pyright`
- `uv run basement --reuse-curated`
- Browser check via Playwright against `http://localhost:8765/index.html`: four nonblank uPlot
  canvases, no console errors, request log contained only `index.html`, mobile chart widths fit a
  390 px viewport, and the `1w`/`All` controls toggled correctly.

Build-size note: the generated dashboard is now about 652 KB with full-history data and vendored
uPlot inlined; this is acceptable for the current no-build static publishing model and does not
warrant a frontend build-step ticket before the redesign arm.
