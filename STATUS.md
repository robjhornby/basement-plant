# Status

## Heading

Frutiger Aero dampness dashboard is shipped and live at https://robjhornby.com/basement/.
The tank-fill predictor has been rebuilt around a moisture-drawdown "fuel gauge" (fraction-full /
cycles-remaining / time-remaining), replacing the calendar-days next-full estimate — the fill rate
is non-stationary because the basement is drying. **All three issues have now landed in code:** 01
(estimator), 02 (footer swap, wording confirmed by Rob), 03 (logged tank-full events reach the
hosted curated feed). The work is uncommitted and not yet deployed.

**Autonomy:** ask <!-- ask | go -->

## Threads

<!-- one per live line of work: name — area — one-line state — [artifact](path) -->

- incremental-load — Upkeep — nightly job re-downloads + re-parses ALL R2 CSVs every run (won't
  scale); design for watermark-driven incremental load is written up below and needs Rob to pick
  the shape before build — [workflow](.github/workflows/basement-site.yml)

## Awaiting

<!-- someone else's move: name — area — the evidence wanted and who owns getting it — [artifact](path) -->

- tank-fill-gauge — Build — rebuild complete in code (issues 01/02/03) plus the hosted-build fix
  (un-ignored data/basement_events.csv), full suite 70 green + ruff clean, all uncommitted and
  undeployed. Waiting on Rob to say ship it (commit + deploy), then a live smoke-test that the gauge
  footer renders on https://robjhornby.com/basement/ — [PRD](.scratch/tank-fill-reassessment/PRD.md)

## Parked

<!-- deliberately not now: item — the reason -->

- Alerting / anomaly detection / failure notifications — deferred until the loop has run unattended a while
- Analytical successor work (what the X-Sense sensors actually sense) — the tank-fill slice is now active above; the wider "what do the sensors sense" question is still parked
- Cloudflare hosting consolidation (drop GitHub Pages) — user said "not right now"
