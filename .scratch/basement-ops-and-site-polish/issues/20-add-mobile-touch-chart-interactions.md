# Add mobile touch chart interactions

Type: task
Parent: ../map.md
Status: resolved

## Question

Harden the uPlot interactions for touch devices so the production dashboard works on mobile, not
only desktop mouse/trackpad.

Resolve when:

- Charts support mobile touch scrub/select for reading values.
- Charts support mobile zoom/pan or an equivalent touch-friendly range control without fighting
  normal page scroll.
- Desktop hover, wheel zoom, pan, week/full-history controls, min/max bands, event markers, and
  rainfall hover values still work.
- Interaction code remains self-contained in the generated HTML with vendored uPlot; no CDN or
  frontend build step.
- Browser verification covers at least one mobile viewport and one desktop viewport.

## Answer

Resolved 2026-07-11. The shared chart runtime in `static_site.py` (`CHART_BOOTSTRAP_JAVASCRIPT`)
now has an `addTouchNavigation` layer alongside the existing wheel/drag handlers, applied to both
the dashboard and the private report since they share the bootstrap script and
`render_chart_styles()`.

Gesture model:

- **One-finger horizontal drag** scrubs the uPlot cursor (`plot.setCursor`) so the live legend
  reads values; a **tap** sets the cursor at that point. Direction is decided once per touch after
  an 8 px slop: horizontal claims the gesture (`preventDefault`), vertical hands it to the browser.
- **Page scroll never fights the charts**: `.interactive-chart .u-over` gets
  `touch-action: pan-y` (plus `user-select`/`touch-callout` suppression), and vertical
  single-finger movement is deliberately left unprevented.
- **Two fingers pinch-zoom and pan** by solving the x-scale so the data values under both fingers
  at pinch start stay under them as they move — one formula gives zoom and pan; the span is
  clamped to data bounds (existing `clampRange`) and a 10-minute minimum.
- The 1w/All buttons stay as the touch-friendly range reset; desktop hover, ctrl/meta-wheel zoom,
  shift-wheel pan, and drag-select zoom are untouched code paths.

Implementation notes: `frame.chartPlot` now exposes the uPlot instance as a DOM property for
test/verification access. uPlot applies `setScale` on a deferred commit, so scale reads in
verification must happen a tick after dispatching events.

Verification:

- `uv run pytest` — 41 passed (includes new
  `test_charts_include_touch_interactions_without_trapping_page_scroll` covering both pages);
  `uv run ruff check .` and `uv run pyright` clean.
- Playwright (Chromium) against a real-data build at desktop 1440x900 (mouse) and mobile 390x844
  (touch, iPhone UA): 19/19 checks passed — hover legend values, ctrl-wheel zoom, shift-wheel pan,
  drag-select zoom, 1w/All buttons, rainfall hover value in mm, tap-to-read, horizontal scrub
  claimed + cursor moves, vertical swipe left to the browser, pinch-out zoom (604800 s → 201600 s),
  two-finger pan at constant span, no horizontal page overflow, `touch-action: pan-y` computed,
  zero console errors on both viewports.
- Script: [assets/ticket-20-verify-touch.mjs](../assets/ticket-20-verify-touch.mjs); screenshots
  `output/playwright/ticket-20-touch-{desktop,mobile}.png`.
