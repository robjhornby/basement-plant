# Reshape dashboard chart lineup for redesign

Type: task
Parent: ../map.md

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
