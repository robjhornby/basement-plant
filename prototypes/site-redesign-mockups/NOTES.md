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
2. [frutiger-aero.html](frutiger-aero.html) — the round-3 **extreme** build (see
   [EXTREME-AERO-PLAN.md § Round 3](EXTREME-AERO-PLAN.md)): ONE tall scene image
   (sky → hills → waterline → underwater) pinned so the meniscus peeks just above
   the fold; above the fold only the title, the two readout orbs (water-filled
   glass for humidity — the fill height *is* the reading — warm gel for
   temperature), and a bobbing scroll chevron. All five charts sit underwater,
   with the concrete "basement floor" and a glossy CGI dehumidifier at the very
   bottom — the basement nod. Keeps: aurora ribbons, bokeh, goldfish (sky +
   deep silhouette), dragonfly skimming the water, rising bubbles, Vista-grade
   glass with sheen sweeps, candy gel buttons, hero relative-humidity area as
   translucent water, droplet-capped rainfall bars, event markers as bubble
   columns. Dropped in round 3: SVG hills + grass cutouts, the separate
   sky/waterline images, CSS sun rays and animated caustics (they duplicated the
   scene image at lower quality), and the planned brick wall strips (generated
   but rejected on looks).

A third candidate (spring / wet moss: warm paper, moss green/clay/teal, serif title)
was dropped after the round-1 reaction round — see below.

## How they were built

- `build_payloads.py` — builds `payloads.json` (five chart payloads + latest readouts)
  from the curated parquet snapshot using the repo's own aggregation helpers
  (tiered 10-minute/hourly buckets, min/max bands, hourly rainfall sums).
- `process_assets.py` — derives `assets/derived/*.webp` from the round-3 keeper art
  in `assets/` (User, 2026-07-11: keepers for the final site): `tall-scene`
  recompressed at native size (84 KB), the concrete band cropped out of
  `floor-strip` and made horizontally seamless by wrap-crossfade, `dehumidifier`
  keyed via edge-connected flood fill (NOT the global white un-blend — the body is
  white) with a feathered rim and the baked shadow converted to translucent black,
  goldfish/dragonfly un-blended to true alpha as before. ~280 KB total. Run with
  `uv run --with pillow python …`.
- `build_mockups.py` — wraps the payloads, the vendored uPlot, a shared multi-axis chart
  runtime (per-measure y-axes, week/all range controls, wheel zoom/pan, event markers,
  min/max bands, custom rainfall bars), and one CSS skin per theme into two
  self-contained HTML pages (instrument 1.92 MB, aero 2.31 MB with embedded art, no
  external requests). Chart→zone slot assignment is now per-theme config
  (`chartSlots`): instrument keeps charts in sky/ground/under, aero routes all five
  underwater. The aero water-chart styling stays theme-flag-scoped; the round-3
  instrument page was pixel-diffed against the committed one — identical.
- Chart palettes are unchanged from round 1 (guardrail). Round 3 moves all five
  charts onto the underwater frost — the first two float over the scene's own
  underwater sunbeams — so each chart triple was re-validated with the dataviz
  skill's `validate_palette.js` against its rendered surface (sampled `#c3e0ee`
  and `#c0d0dc` for charts 1–2, `#c8d1d6`–`#c9d4dc` for the room charts): all
  PASS; the sub-3:1 contrast WARNs (2.2:1–3.0:1 across orange/green/violet/
  pink/amber) are relieved by the always-visible live legend labels under every
  chart, as in round 2.

## Reactions (User, 2026-07-09)

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

## Round 2 — extreme Frutiger Aero (built 2026-07-11, reactions in)

User reopened the ticket to push the aero skin to the full extreme parody
("everything on; tone down from there"). Landed well ("Cool") but the composition
needed rework — stitched-image seams, short sky, duplicated scenery, low-quality
CSS rays/caustics, waterline below the fold — captured as
[ticket 16](../../.scratch/basement-ops-and-site-polish/issues/16-refine-extreme-aero-descent.md).

## Round 3 — one tall scene + fold-first descent (built 2026-07-11, awaiting reactions)

Ticket 16: one tall scene image replaces the sky/hills/waterline stitch (the
seams and the flat-gradient sky stretch go away); the fold shows only title +
orbs + scroll hint with the waterline peeking at the bottom; all charts move
underwater; below the water it's just gradient + bubbles + a faint goldfish; the
page bottoms out on a concrete floor with a glossy CGI dehumidifier (the whole
basement nod — brick wall strips were generated but rejected on looks).

Scene geometry: the 2:3 image is pinned by its meniscus (~63% of image height) at
92vh. On landscape screens the image top crops off above the viewport — **the sun
is not visible on desktop**; a landscape companion render of the same scene would
fix that if wanted. On portrait screens the sun shows and a CSS gradient + radial
sun-glow extension fills above the image top, with a 56px crossfade mask hiding
the join (verified seamless by pixel sampling).

Verified with Playwright + system Chrome at 1440×900 and 390×844: fold, full-page
and full-history screenshots, no console errors/warnings, no cadence-boundary
gaps; instrument page pixel-diff identical; palettes re-validated (see above).

Reactions (User, 2026-07-11): accepted — "It all looks good, no big remaining
changes". The desktop sun crop is fine as-is (no landscape companion render).
One amendment, applied: the charts start **just below the fold**, floating over
the scene's underwater sunbeams, rather than after the image ends. User declared
the Frutiger Aero theme the winner; implementation on the real site is ticket 12.
