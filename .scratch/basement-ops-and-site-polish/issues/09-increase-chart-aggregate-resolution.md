# Increase chart aggregate resolution and show within-window spread

Type: prototype
Status: resolved
Parent: ../map.md

## Question

Now that the dashboard charts are interactive, improve the data resolution behind zoomed-in views.
The current sensor chart series are hourly aggregates, which look too sparse when zoomed to the
latest week.

User preference, in order:

- Prefer 10-minute aggregate windows for sensor time-series data.
- Ideally show the min/max spread within each 10-minute window as error bars or a band, with the
  mean/central value still visible as the main line.
- If all-history 10-minute data makes the self-contained HTML too large or sluggish, use a tiered
  payload: 10-minute aggregates for the most recent month and 1-hour aggregates for older history.

Resolve when:

- The current chart aggregation points are inventoried: which series are hourly because of local
  aggregation, which are daily by design, and which upstream sources are inherently hourly or
  coarser.
- A page-weight target is chosen using measured generated `index.html` size and browser behavior,
  not guesswork.
- The chosen implementation is landed for the relevant dashboard and report charts. At minimum,
  sensor-derived time-series charts should no longer be hourly-only in the latest-week view.
- The min/max representation is prototyped and kept if it reads clearly; if uPlot makes the result
  visually noisy or technically awkward, record that and ship the higher-resolution mean lines
  without forcing error bars.
- The large `<noscript>` SVG fallbacks are reconsidered. Either remove them, replace them with a
  much smaller non-JS fallback, or keep them only with a measured justification.
- Render tests cover the new payload shape and resolution policy.
- Local build and browser checks verify chart rendering, range controls, payload size, and mobile
  layout.

This is next in the queue because the user asked to do it immediately after seeing the first
interactive zoomed plots.

## Answer

Implemented a tiered sensor-chart payload:

- Sensor-derived dashboard/report line charts now use 10-minute aggregate buckets for the most
  recent 31 days and 60-minute buckets for older history.
- The sensor aggregate model now carries mean/min/max values per bucket. The mean remains the
  visible line; min/max render as a faint canvas band for sensor-derived series.
- The min/max band was kept after browser checks: it reads as useful spread context without adding
  legend clutter because the bands are drawn by a lightweight uPlot canvas plugin rather than as
  extra visible series.
- The large SVG `<noscript>` fallbacks were replaced with compact text fallbacks. The interactive
  pages remain self-contained: vendored uPlot and chart JSON are still inlined, with no CDN or
  external asset requests.

Aggregation inventory:

- `Daily Basement Trends` remains daily by design via `daily_basement_points`.
- `Basement Versus Outdoor Moisture` now uses tiered local sensor aggregation for the basement
  absolute-humidity series; the Open-Meteo outdoor absolute-humidity series remains inherently
  hourly.
- `Raw Sensor Context` now uses tiered local sensor aggregation for basement, bedroom, and living
  room RH series.
- `Environment Agency Rainfall` remains hourly local aggregation because the published rainfall
  comparison is mm/hr and the upstream data cadence is coarser/contextual.

Measured page-weight target and result:

- Chosen dashboard target: stay under 2 MB for `index.html` in the current no-build,
  self-contained model.
- Previous generated size from `build/basement-site`: `index.html` 667,283 bytes,
  `physics-report.html` 331,769 bytes.
- New generated size from `build/ticket-09-site`: `index.html` 1,141,587 bytes,
  `physics-report.html` 644,029 bytes.

Verification:

- `uv run pytest tests/test_static_site_summary.py` — 7 passed.
- `uv run pytest` — 34 passed.
- `uv run ruff check src/basement_analysis/static_site.py src/basement_analysis/summaries.py tests/test_static_site_summary.py` — passed.
- `uv run pyright` — 0 errors.
- `uv run basement build-site --output-dir build/ticket-09-site` — built from 571,021 sensor rows.
- Playwright against `http://127.0.0.1:8765/index.html`: four nonblank uPlot canvases, no console
  warnings/errors, only the static page request, no horizontal overflow on desktop or 390px mobile,
  hidden `<noscript>` fallbacks, min/max band payloads on the two sensor-derived charts, and
  `1w`/`All` controls toggled correctly.
- Browser screenshots saved to `output/playwright/ticket-09-dashboard-desktop.png` and
  `output/playwright/ticket-09-dashboard-mobile.png`.
