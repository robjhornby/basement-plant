# Site redesign mockups — PROTOTYPE, throwaway

**Question** ([ticket 11](../../.scratch/basement-ops-and-site-polish/issues/11-prototype-redesign-mockups.md)):
which of the three redesign skins should the dashboard adopt? The page spec is fixed
(ticket 10); these vary only the skin.

## The mockups

Open any one in a browser; the floating pill (bottom centre) and the left/right arrow
keys switch between them. All render the same real curated data (snapshot from
`build/ticket-09-site/curated-data`, data to 03 Jul 2026).

1. [instrument-panel.html](instrument-panel.html) — near-black, phosphor green/amber,
   monospace, scanline readouts, glowing traces.
2. [frutiger-aero.html](frutiger-aero.html) — aqua sky gradient, sun glow, glossy glass
   panels, bubbles, green hills.

A third candidate (spring / wet moss: warm paper, moss green/clay/teal, serif title)
was dropped after the reaction round — see below.

## How they were built

- `build_payloads.py` — builds `payloads.json` (three chart payloads + latest readouts)
  from the curated parquet snapshot using the repo's own aggregation helpers
  (tiered 10-minute/hourly buckets, min/max bands, hourly rainfall sums).
- `build_mockups.py` — wraps the payloads, the vendored uPlot, a shared multi-axis chart
  runtime (per-measure y-axes, week/all range controls, wheel zoom/pan, event markers,
  min/max bands, custom rainfall bars), and one CSS skin per theme into three
  self-contained HTML pages (~1.1 MB each, no external requests).
- Every per-chart palette triple was validated with the dataviz skill's
  `validate_palette.js` (lightness band, chroma floor, CVD separation, contrast) against
  each theme's surface. Two floor-band WARNs (instrument room-comparison orange↔green,
  moss hero teal tritan) are relieved by the always-visible live legend labels.

## Reactions (Rob, 2026-07-09)

- **Frutiger Aero and Instrument panel are fantastic**; spring / wet moss dropped
  (file deleted, theme removed from the generator).
- Aero: the white gloss reflections sat at different offsets on the readout boxes
  versus the chart boxes (they were %-sized) — **fixed** to constant pixel
  offsets/height so every box matches.
- Aero: "Watch a basement dry" title needed slightly more contrast against the sky —
  **fixed** with a darker gradient and stronger white drop-shadow.
- Both: wanted units in the hover values under the charts — **added** via uPlot
  per-series value formatters ("87.0%", "17.9 °C", "13.3 g/m³", "0.20 mm per hour").
- Room comparison: preferred three single-measure charts over one — **replaced** with
  Room relative humidity / Room temperature / Room absolute humidity, each with the
  same room-identity colours (basement/bedroom/living room).

The winner and implementation slicing belong to ticket 12.
