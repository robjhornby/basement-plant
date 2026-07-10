# Prototype redesign mockups

Type: prototype
Status: resolved
Parent: ../map.md
Blocked by: 10

## Question

Produce three cheap, visually distinct static mockups of the redesigned dashboard for the user to
react to — reaction beats specification for aesthetics. The direction grill
([ticket 10](10-grill-site-redesign-direction.md)) fixed the page spec; the mockups vary **only
the skin**.

### The three candidates

1. **Instrument panel** — near-black background, phosphor-green/amber accents, monospace
   numerals, dense grid, charts styled like oscilloscope traces. Feels like equipment.
2. **Spring / wet moss** — vibrant greens, clay browns, clean modern layout with earthy colours;
   things growing in the damp months.
3. **Frutiger Aero** — nostalgic early-2000s gloss: aqua gradients, lush skies, glassy panels.
   Requires generating some Frutiger-Aero-style background art; get creative with how the charts
   sit in the gloss.

### The fixed page spec (every mockup renders exactly this)

- Header: the title **"Watch a basement dry"**, nothing else.
- Hero: large current basement relative-humidity + temperature readouts above the hero chart
  (basement relative humidity + temperature + absolute humidity, one-week default, full-history
  range controls).
- Chart 2: basement vs outdoor absolute humidity with rainfall bars (say "rainfall", never "EA").
- Chart 3: basement vs bedroom vs living room relative humidity.
- Thin themed event markers on all charts.
- Footer: "Data to {latest reading time}" + a plain-words data-sources line. No other prose.
- No metric cards, no hypothesis panels, no period table, no physics-report link.

### Constraints

- Each mockup is a self-contained HTML page using real (or lightly faked) current data. Use the
  `/prototype` skill; consult the `dataviz` skill before styling any charts — themed palettes
  must stay legible and colourblind-safe.
- Charts fully themed (colours, typography, optional themed frames) but functional first. Each
  measure gets a dedicated y-axis titled "<measure> / <unit>"; same-measure traces share an axis.
- No unexplained abbreviations anywhere; prefer whole words.
- Throwaway artifacts — favour speed and visual fidelity over code quality; do not wire them
  into the production render path. Static chart fakes are fine; mobile touch behaviour is an
  implementation-round concern, not a mockup concern.

Resolve when the mockups are linked from this ticket (e.g. under
`prototypes/site-redesign-mockups/`), the user has viewed them, and their raw reactions
(what works, what doesn't, per mockup) are recorded in the answer. Picking the winner and
specifying implementation belongs to the follow-up grill (issue 12), not this ticket.

## Answer

All three skins were built as self-contained ~1.9 MB HTML pages over real curated data
(snapshot to 03 Jul 2026) in
[prototypes/site-redesign-mockups/](../../../prototypes/site-redesign-mockups/) —
see its [NOTES.md](../../../prototypes/site-redesign-mockups/NOTES.md) for build detail.
Every per-chart palette triple was validated with the dataviz palette checker against
each theme's surface.

**Raw reactions (Rob, 2026-07-09):**

- **Instrument panel and Frutiger Aero: "fantastic"** — both survive to the winner
  grill. **Spring / wet moss: dropped** (page deleted, theme removed from the
  generator).
- Frutiger Aero: gloss reflections were %-sized so their offsets differed between the
  readout boxes and the chart boxes — wants constant offsets (fixed in place).
- Frutiger Aero: the page title needed a touch more contrast against the sky (fixed in
  place).
- Both: wants units shown in the hover values under the charts, e.g.
  "Relative humidity: 56.2%" — confirmed easily done via uPlot per-series value
  formatters, and applied ("87.0%", "17.9 °C", "13.3 g/m³", "0.20 mm per hour").
- Room comparison: prefers **three single-measure charts** (relative humidity,
  temperature, absolute humidity, each basement vs bedroom vs living room) over one
  combined chart — applied to both pages; this amends the ticket-10 page spec, so the
  redesigned page now carries five charts.

The two updated survivors were re-verified in Chrome (week + full-history views, no
console errors, hover units shown). Picking the winner and slicing implementation is
[ticket 12](12-grill-mockup-winner-and-implementation.md).

## Comments

**2026-07-09 (agent)** — Mockups built and awaiting reactions.

The three skins, in [prototypes/site-redesign-mockups/](../../../prototypes/site-redesign-mockups/)
(see its [NOTES.md](../../../prototypes/site-redesign-mockups/NOTES.md) for build detail):

1. [instrument-panel.html](../../../prototypes/site-redesign-mockups/instrument-panel.html) —
   near-black, phosphor green/amber, monospace scanline readouts, glowing traces.
2. spring-moss.html — warm paper, moss green/clay/teal, serif title, rounded cards,
   hill-silhouette footer (deleted after the reaction round dropped it).
3. [frutiger-aero.html](../../../prototypes/site-redesign-mockups/frutiger-aero.html) —
   aqua sky, sun glow, glossy glass panels, bubbles, green hills.

Each is a self-contained ~1.1 MB page rendering the fixed ticket-10 spec with **real
curated data** (snapshot to 03 Jul 2026): "Watch a basement dry" header; large current
relative-humidity/temperature readouts; the three interactive uPlot charts with
per-measure y-axes titled "measure / unit", min/max bands, thin themed event markers,
Week/All range controls, wheel zoom/pan, hourly rainfall bars (labelled "Rainfall");
footer-only freshness and plain-words sources; no other prose, no metric cards, no
report link. A floating pill (bottom centre) plus left/right arrow keys switch between
the three files — it is scaffolding, not part of any design.

All per-chart palette triples pass the dataviz validator against each theme's surface
(two floor-band CVD warnings are relieved by the always-visible live legend labels).
Verified in Chrome: week-default and full-history views render with no console errors
and no gaps across the 10-minute/hourly cadence boundary.
