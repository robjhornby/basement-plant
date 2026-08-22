# Status

## Heading

Frutiger Aero dampness dashboard is shipped and live at https://robjhornby.com/basement/.
The R2-backed basement event store and manual GitHub Action entry flow are implemented on local
`main`. Follow-on cleanup now enforces UUIDv7, supplies the promised local update/delete script,
and writes one derived event Parquet per year; live R2 currently contains the verified 12-row
`parquet/events/year=2026/part-00000.parquet`. The bucket-wide semantic layout is inventoried and
proposed. None of these workflow commits is pushed, so the deployed daily workflow can recreate
the legacy event layout and the live Action-to-site smoke test remains outstanding.

**Autonomy:** ask <!-- ask | go -->

## Threads

<!-- one per live line of work: name — area — one-line state — [artifact](path) -->

- (none — implementation and live event cleanup are complete; review/deployment belong to Rob)

## Awaiting

<!-- someone else's move: name — area — the evidence wanted and who owns getting it — [artifact](path) -->

- enter-events-via-github-action — Prove — event cleanup passed a real 147-object full rebuild,
  record equality, live R2 replacement, and direct-R2 static build; final gate 113 tests, Ruff,
  strict Pyright, and diff checks green. Rob owns pushing/deploying before the next daily run, then
  dispatching `Log basement event` to prove upload → `workflow_run` rebuild → refreshed Cloudflare
  static site (and that a failed logger does not run the build job) — [PRD](.scratch/enter-events-via-github-action/PRD.md)
- semantic-r2-object-layout — Shape — Rob to approve or adjust the lifecycle-first `ingest/`,
  `events/`, `datasets/` proposal before a deployment-coupled migration is implemented — [proposal](.scratch/enter-events-via-github-action/R2-OBJECT-LAYOUT.md)

## Parked

<!-- deliberately not now: item — the reason -->

- Alerting / anomaly detection / failure notifications — deferred until the loop has run unattended a while
- Analytical successor work (what the X-Sense sensors actually sense) — the tank-fill slice is now active above; the wider "what do the sensors sense" question is still parked
- Cloudflare hosting consolidation (drop GitHub Pages) — user said "not right now"
