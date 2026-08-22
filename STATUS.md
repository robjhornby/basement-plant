# Status

## Heading

Frutiger Aero dampness dashboard is shipped and live at https://robjhornby.com/basement/.
The R2-backed basement event store and manual GitHub Action entry flow are implemented and
committed on local `main`: all six PRD tickets are resolved, the 12 legacy events were migrated
exactly once and verified live in R2, and the repository no longer carries the CSV. The workflow
commits have not been pushed/deployed, so the one-off UTC Parquet rebuild and live Action-to-site
smoke test have not run yet.

**Autonomy:** ask <!-- ask | go -->

## Threads

<!-- one per live line of work: name — area — one-line state — [artifact](path) -->

- (none — implementation is complete; rollout evidence belongs to Rob below)

## Awaiting

<!-- someone else's move: name — area — the evidence wanted and who owns getting it — [artifact](path) -->

- enter-events-via-github-action — Prove — six tickets committed on local `main`; live R2 contains
  the 12 verified migrated events; final gate 108 tests, Ruff, strict Pyright, YAML, and diff checks
  green. Rob owns pushing/deploying, then running `curate-ingested-r2 --rebuild-all` once and
  dispatching `Log basement event` to prove successful upload → `workflow_run` rebuild → refreshed
  live site (and that a failed logger does not run the build job) — [PRD](.scratch/enter-events-via-github-action/PRD.md)

## Parked

<!-- deliberately not now: item — the reason -->

- Alerting / anomaly detection / failure notifications — deferred until the loop has run unattended a while
- Analytical successor work (what the X-Sense sensors actually sense) — the tank-fill slice is now active above; the wider "what do the sensors sense" question is still parked
- Cloudflare hosting consolidation (drop GitHub Pages) — user said "not right now"
