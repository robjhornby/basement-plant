# Extreme Frutiger Aero — round-2 plan (ticket 11, reopened)

> **Round 3 supersedes parts of this plan** — see [Round 3](#round-3--one-tall-scene--basement-walls-ticket-16)
> at the end: one tall scene image replaces `sky.png` + the SVG hills/grass layer +
> `waterline.png` for the scene; the underwater zone gains basement walls, a concrete
> floor, and a dehumidifier; all charts move below the fold.

Approved direction (User, 2026-07-10): full extreme parody, tone down later if needed.
The **descent narrative** is the spine. **Data-driven condensation is dropped** for now.
The page spec itself (title, orb-worthy readouts, five charts, footer-only prose) does
not change — only the skin goes to eleven.

## The descent narrative

The background scrolls *with* the page (no more `background-attachment: fixed`) and
tells one story top to bottom: you start in the sky and sink into the damp.

| Zone | Page content | World |
| --- | --- | --- |
| **A — Sky** | Title, hero readout orbs, hero chart | Saturated cyan sky, cumulus clouds, sun + lens flare (upper left), a goldfish swimming through open air, drifting bokeh, aurora ribbons behind the glass |
| **B — Ground / shoreline** | Chart 2 (basement vs outdoor absolute humidity + rainfall — rain lands at ground level) | Rolling hyper-green hills, dewy macro grass blades rising into the viewport corners, a dragonfly perched near the chart |
| **Waterline band** | (divider between B and C) | The canonical half-above/half-below water shot — meniscus edge-on, hills above, sunbeams below |
| **C — Underwater** | Charts 3–5 (room comparison) + footer | Deep aqua, volumetric light rays slanting down, animated caustics, bubbles rising past the panels, a distant fish silhouette; the footer sits on the "basement floor" |

CSS gradients extend above/below and between the images so any page height works and
image edges blend invisibly.

## Asset status

Files live in `prototypes/site-redesign-mockups/assets/`. The mockup build embeds them
as data URIs so the page stays self-contained.

**Scope (User, 2026-07-11): these assets are keepers for the final site, not just the
mockup.** So weight matters: the build recompresses (scenes → JPEG/WebP at quality ~80,
cutouts → WebP/PNG with alpha), and on the real site they ship as same-origin files
(allowed by the ticket-10 spec) rather than data URIs — that slicing belongs to
ticket 12. Provenance: GPT Image 2 via ChatGPT; transparent cutouts via Recraft.

**Asset set is FINAL (User, 2026-07-11): the five ChatGPT images win.** The Recraft
round was run (`*-recraft.png`, true alpha) but loses on style for all three cutouts —
darker, more photographic, less period-CGI gloss, plus ghosting artifacts around the
goldfish dorsal fins and a green haze around the dragonfly wings. The build session
keys the three ChatGPT cutouts itself (un-blend white into alpha — fins/wings become
genuinely translucent) and deletes the `*-recraft.png` files.

| File | Role | Status |
| --- | --- | --- |
| `sky.png` | Zone A backdrop | Final |
| `waterline.png` | Zone B→C transition | Final |
| `grass.png` | Zone B foreground corners | Final; on white — key to alpha at build |
| `goldfish.png` | Zones A + C fauna | Final; on white — key to alpha at build |
| `dragonfly.png` | Zone B garnish (optional) | Final; on white — key to alpha at build |
| `*-recraft.png` | — | Rejected (style); delete at build |

Review of round 1 (2026-07-11): all five on-brief, none needs a ChatGPT re-generation.
`sky` is a direct hit (sun upper-left, hex flare, light bottom edge blends into zone B).
`waterline` is the star; its bright shallow bottom edge gets darkened by a gradient
overlay in the build so the page keeps descending into deep zone-C aqua. `grass` blades
touch the left/right frame edges, so corner placements must hang those edges offscreen —
the one real flaw the Recraft round fixes. `goldfish` and `dragonfly` are on white;
un-blending white into alpha makes fins/wings genuinely translucent, which reads well
over the sky — so keying them is a fully viable fallback if Recraft's style is weaker.

## Recraft round — three transparent cutouts

Recraft sets output size with the size/frame selector next to the prompt, not from
prompt text — pick the landscape preset closest to the target listed per asset.
1024-class is ample: the largest on-page display is the grass at roughly 500 CSS
pixels wide, and production recompression shrinks everything anyway.

### grass.png — select wide landscape, closest to 1820×1024

Composition intent: one compact tuft for planting in a page corner (scaled, flipped,
reused) — not grass along the whole bottom edge. Only the bottom frame edge may cut
blades off; every blade tip and side must end naturally inside the frame.

A single compact tuft of vivid green grass, about half the frame wide, centered at the bottom of the frame, macro close-up, the blades covered in large glistening water droplets, mid-2000s Frutiger Aero CGI advertisement style, glossy and hyper-saturated. The blades grow up from the bottom edge of the frame, where their stems may be cut off, and spread slightly outward; no blade touches the left, right, or top edges — empty transparent space surrounds the tuft on those three sides. Transparent background. No text.

### goldfish.png — select landscape, closest to 1365×1024

A single glossy CGI goldfish in profile swimming to the right, flowing semi-translucent fins, mid-2000s Frutiger Aero tech-advertisement style, hyper-saturated orange with strong specular highlights, the whole fish fully inside the frame with margin on all sides. Transparent background. No text.

### dragonfly.png — select landscape, closest to 1536×1024

A glossy CGI dragonfly in flight seen from the side, iridescent metallic blue-green body, semi-transparent finely-veined wings, mid-2000s Frutiger Aero advertisement style, hyper-saturated, fully inside the frame with margin on all sides. Transparent background. No text.

## Round-1 ChatGPT prompts (already generated, kept for future re-generation)

### sky

A Frutiger Aero desktop wallpaper in the style of mid-2000s Windows Vista stock art: a hyper-saturated cyan-to-azure sky filled with puffy white cumulus clouds, a bright sun in the upper left with a subtle hexagonal lens flare trailing diagonally toward the centre, ultra-clean glossy CGI advertisement look. Sky only — no ground, no text, no watermarks. Wide landscape format.

### waterline

A Frutiger Aero stock photograph in mid-2000s tech-advertisement CGI style: the camera exactly at the surface of crystal-clear water, split half above and half below the waterline. Above the line: impossibly green rolling hills under a bright cyan sky with a few clouds. Below the line: clean aqua water with sunbeams and caustic light patterns and a few small rising bubbles. Glossy, hyper-saturated, optimistic. No text, no people, no watermarks. Wide landscape format.

## Built in pure CSS/SVG (no assets needed)

- **Orb readouts**: current relative humidity inside a giant Aqua glass sphere,
  water-filled to the reading (the fill *is* the readout — this is not the dropped
  condensation gimmick); temperature in a warm gel orb; caustic light spot under each.
- **Vista-grade glass**: thicker bevels, cyan edge glow, a specular sheen that sweeps
  each panel once on load and on hover.
- **Candy gel range buttons** with under-reflection.
- **Data-as-water chart styling** (aero theme only): hero relative-humidity area fill
  as translucent water with a bright meniscus edge, droplet-capped rainfall bars,
  event markers as thin rising bubble columns.
- **Atmosphere**: aurora/chrome ribbons, drifting bokeh, slow clouds parallax (maybe),
  rising-bubble animation in zone C, underwater light rays + animated caustics.

## Guardrails

- Legibility is non-negotiable: the frosted panels get *stronger* (more blur, more
  white) as the background gets louder; the plot areas stay quiet glass.
- The validated colourblind-safe chart palettes do not change; re-run the dataviz
  palette validator against any panel surface that changes tone.
- `instrument-panel.html` is untouched — chart-runtime changes must be theme-scoped.

## Build changes (when assets land)

`build_mockups.py`: rewrite `AERO_CSS`/`AERO_ART` around the zone backdrop; add an
`assets/` data-URI embed step; add theme-conditional hooks in the shared chart runtime
for the aero water styling. Then re-verify both pages in Chrome (week + full history,
no console errors) and update `NOTES.md`.

## Round 3 — one tall scene + basement walls (ticket 16)

User's round-2 reactions ([ticket 16](../../.scratch/basement-ops-and-site-polish/issues/16-refine-extreme-aero-descent.md)):
the stitched scene reads as seams, the sky is too short, the scenery duplicates around
the waterline, the CSS sun rays/caustics under the waterline image are low-quality
repeats, the waterline sits too far below the fold, and all charts should move
underwater. Plus the settled item-7 concept (2026-07-11): **the underwater zone becomes
the basement.**

### The round-3 composition, top to bottom

1. **Sky (above the fold)**: title, readout orbs, an animated down arrow — nothing
   else. The top of the tall scene image is clean featureless gradient sky, so CSS
   extends it upward invisibly to any viewport height (fixes "sky too short" without
   a visible bridge).
2. **The fold**: the scene image's waterline peeks at the bottom of the first screen,
   inviting the scroll. The fold is ground level; below it is the basement.
3. **Underwater (all five charts + footer)**: gradient background, rising bubbles,
   faint goldfish silhouette — no CSS sun rays, no animated caustics, and (revised
   2026-07-11) **no basement wall strips**: the generated brick cross-section didn't
   look good, so the walls are dropped and the bulk of the zone stays pure water.
4. **Floor (footer)**: a side-on concrete floor band; a glossy 3/4-view CGI
   dehumidifier sits on it with a soft contact shadow. The floor + dehumidifier are
   the *whole* basement nod for now. The isometric flavor comes from the object's
   pose, not tilted geometry — the page keeps one eye-level camera throughout.

### Decisions

- Superseded for the scene: `sky.png`, `waterline.png`, `grass.png`, the SVG
  hills/grass layer. Kept: `goldfish.png`, `dragonfly.png` cutouts and their derived
  WebPs.
- **Walls dropped (User, 2026-07-11)**: the wall-strip generation was run but the
  brick cross-section didn't look good; the concrete floor and dehumidifier carry
  the basement nod alone. (The wall-strip prompt below is kept only as a record;
  the slivers-on-narrow-screens plan went with it.)
- Floor band: try the generated concrete strip first; plain CSS gradient/noise is the
  fallback if it fights the scene.
- Guardrails unchanged: validated chart palettes, frosted-panel legibility, palette
  re-validation against any changed panel surface, `instrument-panel.html` untouched.

### Round-3 ChatGPT prompts

#### tall-scene — portrait 1024×1536

A tall vertical Frutiger Aero scene in the style of mid-2000s Windows Vista stock art, one single continuous composition from top to bottom: the top third is a clean, nearly featureless hyper-saturated cyan-to-azure sky gradient with at most a few wisps of cloud; below that, puffy white cumulus clouds and a bright sun on the upper left with a subtle hexagonal lens flare; the sky meets impossibly green glossy rolling hills that descend to the shore of a crystal-clear lake; at the bottom of the frame the camera sits exactly at the water surface, split above and below the waterline, and the lowest part of the frame is below the surface: clean aqua water with sunbeams, caustic light patterns and a few small rising bubbles, darkening smoothly toward the bottom edge into deep blue. Ultra-clean glossy CGI advertisement look, hyper-saturated, optimistic. No text, no people, no watermarks.

#### wall-strip — portrait 1024×1536 (RUN AND REJECTED — walls dropped, kept as record)

A tall narrow vertical cut-away cross-section of a basement wall in mid-2000s Frutiger Aero CGI advertisement style: even, regular courses of glossy red-brown bricks with pale mortar joints on one side and a smooth pale plaster face on the other, perfectly straight vertical edges, completely uniform lighting from top to bottom with no vignette and no perspective, the pattern repeating evenly so the strip could tile vertically. Clean, glossy, hyper-saturated. Plain white background around the strip. No text, no watermarks.

#### floor-strip — landscape 1536×1024

A clean horizontal band of smooth pale-grey polished concrete floor seen exactly side-on, occupying the lower half of the frame, with a subtle glossy specular sheen and completely uniform lighting from left to right with no vignette and no perspective, so the band could tile horizontally. Mid-2000s Frutiger Aero CGI advertisement style. Plain white background above the band. No text, no watermarks.

#### dehumidifier — landscape 1536×1024

A single glossy CGI portable home dehumidifier seen from a three-quarter angle, mid-2000s Frutiger Aero tech-advertisement style: rounded white and cyan plastic body, air-vent grille, a small glowing indicator light, strong specular highlights, hyper-saturated and optimistic, the whole unit fully inside the frame with margin on all sides, on a plain white background. No text, no watermarks.

### Build changes (when round-3 assets land)

- `process_assets.py`: derive the tall scene WebP (bottom edge gets a darkening
  overlay in CSS, not baked); crop the concrete band out of `floor-strip` and make
  it horizontally seamless; key `dehumidifier` via edge-connected background removal
  (NOT the global white un-blend — the body itself is white), keeping interior
  whites opaque. Asset review 2026-07-11: all three accepted, no re-generation;
  tall-scene top row is not flat (sun glow, G 69→118), so any CSS sky extension
  above it needs a radial glow continuation, not a plain vertical gradient (desktop
  crops the top off-screen anyway); tall-scene waterline sits at ~62% of image
  height; floor band starts at 49% height, left/right lighting uniform within ~2%.
- `build_mockups.py`: fold-first layout (title + orbs + down arrow in the sky,
  waterline at the fold, all charts underwater); one scene image positioned so the
  waterline peeks just above the fold; drop the SVG hills/grass layer, the grass
  cutouts, the underwater sun rays and animated caustics; add the floor band and
  the dehumidifier by the footer.
- Verify in Chrome (week + full history, 1440px and 500px, no console errors);
  re-validate palettes against any changed panel surface; update `NOTES.md`.
