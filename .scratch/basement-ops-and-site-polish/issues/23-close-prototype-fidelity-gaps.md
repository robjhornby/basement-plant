# Close production fidelity gaps against the accepted prototype

Type: task
Parent: ../map.md
Status: claimed

## Question

The production render has drifted from the accepted round-3 prototype and the ticket-10 spec in
ways two screenshot passes missed. Close the gaps. This ticket carries the spec **verbatim** —
do not re-paraphrase it into looser acceptance criteria; where anything here is ambiguous, the
reference files win:
[frutiger-aero.html](../../../prototypes/site-redesign-mockups/frutiger-aero.html),
[build_mockups.py](../../../prototypes/site-redesign-mockups/build_mockups.py),
[build_payloads.py](../../../prototypes/site-redesign-mockups/build_payloads.py),
[payloads.json](../../../prototypes/site-redesign-mockups/payloads.json).

### A. Axis and unit contract (mechanical)

Ticket-10 rule, verbatim: *"Each **measure** gets a dedicated y-axis titled '\<measure\> /
\<unit\>' (e.g. 'Temperature / °C'); traces sharing a measure share its axis."* Units are **never
in brackets**. The exact label strings, matching the prototype's `payloads.json`:

- **Basement conditions**: two axes — `Relative humidity / %` (left) and `Temperature / °C`
  (right). This replaces the combined bracketed `y_label` at `summaries.py:251`
  ("Basement relative humidity (%) and temperature (C)").
- **Absolute humidity**: `Absolute humidity / g/m³` (left). The rainfall scale stays hidden with
  hover values retained (ticket-18 behaviour is correct and kept).
- **Temperature**: `Temperature / °C`.
- **Relative humidity**: `Relative humidity / %`.

Unit glyphs matter: `°C` not `C`, `g/m³` not `g/m3`. Hover/legend values follow the ticket-11
accepted examples verbatim: `87.0%`, `17.9 °C`, `13.3 g/m³`, `0.20 mm per hour` — so the rainfall
series unit is `mm per hour`, not `mm`.

Remove `"EA rain mm/hr"` (`summaries.py:827`) → `Rainfall / mm per hour`. The
no-unexplained-abbreviations rule ("EA" was never understood — ticket 10) applies even though
that chart now only reaches the private report.

Ticket-18 tension, resolved here: its "do not include extra axes/series that consume horizontal
chart space" line was about keeping chart 1 basement-only, **not** licence to merge axis titles.
The dedicated-per-measure-axis rule wins; the prototype hero chart shows the pattern (per-measure
axes assigned to left/right sides).

Update any tests asserting the old label/unit strings.

### B. Visual parity with the prototype

Method, not feature checklist — the checklist approach is what failed twice:

1. Render the production dashboard and open the prototype `frutiger-aero.html` over the same (or
   visually equivalent) data snapshot.
2. Playwright screenshots of **both**, side by side, at 1440×900 and 390×844: first fold, chart
   zone, footer/floor.
3. Enumerate every visible difference, port the fix from `build_mockups.py` / the prototype's
   CSS/JS, and repeat until no unintended differences remain.

Known-suspect areas from Rob's review ("the visual style of the charts doesn't match what's in
the prototype"): Aero role palette application, translucent water fill on the hero
relative-humidity series, droplet-capped rainfall bars, bubble-column event markers, grid/axis
text styling, panel frost strength, live-legend styling, gel range buttons.

Constraints carried forward: chart palettes stay the validated ticket-11 set — re-run the dataviz
validator against any surface that changes tone; no external requests; the private report keeps
the generic chart style (per ticket 19).

### Resolution gate

Resolve only when **Rob has viewed the side-by-side screenshots (or the rendered build) and
accepted parity**. An agent-only screenshot pass is not acceptance — that is exactly how the two
previous passes slipped.

## Comments

**2026-07-12 (agent, work done — awaiting Rob's parity acceptance):** Both parts implemented and
committed as `17fe683`; the ticket stays open until Rob accepts.

Part A shipped verbatim: per-measure axes with exact label strings (`Relative humidity / %` left +
`Temperature / °C` right on the hero; `Absolute humidity / g/m³`; `Temperature / °C`;
`Relative humidity / %`), unit glyphs `°C`/`g/m³`, rainfall unit `mm per hour`, hover format
`87.0%` / `17.9 °C` / `0.20 mm per hour` (per-series digits, `–` for missing), and
`EA rain mm/hr` → `Rainfall / mm per hour`. Tests assert the exact strings
([test](../../../tests/test_static_site_summary.py) `test_dashboard_axes_use_verbatim_measure_slash_unit_labels`).

Part B ran the prescribed method — three side-by-side Playwright rounds at 1440×900 and 390×844
([capture script](../assets/ticket-23-screenshot-parity.mjs), stitched pairs in
`output/playwright/ticket-23/side-by-side/`). Ported fixes: concise prototype legend names with
per-chart aero roles (basement stays blue in room charts), Week/All gel buttons on the card title
row, borderless chart canvas on the frost panel, fixed full-history rain-bar scale (zooming no
longer inflates light rain), prototype chart heights 340/320/280/280, h1/h2 typography and fold
geometry, removal of the non-prototype fixed glare overlay, footer "03 Jul 2026, 12:00" date format
and thermometer–hygrometer en dash, 110px deep fish. Chart palettes untouched (validated ticket-11
set; no tones changed, so no re-validation needed).

Bonus find: the private report's charts had been broken since the ticket-19 port (uPlot crashed on
explicitly-undefined axis fonts; reproduced at HEAD) — fixed, report renders all four charts again.
All 19 ticket-20 interaction checks pass against the new runtime
([updated script](../assets/ticket-23-verify-touch.mjs)). Full suite: 42 passed, Ruff/Pyright clean.

One judgment call for the review: the Temperature chart now contains two blues (basement `#0b76c2`,
outdoor `#437fff`) — same pairing the Relative humidity chart already had, and it follows the
prototype's basement-is-blue rule, but say if you want outdoor re-toned.
