# Status

## Heading

Frutiger Aero dampness dashboard is shipped and live at https://robjhornby.com/basement/.
The tank-fill predictor is being rebuilt around a moisture-drawdown "fuel gauge" (fraction-full /
cycles-remaining / time-remaining), replacing the calendar-days next-full estimate — the fill rate
is non-stationary because the basement is drying. Analysis is done and the build is ticketed;
issues 01–03 are ready for implementation sessions.

**Autonomy:** ask <!-- ask | go -->

## Threads

<!-- one per live line of work: name — area — one-line state — [artifact](path) -->

- tank-fill-gauge — Build — analysis done (gauge beats calendar-days, backtest MAE 1.27 vs 1.75 d);
  workbench script written; PRD + issues 01 (estimator) / 02 (footer) / 03 (events→hosted feed)
  ready — [PRD](.scratch/tank-fill-reassessment/PRD.md)

## Parked

<!-- deliberately not now: item — the reason -->

- Alerting / anomaly detection / failure notifications — deferred until the loop has run unattended a while
- Analytical successor work (what the X-Sense sensors actually sense) — the tank-fill slice is now active above; the wider "what do the sensors sense" question is still parked
- Cloudflare hosting consolidation (drop GitHub Pages) — user said "not right now"
