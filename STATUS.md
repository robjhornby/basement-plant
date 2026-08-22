# Status

## Heading

Frutiger Aero dampness dashboard is shipped and live at https://robjhornby.com/basement/.
The event Action-to-site flow and semantic R2 migration are complete. The deployed Email Worker
writes `ingest/`, the production workflow reads it and publishes `datasets/`, and workflow run
32591218744 rebuilt and published the site successfully from `main`. Live R2 now contains only 253
ingest objects, 14 canonical event revisions, and 32 analytical datasets; a post-deletion build
verified 784,858 sensor rows, 4,583 weather hours, 7,150 rainfall readings, and 14 current events.

**Autonomy:** ask <!-- ask | go -->

## Threads

<!-- one per live line of work: name — area — one-line state — [artifact](path) -->

- (none — semantic layout implementation, deployment, migration, and cleanup are complete)

## Awaiting

<!-- someone else's move: name — area — the evidence wanted and who owns getting it — [artifact](path) -->

- (none)

## Parked

<!-- deliberately not now: item — the reason -->

- Alerting / anomaly detection / failure notifications — deferred until the loop has run unattended a while
- Analytical successor work (what the X-Sense sensors actually sense) — the tank-fill slice is now active above; the wider "what do the sensors sense" question is still parked
- Cloudflare hosting consolidation (drop GitHub Pages) — user said "not right now"
