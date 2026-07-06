# Implement site publication bucket and Worker

Type: task
Status: resolved
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

## Answer

Implemented the publication path, adapted to the current map decision that hosted analysis runs in
GitHub Actions rather than a Cloudflare Container:

- OpenTofu now declares a dedicated private `basement-site` R2 bucket separate from
  `basement-pipeline` (`infra/cloudflare/tofu/r2.tf`, `site_bucket_name` variable, and
  `site_bucket_name` output).
- OpenTofu now declares a proxied `basement.robjhornby.com` placeholder DNS record so the
  Wrangler-managed Worker route can receive traffic through Cloudflare.
- Added `infra/cloudflare/workers/site/`, a Wrangler-managed TypeScript Worker bound to
  `SITE_BUCKET = basement-site`, routed at `basement.robjhornby.com/*`, serving only:
  `/` and `/index.html` -> `index.html`; `/physics-report.html` -> `physics-report.html`.
  Unknown paths return `404`; non-GET requests return `405`.
- Updated `.github/workflows/basement-site.yml` so the analysis runner still reads curated Parquet
  from `s3://$R2_BUCKET/parquet`, but publishes rendered HTML to `$R2_SITE_BUCKET` with Wrangler
  rather than the interim `s3://$R2_BUCKET/site/basement-site` prefix.
- Updated Cloudflare docs under `infra/cloudflare/` and
  `docs/architecture/cloudflare-email-r2-static-site.md` to record the split bucket/publication
  shape and the GitHub Actions runner replacing the Container path.

Operational facts later tickets depend on:

- New GitHub Actions secrets required: `R2_SITE_BUCKET=basement-site` and `CLOUDFLARE_API_TOKEN`
  for Wrangler R2 object uploads.
- The workflow's existing R2 S3 credentials only need to read `basement-pipeline`; the current
  key is intentionally not widened to write the public site bucket.
- Apply/deploy order: `tofu apply` to create the site bucket and DNS record, then
  `npm install && npm run types && npm run deploy` from `infra/cloudflare/workers/site/`.
- Verification passed: `uv run ruff check`, `uv run pyright`, `uv run pytest`,
  `tofu fmt -check -recursive && tofu validate`, `npm run check`, `npm test`,
  and `npx wrangler deploy --dry-run` for the site Worker.

Deployment facts:

- Applied OpenTofu with `create_email_ingest_rule=true`; created `basement-site` and the proxied
  `basement.robjhornby.com` DNS placeholder without changing the existing email ingest rule.
- Deployed the site Worker to `basement.robjhornby.com/*`; current live Worker version after the
  HEAD-support fix is `763a4097-1071-4eb5-ae55-f3dd1ba5a84c`.
- Uploaded the current local `build/basement-site/index.html` and `physics-report.html` into
  `basement-site` using `wrangler r2 object put`.
- Set GitHub Actions secrets `R2_SITE_BUCKET=basement-site` and `CLOUDFLARE_API_TOKEN` in
  `robjhornby/basement-plant`.
- Pushed commit `742285a` (`Publish basement site via R2 Worker`) to `main`; dispatched GitHub
  Actions run `28831151415` completed successfully in 43 s using the new Wrangler publish path.
- Live smoke tests passed: `https://basement.robjhornby.com/` and
  `https://basement.robjhornby.com/physics-report.html` return `200` with the expected page
  content; `HEAD` returns `200`; non-GET/HEAD methods return `405`.
