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

**Raw reactions (User, 2026-07-09):**

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

**Round 2 (reopened 2026-07-10, re-resolved 2026-07-11):** the extreme descent skin
was built into `frutiger-aero.html` per
[EXTREME-AERO-PLAN.md](../../../prototypes/site-redesign-mockups/EXTREME-AERO-PLAN.md)
(build detail in the 2026-07-11 comment below). **User's raw reactions: "Cool"
overall, but the composition needs rework** — image-to-image transitions read as
seams; the sky image is too short for the page; the SVG-hills + grass layer
duplicates the scenery already inside the waterline image (suspected fix: one tall
generated image running sky → hills → waterline); below the water image the CSS
sun rays/caustics duplicate the image's own rays at lower quality (keep just
gradient + bubbles + faint goldfish); the waterline should peek just above the
fold; above the fold only title + orbs + an animated down arrow, all five charts
moving underwater; plus an open thematic question — should the underwater zone
read as a *basement* (a room in a house) rather than open water? All captured in
detail as
[Refine the extreme aero descent](16-refine-extreme-aero-descent.md), which now
blocks the winner grill instead of this ticket.

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

**2026-07-10 (agent)** — Reopened at the user's request for a second prototyping round:
push the Frutiger Aero skin to the extreme of the style (bolder visuals, possibly
generated/embedded image assets). Round runs concept ideation → user reaction → prototype
update. Reopening re-blocks [ticket 12](12-grill-mockup-winner-and-implementation.md)
(winner grill) until this round resolves.

**2026-07-10 (User, concept reaction)** — "Absolutely fantastic ideas." The **descent
narrative** (sky → ground → underwater as you scroll) is in. **Data-driven condensation
is dropped** for now to simplify. Otherwise go **full extreme parody** — everything on;
tone down from there if needed. Concept plan, asset specs, and image-generation prompts:
[EXTREME-AERO-PLAN.md](../../../prototypes/site-redesign-mockups/EXTREME-AERO-PLAN.md).
Next: User generates the raster assets into `prototypes/site-redesign-mockups/assets/`,
then the agent rebuilds `frutiger-aero.html` around them.

**2026-07-11 (agent)** — All five ChatGPT (GPT Image 2) assets landed in `assets/` and
reviewed: on-brief keepers, no re-generation needed (detail in the plan file's "Asset
review round 1"). **Scope note from User: these images are for the final site, not just
the mockup** — production weight/format/serving decisions go to
[ticket 12](12-grill-mockup-winner-and-implementation.md). Refined transparent-cutout
prompts for User's Recraft round added to
[EXTREME-AERO-PLAN.md](../../../prototypes/site-redesign-mockups/EXTREME-AERO-PLAN.md);
build starts when User calls the asset set final (or immediately with keyed round-1
cutouts if Recraft disappoints).

**2026-07-11 (agent) — asset set final, ready for the build session.** The Recraft
round ran (`*-recraft.png`, true alpha) but User prefers the ChatGPT look and the agent
review agrees: the Recraft cutouts are darker and more photographic (less period-CGI
gloss), with ghosting around the goldfish dorsal fins and green haze around the
dragonfly wings. **Decision: the five ChatGPT images are the final asset set**; the
build keys the three white-background cutouts into alpha itself and deletes the
rejected `*-recraft.png` files. Everything the build session needs is in
[EXTREME-AERO-PLAN.md](../../../prototypes/site-redesign-mockups/EXTREME-AERO-PLAN.md)
(descent zone map, asset status, CSS/SVG feature list, guardrails, build steps).
Remaining to resolve this ticket: build the extreme skin into `frutiger-aero.html`
via `build_mockups.py`, verify in Chrome, update `NOTES.md`, collect User's reactions,
then record the answer and re-resolve.

**2026-07-11 (agent) — extreme skin built; awaiting User's reactions.**
[frutiger-aero.html](../../../prototypes/site-redesign-mockups/frutiger-aero.html)
(2.7 MB self-contained) now carries the full descent: sky zone (title, orb readouts,
hero chart, aurora ribbons, bokeh, goldfish in open air), shoreline zone (moisture
chart, hyper-green hills, dewy grass in the viewport corners, dragonfly perched on
the chart), the half-above/half-below waterline band, and the underwater zone (three
room charts + footer on the "basement floor", sun rays, animated caustics, rising
bubbles, distant fish silhouette). The humidity readout is a glass sphere
water-filled to the reading; temperature is a warm gel orb. Aero-only chart water
styling: hero relative-humidity area as translucent water, droplet-capped rainfall
bars, event markers as rising bubble columns. Asset work per plan: the three ChatGPT
cutouts keyed to true alpha (fins/wings/droplets genuinely translucent), everything
recompressed to WebP (~550 KB embedded), `*-recraft.png` deleted;
`process_assets.py` records the derivation. Guardrails held: chart palettes
untouched and re-validated against the three new frosted zone surfaces (all PASS;
one WARN — living-room amber 2.63:1 on the underwater panel — relieved by the live
legend labels, same relief as round 1); underwater panels get the strongest frost;
[instrument-panel.html](../../../prototypes/site-redesign-mockups/instrument-panel.html)
visually unchanged. Verified in headless Chrome at 1440px/500px, week + full
history, zero console errors. Detail in
[NOTES.md](../../../prototypes/site-redesign-mockups/NOTES.md). Next: User views the
page and reacts; then the answer is updated and the ticket re-resolves.
