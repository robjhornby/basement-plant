# Grill the site redesign direction

Type: grilling
Status: resolved
Parent: ../map.md
Blocked by: 07, 08, 09, 15

## Question

With the quick wins live, pin down the design direction for the bigger dashboard redesign in a
`/grilling` (+ `/domain-modeling` where terminology needs sharpening) session with the user.

The seed idea from the user's todo: "cool design, 3D model of the basement as a black background
with green mesh model of the dehumidifier and other key room elements (or something less cliché)".
Treat that as a mood signal, not a spec.

Questions to walk through (one at a time), each with a recommendation:

- Is 3D actually wanted, or was it a placeholder for "visually striking"? What is the hero view —
  the room, the headline dampness number, the week's chart?
- Mood/direction candidates: instrument-panel, editorial/report, playful-schematic, the green-mesh
  wireframe idea — what resonates, what's ruled out?
- How do the uPlot charts coexist with the design — themed to match, or visually quarantined?
- Page-weight and dependency tolerance: does the no-build-step / self-contained constraint hold
  for the redesign, or is this where a bundler arrives (deferred question from the quick wins)?
- Does the physics report shell inherit automatically, and does the build-info/freshness record
  (issue 03) earn a visible spot on the page?
- Room geometry/fidelity source if 3D: the room-context research on the previous map recorded
  geometry — is approximate-schematic fine, or does it need to feel like *their* basement?

Resolve with the chosen direction and constraints recorded in the answer, and with the mockup
prototype ticket (issue 11) updated so its brief matches the decision. Expect 2–3 candidate
directions to survive into the mockups — the grill narrows, the mockups decide.

## Answer

Grilled 2026-07-09. The user confirmed the full shared understanding below.

### Direction — three mockup candidates

3D is **mood, not spec** — no 3D scene. The hero is the data (headline readouts + one-week
chart), not the room. Candidates for the mockup round (ticket 11):

1. **Instrument panel** — near-black, phosphor-green/amber accents, monospace numerals, dense
   grid, charts styled like oscilloscope traces.
2. **Spring / wet moss** — vibrant greens, clay browns, clean modern layout with earthy colours;
   inspired by things growing in the damp months.
3. **Frutiger Aero** — nostalgic early-2000s gloss: aqua gradients, lush skies, glassy panels;
   needs some generated background art.

Ruled out: editorial/report (disliked), playful-schematic (too cliché), literal wireframe-room
(cliché; its virtues live inside candidate 1).

### Page spec — identical across candidates; mockups vary only the skin

- **Header**: the title **"Watch a basement dry"**, nothing else.
- **Hero**: large current basement relative-humidity + temperature readouts above the hero
  chart — basement relative humidity, temperature, and absolute humidity; one-week default
  range, full history via range controls. Absorbs and replaces the Daily Basement Trends chart.
- **Chart 2**: basement absolute humidity vs outdoor absolute humidity, rainfall bars beneath.
  Physics note recorded during the grill: absolute humidity is the temperature-robust moisture
  measure (relative humidity manufactures correlations via shared temperature swings), which is
  why like-for-like absolute humidity wins here.
- **Chart 3**: basement vs bedroom vs living room relative humidity — both reference sensors.
- **Event markers** stay on all charts: thin, unobtrusive, themed.
- **Footer**: "Data to {latest reading time}" plus a plain-words data-sources line (sensors,
  Open-Meteo, Environment Agency rainfall gauge — provenance naming lives here only; body copy
  just says "rainfall"). No other prose anywhere on the page.
- **Dropped**: all metric cards, the hypothesis-evidence panels, the Daily Basement Trends
  chart, the event-bounded period-metrics table, and the physics report link.
- **Physics report comes off the web entirely** — kept as a locally rendered artifact; hosted
  builds stop publishing it (implementation work for the ticket-12 slicing).

### Standing constraints

- Charts fully themed per direction but functional first; colours/typography follow the theme
  and charts may sit in themed frames. Consult the `dataviz` skill when styling.
- Each **measure** gets a dedicated y-axis titled "<measure> / <unit>" (e.g. "Temperature /
  °C"); traces sharing a measure share its axis. Date/time axis is its own thing.
- **No build step** — the Python render layer with inlined CSS/JS/data stays the whole
  pipeline. "Everything inlined" relaxes to "everything same-origin": image assets (theme art)
  may be uploaded to R2 alongside the HTML and referenced relatively. Page weight may grow
  moderately past today's 1.14 MB.
- **Mobile touch zoom/scrub on charts is a hard implementation requirement** (uPlot needs
  custom touch handlers — implementation-round work).
- **No unexplained abbreviations in any copy**; prefer whole words ("EA" was never understood).
- Absolute humidity is the favoured moisture measure; relative humidity still shown where
  natural.

### Explicitly out of the redesign

- Basement−outdoor absolute-humidity delta — removed as uninteresting: the dehumidifier
  setpoint fully decides it.
- Drying-rate metric (rate of humidity rise after each dehumidifier-off cycle) — wanted later
  as a **net-new feature** on the analysis effort, with **no placeholder slot** in the redesign.
  No such computation exists in the repo yet.
- Research into what the X-Sense sensors actually sense (to validate correlation assumptions) —
  future analysis work.
