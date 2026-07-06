# Design Cloudflare static publication

Type: task
Status: resolved
Parent: ../map.md
Blocked by: 27, 28, 32

## Question

How should the hosted Cloudflare analysis job publish the generated basement static site after
reading Parquet data from R2 and running the production analysis pipeline?

Compare Cloudflare Pages direct upload, Workers static assets, and writing generated site artifacts
back to R2 behind a Worker route. Preserve the local `uv run basement` workflow as a reproducible
debug path.

## Answer

Research asset:
[Cloudflare static publication design](../research/30-cloudflare-static-publication-design.md).

Publish the generated site by writing `index.html` and `physics-report.html` directly to a
dedicated R2 bucket from the analysis Container job, and serve that bucket through a small
Wrangler-managed Worker route rather than through Cloudflare Pages or Workers static assets. The
Container job already proves this write path: `prototypes/cloudflare-container-duckdb-analysis/prototype.py`
writes generated artifacts to R2 with plain `boto3.put_object` calls using R2-scoped S3-compatible
credentials, no Wrangler or Node.js involved. Extending that path to the real
`render_index_html`/`render_physics_report_html` output means daily publication is just two object
writes, not a `wrangler deploy`/`wrangler pages deploy` invocation.

Cloudflare is steering new projects toward Workers static assets over Pages in 2026 (feature
parity since March 2026, no forced Pages migration deadline), but that platform-level preference
does not apply here: the deciding factor is that both Pages direct upload and Workers static
assets couple every *content* publish to a new *code* deployment, requiring a Wrangler/Node.js
toolchain and an account-scoped API token inside (or alongside) the Python container job. Writing
to R2 keeps content publication and Worker code deployment fully decoupled, keeps the publishing
Worker at "minimal control-plane glue" (a GET-only fetch handler mapping paths to R2 keys), and
narrows the scheduled job's credential footprint to an R2-scoped token instead of an account-wide
one. The site is two small self-contained HTML files (under 400 KB total today, no separate
CSS/JS/image assets), so none of the three options are differentiated by Cloudflare's file-count or
file-size limits, and all three support a future Worker custom domain/route for `robjhornby.com`
equally well.

IaC split: OpenTofu owns the new site R2 bucket (recommended as a bucket dedicated to the site,
separate from the ingest pipeline bucket, for blast-radius isolation) and any future custom-domain
DNS; Wrangler owns the site Worker project (`infra/cloudflare/workers/site/`), its R2 binding, and
its route/deploy; no new narrow script is required for publication under this decision. The local
`uv run basement` workflow is unaffected — it keeps writing HTML to
`build/basement-site/` using the same render functions the hosted path now also calls directly.
Explicit reversible assumptions (dedicated bucket vs. shared prefix, no edge caching yet, hardcoded
filenames vs. a manifest, direct writes vs. a versioned-prefix/manifest publish) are recorded in the
research asset.
