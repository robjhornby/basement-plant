# Production Frutiger Aero asset pipeline

Type: task
Parent: ../map.md

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
