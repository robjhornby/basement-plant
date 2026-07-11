# Unpublish public physics report

Type: task
Status: resolved
Parent: ../map.md

## Question

Remove the physics/metrology report from the hosted public site while preserving local report
generation for private analysis.

Resolve when:

- Hosted builds stop writing `physics-report.html` to the public site bucket.
- The site Worker no longer serves `/basement/physics-report.html` as a live public object.
- Any existing public R2 `physics-report.html` object is removed as a one-time cleanup.
- The dashboard no longer links to the physics report.
- Local report rendering remains available for private use, with tests updated to reflect the
  public/private boundary.

## Answer

The public site now treats `physics-report.html` as unpublished:

- `render_site_pages()` only returns `index.html`, and the dashboard no longer links to the
  report.
- `render_physics_report_html()` remains available through `render_private_report_pages()` and the
  local CLI flag `--include-private-report`, which writes `physics-report.html` only when requested.
- The hosted GitHub Actions publication step syncs only public site artifacts and has no
  `physics-report.html` steady-state reference.
- Existing `s3://basement-site/physics-report.html` cleanup was performed as a one-time operator
  action and verified with a post-delete `head-object` miss.
- The site Worker no longer maps `/basement/physics-report.html`, so stale R2 objects are not
  served even before cleanup has run.
- README, Cloudflare architecture docs, and Worker docs now describe the dashboard-only public
  publication shape and private local report rendering.

Verification:

- `uv run ruff check .`
- `uv run pyright`
- `uv run pytest`
- `npm test` in `infra/cloudflare/workers/site`
- `npm run check` in `infra/cloudflare/workers/site`
