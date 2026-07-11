# Production Frutiger Aero asset pipeline

Type: task
Parent: ../map.md
Status: resolved

## Question

Move the final Frutiger Aero theme art from the prototype into the production static-site
pipeline, with explicit production weight and serving rules.

Resolve when:

- The upscaled scene source
  `prototypes/site-redesign-mockups/assets/upscalemedia-tall-scene.webp` is the canonical source
  for the production tall scene, not the smaller 1024x1536 derived mockup image.
- Production generates responsive/compressed same-origin derivatives from that source rather than
  serving the 1.9 MB source to every visitor by default.
- The regenerated no-shadow dehumidifier source
  `prototypes/site-redesign-mockups/assets/dehumidifier-no-shadow.png` replaces
  `dehumidifier.png` for production; the WebP derivative is rebuilt from the no-shadow file.
- The final production asset set includes the tall scene derivatives, floor strip, no-shadow
  dehumidifier, goldfish, and dragonfly; superseded sky/waterline/grass/old-dehumidifier assets
  are not used by the live site.
- Assets are published as same-origin R2 objects alongside the generated HTML, with cache headers
  compatible with the existing site Worker policy.
- Tests or verification cover the generated asset manifest/paths so missing production assets fail
  locally before deployment.

## Answer

Implemented the production Frutiger Aero asset pipeline in the static-site build:

- Added the production source art under
  `src/basement_analysis/site_assets/frutiger_aero/source/`: the upscaled tall scene copied from
  `prototypes/site-redesign-mockups/assets/upscalemedia-tall-scene.webp`, floor strip, no-shadow
  dehumidifier, goldfish, and dragonfly. Superseded sky/waterline/grass/old-dehumidifier sources
  are not in the production source set.
- Added Pillow as a runtime dependency and made `static_site.py` generate same-origin WebP
  derivatives plus `assets/frutiger-aero/manifest.json`: `tall-scene-960.webp`,
  `tall-scene-1440.webp`, `tall-scene-2048.webp`, `floor-strip.webp`, `dehumidifier.webp`,
  `goldfish.webp`, and `dragonfly.webp`.
- The asset manifest records paths, dimensions, content types, cache policy, source names, byte
  sizes, and the scene srcset so missing/stale production assets fail in local tests.
- The site Worker now serves only the generated Frutiger Aero asset paths under
  `/basement/assets/frutiger-aero/` and keeps the source art unreachable.
- The hosted publish workflow now uploads the generated WebP assets and manifest alongside
  `index.html`, with `public, max-age=600, no-transform` cache metadata.
- Verified with `uv run pytest tests/test_static_site_summary.py`, `uv run pytest`, `uv run
  ruff check .`, `uv run pyright`, site Worker `npm test`, `uv build`, and an explicit wheel
  contents check for the packaged source art.
