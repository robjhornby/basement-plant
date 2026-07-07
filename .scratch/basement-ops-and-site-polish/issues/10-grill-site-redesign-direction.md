# Grill the site redesign direction

Type: grilling
Parent: ../map.md
Blocked by: 07, 08, 09

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
