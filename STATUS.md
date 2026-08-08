# Status

## Heading

Frutiger Aero dampness dashboard is shipped and live at https://robjhornby.com/basement/.
The tank-fill predictor is being rebuilt around a moisture-drawdown "fuel gauge" (fraction-full /
cycles-remaining / time-remaining), replacing the calendar-days next-full estimate — the fill rate
is non-stationary because the basement is drying. Issue 01 (the estimator) and issue 03 (logged
tank-full events now reach the hosted curated feed) have landed. Only issue 02 (the footer swap)
remains, and it is blocked on Rob confirming the footer wording.

**Autonomy:** ask <!-- ask | go -->

## Threads

<!-- one per live line of work: name — area — one-line state — [artifact](path) -->

<!-- no thread is "our move now": issues 01 + 03 are done and the only remaining step (02, the
     footer swap) is blocked on Rob — see Awaiting. -->


## Awaiting

<!-- someone else's move: name — area — the evidence wanted and who owns getting it — [artifact](path) -->

- tank-fill-gauge/footer — Build — the last remaining tank-fill step (issue 02, footer swap) needs Rob
  to confirm the footer wording (three real-state renderings) before any copy ships; estimator (01) and
  the hosted event feed (03) are both landed, so this is all that's left — [issue 02](.scratch/tank-fill-reassessment/issues/02-footer-gauge-paragraph.md)

## Parked

<!-- deliberately not now: item — the reason -->

- Alerting / anomaly detection / failure notifications — deferred until the loop has run unattended a while
- Analytical successor work (what the X-Sense sensors actually sense) — the tank-fill slice is now active above; the wider "what do the sensors sense" question is still parked
- Cloudflare hosting consolidation (drop GitHub Pages) — user said "not right now"
