# Add mobile touch chart interactions

Type: task
Parent: ../map.md

## Question

Harden the uPlot interactions for touch devices so the production dashboard works on mobile, not
only desktop mouse/trackpad.

Resolve when:

- Charts support mobile touch scrub/select for reading values.
- Charts support mobile zoom/pan or an equivalent touch-friendly range control without fighting
  normal page scroll.
- Desktop hover, wheel zoom, pan, week/full-history controls, min/max bands, event markers, and
  rainfall hover values still work.
- Interaction code remains self-contained in the generated HTML with vendored uPlot; no CDN or
  frontend build step.
- Browser verification covers at least one mobile viewport and one desktop viewport.
