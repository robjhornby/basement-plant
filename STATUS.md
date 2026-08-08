# Status

## Heading

Frutiger Aero dampness dashboard is shipped and live at https://robjhornby.com/basement/.
The tank-fill predictor is being rebuilt around a moisture-drawdown "fuel gauge" (fraction-full /
cycles-remaining / time-remaining), replacing the calendar-days next-full estimate — the fill rate
is non-stationary because the basement is drying. Issue 01 (the estimator) has landed; the footer
swap (02) and getting logged events into the hosted feed (03) remain.

**Autonomy:** ask <!-- ask | go -->

## Threads

<!-- one per live line of work: name — area — one-line state — [artifact](path) -->

- tank-fill-gauge — Build — estimator built + tested (issue 01 done, old footer still live);
  next: issue 03 (get logged tank-full events into the hosted curated feed) then issue 02 (footer
  swap) — [PRD](.scratch/tank-fill-reassessment/PRD.md)

## Awaiting

<!-- someone else's move: name — area — the evidence wanted and who owns getting it — [artifact](path) -->

- tank-fill-gauge/footer — Build — issue 02 needs Rob to confirm the footer wording (three real-state
  renderings) before any copy ships — [issue 02](.scratch/tank-fill-reassessment/issues/02-footer-gauge-paragraph.md)

## Parked

<!-- deliberately not now: item — the reason -->

- Alerting / anomaly detection / failure notifications — deferred until the loop has run unattended a while
- Analytical successor work (what the X-Sense sensors actually sense) — the tank-fill slice is now active above; the wider "what do the sensors sense" question is still parked
- Cloudflare hosting consolidation (drop GitHub Pages) — user said "not right now"
