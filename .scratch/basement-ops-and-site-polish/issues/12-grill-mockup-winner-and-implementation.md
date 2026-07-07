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
- Confirm the physics report inherits the shell/typography only (standing decision), and whether
  any redesign element (e.g. freshness display) pulls in the build-info record from issue 03.

Resolve when the winner and mechanics are recorded in the answer, the implementation tickets
exist and are wired, and the redesign entry in the map's Not-yet-specified fog is cleared.
