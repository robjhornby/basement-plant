# Grill the mockup winner and implementation shape

Type: grilling
Parent: ../map.md
Blocked by: 11

## Question

Close the human-in-the-loop design loop: with the user's mockup reactions recorded (issue 11),
run a `/grilling` session to pick the winning direction (or the hybrid) and pin the
implementation shape, then graduate the redesign implementation work out of the map's fog into
concrete task tickets.

To settle:

- Which mockup (or combination) wins, and which specific elements from the losers survive.
- Implementation mechanics: stays in the Python render layer with inlined assets, or introduces a
  frontend build step (this decision was explicitly deferred from the quick wins) — and if a build
  step arrives, how it fits the "publish = write HTML objects to R2" model and the GitHub Actions
  runner.
- Scope slicing into autonomous implementation tickets sized one session each, with blocking
  edges, created as new child issues of this map.

Implementation work already decided by the direction grill (issue 10) that the slicing must
carry, whatever the winning skin:

- Unpublish the physics report: hosted builds stop writing it to R2, the existing R2 object is
  removed, and the dashboard link is gone; the report stays a locally rendered artifact.
- Mobile touch zoom/scrub on the uPlot charts (custom touch handlers or a small plugin).
- The page-spec changes: hero readouts + three-chart lineup, dropped components (metric cards,
  hypothesis panels, daily-trends chart, period table), "<measure> / <unit>" dedicated y-axes,
  footer freshness line ("Data to {latest reading time}") plus plain-words sources, and the
  no-unexplained-abbreviations copy rule.
- Same-origin image assets (theme art) uploaded to R2 alongside the HTML if the winning skin
  needs them — no build step either way (decided in issue 10; revisit only if the winning
  mockup proves impossible without one).

Resolve when the winner and mechanics are recorded in the answer, the implementation tickets
exist and are wired, and the redesign entry in the map's Not-yet-specified fog is cleared.
