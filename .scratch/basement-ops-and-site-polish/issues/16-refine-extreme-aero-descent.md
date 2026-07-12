# Refine the extreme aero descent: one tall scene image, fold-first layout, basement nod

Type: prototype
Status: resolved
Parent: ../map.md

## Question

Round 3 of the extreme Frutiger Aero skin. The round-2 build
([frutiger-aero.html](../../../prototypes/site-redesign-mockups/frutiger-aero.html),
built 2026-07-11) landed well overall ("Cool") but the composition needs rework in
five specific ways, plus one open thematic question. Captured verbatim-in-spirit from
User's 2026-07-11 reaction round; resolve by reworking the prototype (new asset
round + rebuild) and collecting reactions again.

### 1. Image-to-image transitions don't work

The bottom of one image does not lead into the top of the next. The CSS gradient
bridges between the sky image, the SVG hills/grass layer, and the waterline image
read as seams, not one continuous world.

### 2. The sky image is too short

The page needs far more vertical sky than the sky image provides — it ends (fades
out) long before the grass/hills layer begins, leaving a stretch of flat gradient
in the middle of zone A.

### 3. Duplicated scenery around the waterline — replace with one tall image

Today the stack is: SVG hills with grass cutouts overlaid, then immediately below,
the waterline image which *itself* contains a realistic sky and hills, then the
underwater part of that image. The same scenery appears twice in different styles.

**Suspected fix (User):** get rid of the grass cutouts and SVG hills entirely and
generate **one large tall image** that runs sky → hills → waterline in a single
composition — image generation is more likely to get the transitions right inside
one image than we are stitching several. (Implication: a new ChatGPT asset round
with a portrait/tall prompt; the round-2 `sky.png`/`waterline.png`/`grass.png`
cutout approach is superseded for the scene. The goldfish and dragonfly cutouts
are not implicated by this item.)

### 4. Simplify below the water image

Below the waterline image, use just a **gradient background with the rising
bubbles and the faint goldfish silhouette**. Drop the CSS sun rays and animated
caustics: they repeat the sun rays and refracted light already present in the
waterline image directly above, but at visibly lower quality.

### 5. Waterline placement: peek above the fold

The waterline currently sits far below the fold. It should be **peeking at the
bottom of the first screen, just above the fold**, inviting the visitor to scroll
down into the water.

### 6. Fold-first layout: all charts move underwater

Above the fold: **only the title, the humidity/temperature orbs, and an animated
down arrow** inviting scrolling. All five charts move below the fold, underwater.
(This reshapes the round-2 zone map: the hero chart leaves the sky zone and the
moisture chart leaves the shoreline zone; the ground zone as a content zone may
disappear entirely — the descent imagery compresses into the first screen +
scroll transition.)

### 7. Open thematic question: make it a basement?

Would it make more sense if the imagery somehow showed that the thing below
ground / below the water **is a basement** — a room in a house? Currently the
underwater zone is just open water with no nod to being a room. Concept ideation
with User before building: e.g. does the underwater section gain architectural
cues (walls, brick, joists, a cross-section feel), does the waterline sit at a
house's ground level, or does the water metaphor stay pure? This may change what
the single tall scene image (item 3) should contain, so settle it **before**
writing the new image prompts.

### Constraints carried forward

- Chart palettes stay the validated ticket-11 set; re-run the dataviz validator
  against any panel surface that changes tone.
- Legibility guardrail unchanged: frosted panels strengthen as the background
  gets louder; plot areas stay quiet glass.
- `instrument-panel.html` stays visually untouched; chart-runtime changes stay
  theme-scoped.
- Assets remain final-site keepers: keep `process_assets.py` as the derivation
  record; production weight/format/serving still belongs to
  [ticket 12](12-grill-mockup-winner-and-implementation.md).

### Suggested order within the round

1. Settle the basement-nod question with User (item 7) — it shapes the scene image.
2. Draft the tall-scene prompt(s); User generates the image(s).
3. Rework the layout (items 1–6), rebuild, verify (Chrome week/full, no console
   errors, palette re-validation), collect reactions.

## Answer

Resolved 2026-07-11: the round-3 build is **accepted** ("It all looks good, no big
remaining changes") and User declared the Frutiger Aero theme the winner, ready for
real-site implementation (ticket 12).

How each item landed:

1–3. **One tall scene image** (`tall-scene.png`, 1024×1536) replaced the
sky/SVG-hills/waterline stitch — no seams, no flat-gradient sky. On landscape
screens the image top (and the sun) crops off above the viewport; **User accepted
the desktop sun crop** (no landscape companion render). On portrait screens a
CSS gradient + radial sun-glow extension fills above the image behind a 56px
crossfade mask, verified seamless by pixel sampling.
4. Below the water: gradient + rising bubbles + faint goldfish only; CSS sun
rays and animated caustics deleted.
5–6. Fold-first: title + orbs + bobbing chevron above the fold, the waterline
(meniscus pinned at 92vh, ~63% of image height) peeking at the bottom; all five
charts underwater. Reaction amendment, applied: **charts start just below the
fold** (4vh padding), floating over the scene's underwater sunbeams.
7. Basement nod (settled with User, then revised): the planned brick wall strips
were generated but **rejected on looks and dropped**; the nod is the concrete
floor band (horizontally-seamless crop of `floor-strip.png`) plus a glossy CGI
dehumidifier (`dehumidifier.png`, keyed by edge-connected flood fill — not the
white un-blend, the body is white) standing by the footer.

Assets: five keepers now — tall-scene, floor-strip, dehumidifier, goldfish,
dragonfly (~280 KB derived); sky/waterline/grass superseded. Verification:
Playwright + system Chrome at 1440×900 and 390×844 (fold/full/full-history), zero
console messages, no cadence gaps; instrument page pixel-diff identical; palettes
re-validated against sampled surfaces — all PASS, contrast WARNs relieved by live
legends. Details: [NOTES.md](../../../prototypes/site-redesign-mockups/NOTES.md)
and [EXTREME-AERO-PLAN.md § Round 3](../../../prototypes/site-redesign-mockups/EXTREME-AERO-PLAN.md).

## Comments

**2026-07-11 (agent)** — Created from User's round-2 reaction round on
[Prototype redesign mockups](11-prototype-redesign-mockups.md), which re-resolved
with these requests outstanding. The winner grill
([ticket 12](12-grill-mockup-winner-and-implementation.md)) is re-blocked on this
ticket.

**2026-07-11 (agent, with User)** — Item 7 settled: the underwater zone becomes the
basement. Top to bottom: sky → hills → waterline at the fold → underwater. The
underwater bulk stays pure water (gradient + bubbles + faint goldfish), framed by
thin brick/plaster cross-section wall strips at the page edges flanking the charts —
tiled vertically, fading in from the murk at their top so no hard seam; the footer
is a side-on concrete floor band where the walls stop, with a glossy 3/4-view CGI
dehumidifier on it (isometric flavor from the object's pose, not tilted geometry —
one eye-level camera throughout). Narrow screens: wall strips shrink to thin edge
slivers, never hidden. Full concept, decisions, and the four round-3 ChatGPT prompts
(tall-scene, wall-strip, floor-strip, dehumidifier) recorded in
[EXTREME-AERO-PLAN.md § Round 3](../../../prototypes/site-redesign-mockups/EXTREME-AERO-PLAN.md).
Waiting on User to generate the four images.

**2026-07-11 (agent, with User)** — Walls dropped: User generated the wall-strip but
the brick cross-section didn't look good; the concrete floor + dehumidifier are the
whole basement nod for now (slivers-on-mobile plan dropped with it). The other three
assets (`tall-scene.png`, `floor-strip.png`, `dehumidifier.png`) reviewed and
accepted, no re-generation — detailed edge/blend notes in the plan doc's round-3
build-changes section. Proceeding to layout rework and rebuild.

**2026-07-11 (agent)** — Round-3 build complete, awaiting User's reactions. Items
1–6 all addressed: one tall scene (no seams, no flat-gradient sky), waterline
peeking above the fold, fold-first layout (title + orbs + animated chevron only),
all five charts underwater, gradient + bubbles + faint goldfish below the water
(rays/caustics deleted), concrete floor + keyed dehumidifier as the basement nod.
Verified at 1440×900 and 390×844 (fold/full/full-history, zero console messages);
instrument page pixel-diff identical to the committed build; palettes re-validated
against the sampled underwater frost surfaces — all PASS, contrast WARNs relieved
by live legends (details in [NOTES.md](../../../prototypes/site-redesign-mockups/NOTES.md)).
One known tradeoff for the reaction round: on landscape/desktop screens the 2:3
scene crops above the viewport, so **the sun is only visible on portrait/mobile**;
a landscape companion render of the same scene would restore it on desktop.
