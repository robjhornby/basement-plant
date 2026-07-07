# Replace static SVG charts with vendored uPlot interactive charts

Type: prototype
Parent: ../map.md

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
