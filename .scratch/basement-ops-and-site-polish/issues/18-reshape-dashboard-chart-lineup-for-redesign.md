# Reshape dashboard chart lineup for redesign

Type: task
Parent: ../map.md
Status: resolved

## Question

Change the production dashboard chart set to the final redesign lineup before the visual shell is
ported, so the Frutiger Aero page is built around the right data contract.

Resolve when the dashboard exposes exactly these charts:

1. **Basement conditions**: pure basement sensor data only, showing relative humidity and
   temperature. Do not include extra axes/series that consume horizontal chart space.
2. **Absolute humidity**: basement, bedroom, living room, and outdoor absolute humidity, plus
   rainfall. The rainfall axis should be invisible or visually suppressed; rainfall values still
   appear on select/hover as already implemented.
3. **Temperature**: basement, bedroom, living room, and outdoor temperature.
4. **Relative humidity**: basement, bedroom, living room, and outdoor relative humidity.

Additional requirements:

- Hover/select values include units for every visible series and rainfall.
- Each chart uses dedicated plain-word axis labeling; no unexplained abbreviations.
- The chart payload shape remains suitable for the existing self-contained uPlot runtime.
- The old daily-trends chart, metric-card-driven chart layout, and previous room-comparison split
  are not emitted on the redesigned dashboard.
- Focused tests cover chart titles, series membership, units, and the invisible-rain-axis behavior.

## Answer

The production dashboard chart contract now exposes exactly the final redesign lineup:

1. **Basement conditions**: basement relative humidity and basement temperature only.
2. **Absolute humidity**: basement, bedroom, living room, and outdoor absolute humidity, plus
   rainfall as a hoverable bar series on a hidden `rain` scale.
3. **Temperature**: basement, bedroom, living room, and outdoor temperature.
4. **Relative humidity**: basement, bedroom, living room, and outdoor relative humidity.

`ChartSeries` now carries `unit`, `kind`, and `scale` metadata. The uPlot payload includes those
fields plus explicit axis metadata, and the runtime builds per-scale ranges/axes so rainfall stays
visible in hover/select values without rendering a rainfall axis. Hover values append units for
all chart series.

The dashboard renderer now emits charts from `summary.dashboard_charts` in order and no longer
looks up or renders `Daily Basement Trends`, `Basement Versus Outdoor Moisture`,
`Raw Sensor Context`, or the separate rainfall chart on the dashboard. Focused tests cover the
four chart titles, series membership, unit metadata, hidden rain-axis payload, tiered aggregation
bands, and mixed-cadence line-gap behavior.

Verification:

- `uv run pytest tests/test_static_site_summary.py` — 12 passed.
- `uv run pytest` — 40 passed.
- `uv run ruff check` — passed.
- `uv run pyright` — 0 errors.
