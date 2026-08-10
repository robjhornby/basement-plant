# Status

## Heading

Frutiger Aero dampness dashboard is shipped and live at https://robjhornby.com/basement/.
The tank-fill predictor has been rebuilt around a moisture-drawdown "fuel gauge" (fraction-full /
cycles-remaining / time-remaining), replacing the calendar-days next-full estimate — the fill rate
is non-stationary because the basement is drying. **All three issues have now landed in code:** 01
(estimator), 02 (footer swap, wording confirmed by Rob), 03 (logged tank-full events reach the
hosted curated feed). Separately, nightly curation is now incremental and R2-native (reads only
CSVs newer than the parquet watermark; the bulk download step is gone). All of this is uncommitted
and not yet deployed.

**Autonomy:** ask <!-- ask | go -->

## Threads

<!-- one per live line of work: name — area — one-line state — [artifact](path) -->

- (none — both live lines are Awaiting Rob's ship decision below)

## Awaiting

<!-- someone else's move: name — area — the evidence wanted and who owns getting it — [artifact](path) -->

- incremental-curation — Upkeep — both issues landed in code: curate-ingested-r2 reads R2
  directly via DuckDB and ingests only CSVs newer than the watermark (issue 01), and the workflow's
  bulk aws-sync download step is deleted (issue 02). Suite 76 green, ruff+pyright clean, verified
  end-to-end on a local fixture; uncommitted + undeployed. Waiting on Rob to ship (commit + deploy),
  then a workflow_dispatch run to confirm the download step is gone and curate reads only recent
  CSVs from R2 with the site still building — [PRD](.scratch/incremental-curation/PRD.md)
- tank-fill-gauge — Build — rebuild complete in code (issues 01/02/03) plus the hosted-build fix
  (un-ignored data/basement_events.csv), full suite green + ruff clean, all uncommitted and
  undeployed. Waiting on Rob to say ship it (commit + deploy), then a live smoke-test that the gauge
  footer renders on https://robjhornby.com/basement/ — [PRD](.scratch/tank-fill-reassessment/PRD.md)

## Parked

<!-- deliberately not now: item — the reason -->

- Alerting / anomaly detection / failure notifications — deferred until the loop has run unattended a while
- Analytical successor work (what the X-Sense sensors actually sense) — the tank-fill slice is now active above; the wider "what do the sensors sense" question is still parked
- Cloudflare hosting consolidation (drop GitHub Pages) — user said "not right now"
