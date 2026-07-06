# Implement site publication bucket and Worker

Type: task
Status: open
Parent: ../map.md
Blocked by: 37, 38

## Question

Implement the publication path decided in
[Design Cloudflare static publication](30-design-cloudflare-static-publication.md):

- OpenTofu resource for the dedicated site R2 bucket (separate from the ingest pipeline bucket —
  recorded as a reversible assumption).
- `infra/cloudflare/workers/site/` Wrangler project: a GET-only Worker with an R2 binding mapping
  request paths to `index.html`/`physics-report.html` object keys, plus its route.
- Wire the analysis Container job's render output to R2 object writes (alongside the local
  `build/basement-site/` debug path), using R2-scoped S3-compatible credentials only.

Blocked on the Container smoke test proving real R2 reads/writes and on the render/write boundary
refactor so the hosted job can render to strings.
