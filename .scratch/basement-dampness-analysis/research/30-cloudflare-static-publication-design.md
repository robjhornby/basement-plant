# Cloudflare static publication design

Research asset for
[Design Cloudflare static publication](../issues/30-design-cloudflare-static-publication.md).

## Question

How should the hosted Cloudflare analysis job publish the generated basement static site after
reading Parquet from R2 and running the production analysis pipeline? Compare Cloudflare Pages
direct upload, Workers static assets, and writing generated site artifacts to R2 served behind a
Worker route, while keeping `uv run basement` as the reproducible local debug path.

## What gets published today

`src/basement_analysis/static_site.py::build_static_site` writes exactly two self-contained files
to `output_dir`, with no separate CSS/JS/image assets (charts are inline SVG, styles are inline
`<style>`):

- `index.html` — 258,661 bytes in the current local build.
- `physics-report.html` — 96,380 bytes in the current local build.

Total published payload is well under 400 KB today and is unlikely to grow past a handful of small
HTML files even after report iteration. `build/basement-site/curated-data` and `build/basement-site/cache`
are build-time inputs, not publication artifacts.

The `prototypes/cloudflare-container-duckdb-analysis/prototype.py` container job already proves the
relevant shape end to end: it runs DuckDB against R2-hosted partitioned Parquet through the
S3-compatible endpoint, renders representative HTML/JSON in memory, and — in `--mode r2` — writes
those artifacts to R2 with plain `boto3.put_object` calls using R2 API token credentials (access
key ID / secret access key), no Wrangler or Node.js involved. This is the same mechanism the
production container job would use to write the real `index.html` / `physics-report.html`.

## Standing constraints from the map

- OpenTofu owns durable resources; Wrangler owns each deployable Worker/Container project
  (bindings, deploys, secrets); scripts stay narrow (imports, smoke tests, Pages uploads, provider
  gaps) — [issue 31](../issues/31-choose-cloudflare-infrastructure-as-code-approach.md).
- No database by default; prefer deterministic R2 keys and small manifests.
- Minimal Worker control-plane glue; domain analysis stays in Python/`uv` — [issue 34](../issues/34-grill-hosted-processing-stack-decision.md).
- The Cloudflare Container is the provisional hosted analysis compute surface; it already
  demonstrates writing generated artifacts to R2 — [issue 32](../issues/32-prototype-cloudflare-container-duckdb-analysis-job.md).
- `uv run basement` must remain a reproducible local debug path, unaffected by hosted publication
  mechanics.

## Current Cloudflare status (verified July 2026)

- **Pages vs Workers static assets**: Cloudflare now recommends Workers with static assets for new
  projects — as of March 2026 Workers has feature parity with Pages for static assets, SSR, and
  custom domains, and a single Worker can serve both static files and dynamic logic from one
  `wrangler deploy`. Existing Pages projects remain fully supported with no forced migration
  deadline, but Pages is the legacy path for new work.
  ([Migrate from Pages to Workers](https://developers.cloudflare.com/workers/static-assets/migration-guides/migrate-from-pages/),
  [Static Assets](https://developers.cloudflare.com/workers/static-assets/))
- **Workers static assets deploy flow**: assets live in a directory declared in
  `wrangler.jsonc`/`wrangler.toml`; `wrangler deploy` uploads the Worker script and the assets
  directory together as one versioned deployment. Paid accounts allow up to 100,000 static assets
  per Worker version (Wrangler ≥ 4.34.0), 20,000 on the Free plan; the per-file limit is 25 MiB
  regardless of plan. Assets are edge-cached automatically with tiered caching.
  ([Increased static asset limits](https://developers.cloudflare.com/changelog/2025-09-02-increased-static-asset-limits/),
  [Static Assets](https://developers.cloudflare.com/workers/static-assets/))
- **Pages direct upload**: `wrangler pages deploy <dir> --project-name <name>` still works
  headlessly from any machine with a `CLOUDFLARE_API_TOKEN` (Pages:Edit) and
  `CLOUDFLARE_ACCOUNT_ID` set, no git connection required.
- **R2 behind a Worker**: a Worker with an R2 bucket binding reads/writes objects via
  `env.BUCKET.get()/put()` regardless of the bucket's public/private setting — the binding is a
  programmatic grant, separate from public HTTP exposure. Public HTTP exposure (custom domain or
  `r2.dev`) is only needed if something other than a Worker binding must reach the bucket directly.
  A Custom Domain attached to a bucket (or to the Worker route) enables Cloudflare's normal cache,
  WAF, and single-file purge-by-URL tooling.
  ([Public buckets](https://developers.cloudflare.com/r2/buckets/public-buckets/),
  [Purge by single file](https://developers.cloudflare.com/cache/how-to/purge-cache/purge-by-single-file/))

## Comparison

| Dimension | (a) Pages direct upload | (b) Workers static assets | (c) R2 objects behind a Worker route |
|---|---|---|---|
| Cloudflare direction (2026) | Legacy path, still supported, no new investment recommended | Recommended default for new static/SSR projects | Not a "publication product" — plain building block (R2 + Worker), always supported |
| Publish mechanism | `wrangler pages deploy` (or API) — new Pages deployment per publish | `wrangler deploy` — new Worker version per publish | Plain object writes (`PUT`) to R2, already proven by the container prototype's `publish_to_r2` |
| Runtime dependency to publish | Wrangler/Node.js CLI + Pages-scoped API token | Wrangler/Node.js CLI + Workers-scoped API token | None beyond the S3-compatible client (`boto3`) already used inside the Python container job |
| Fits "publish from inside a container job" | Poorly — needs a second Node/Wrangler step outside the Python job, or bundling Node into the analysis image | Poorly — same problem, plus couples content publish to a Worker *code* deployment | Well — the container job's existing Python/`boto3` R2 write path *is* the publish step, no second toolchain |
| Decouples content update from Worker code deploy | No — each publish is a new Pages deployment | No — each publish is a new Worker version | Yes — Worker code (rarely changes) deploys once via Wrangler; content (daily) is just new R2 objects |
| File count/size fit for this site | Fine (2 files, <400 KB) | Fine (limits are 20k–100k files, 25 MiB/file — far above need) | Fine (no platform-imposed publication limits, ordinary R2 object limits apply) |
| Caching | CDN-cached automatically | CDN-cached automatically, tiered | Cache is opt-in via Custom Domain / Cache-Control from the Worker; simplest to start uncached given very low traffic |
| Auth surface for the scheduled job | Account-level API token with Pages:Edit | Account-level API token with Workers Scripts:Edit | R2-scoped API token (bucket-level S3 credentials) — narrower blast radius than an account-wide token |
| Custom domain path (`robjhornby.com` later) | Pages-specific custom domain flow | Workers custom domain/route (unified model) | Worker custom domain/route (same unified model as (b)) — no discriminator vs (b) |
| Consistency with map's IaC split | Would need a `pages.tf`/script per issue 31's "narrow scripts... Pages uploads" carve-out | Wrangler-owned Worker+assets project; reasonable fit but ties content to deploys | Cleanest fit: OpenTofu owns the R2 bucket, Wrangler owns the (small, static) site Worker project; no bespoke script needed at all |
| Local debug path impact | None — local `uv run basement` unaffected either way | None | None |

## Decision

**Use option (c): the analysis container writes the generated `index.html` and
`physics-report.html` directly to a dedicated R2 bucket, and a small Wrangler-managed Worker serves
that bucket on its route/custom domain.**

Reasons, in order of weight:

1. **It reuses proven, already-built plumbing.** The Container prototype
   ([issue 32](../issues/32-prototype-cloudflare-container-duckdb-analysis-job.md)) already writes
   generated artifacts to R2 with plain S3-compatible `put_object` calls from Python. Publishing is
   then just "write these two HTML strings to two more keys" — no new tool, language runtime, or
   deploy mechanism has to be added to the container image.
2. **It cleanly decouples code deploys from content publishes**, which both Pages and Workers
   static assets conflate (every content update is a new Pages/Worker deployment). The map's IaC
   split already separates "durable resources" (OpenTofu), "deployable code" (Wrangler), and
   "narrow scripts" — daily content publication is not code deployment and should not need
   Wrangler, Node.js, or a Cloudflare account-wide API token to run. The R2-scoped API token needed
   for object writes is also a narrower secret than a Pages/Workers deploy token, which is a nice
   side benefit for the scheduled job's credential footprint.
3. **It keeps the Worker at "minimal control-plane glue,"** consistent with the standing
   preference in `map.md`. The publication Worker is a GET-only fetch handler that maps a path to
   an R2 key and streams the object back with a content type and cache header — a handful of
   lines, deployed once and rarely touched, independent of how often the site content changes.
4. **Cloudflare's 2026 push toward Workers static assets is a reason to prefer Workers over Pages
   in general, but it does not favor option (b) here**, because the discriminator in this decision
   is *how a headless container job publishes content*, not which platform renders static files
   fastest. All three options are far inside Cloudflare's file-count/size limits for a two-file,
   <400 KB site, so platform limits do not differentiate them.
5. **Custom domain routing for the eventual `robjhornby.com` publication is a non-issue either
   way** — Worker custom domains/routes now have the same unified model Pages uses, so choosing (c)
   does not foreclose or complicate that later step.

Rejected:

- **(a) Pages direct upload** — still fully supported, and the map already anticipated it as a
  possible narrow-script use in issue 31, but it adds a Wrangler/Node deploy step per publish for
  no benefit over (c), and Cloudflare is steering new work away from Pages regardless.
- **(b) Workers static assets** — the modern, Cloudflare-recommended default for *git-connected or
  CI-built* static sites, but it has the same "content publish = code deploy" coupling as Pages and
  the same Wrangler/Node/account-token dependency inside a Python container job that (c) avoids
  entirely. Revisit this if the publication Worker ever needs to grow real request-time logic
  beyond serving R2 objects (e.g., auth, redirects, A/B content) where bundling assets with Worker
  code becomes genuinely convenient.

## Publish flow

```
uv run basement (local)              Hosted (Cloudflare Container job, same Python code)
------------------------             ---------------------------------------------------
render_index_html(summary)           render_index_html(summary)
render_physics_report_html(summary)  render_physics_report_html(summary)
write to build/basement-site/*.html  put_object to R2 site bucket: site/index.html,
                                      site/physics-report.html (R2-scoped S3 credentials)
```

- **Container job (Python/`uv`/DuckDB, triggered by the `analysis-container` Worker on its
  schedule)**: reads curated Parquet from the pipeline R2 bucket, runs the existing analysis code,
  calls the *same* `render_index_html` / `render_physics_report_html` functions
  `static_site.py` already exposes, and writes the resulting strings straight to the site R2
  bucket with `boto3.put_object` (extending the pattern already proven in
  `prototypes/cloudflare-container-duckdb-analysis/prototype.py`'s `publish_to_r2`). This needs a
  small refactor in `static_site.py` to split "render to string" (already separate) from
  "write render output to a `Path`" so the container job can call the render functions directly and
  hand the strings to R2 instead of the filesystem — `build_static_site` keeps its current
  filesystem-writing behavior for the local path unchanged.
- **Site Worker (Wrangler-managed, `infra/cloudflare/workers/site/`)**: a small `fetch` handler
  bound to the site R2 bucket. Maps `/` → `site/index.html`, `/physics-report.html` →
  `site/physics-report.html`, returns 404 otherwise, and sets `Content-Type` from the object's
  stored metadata (or a static lookup by extension). Deployed via `wrangler deploy` only when this
  Worker's own code changes — not on every content publish.
- **Local `uv run basement`**: unchanged. It still writes `index.html` / `physics-report.html` to
  `build/basement-site/` for local debugging, using the same render functions the hosted path now
  also calls directly.

## IaC split

- **OpenTofu (`infra/cloudflare/tofu/`)**: the site R2 bucket resource (recommend a dedicated
  bucket, e.g. `basement-site`, separate from the ingest pipeline bucket — see assumptions below),
  DNS records / custom domain attachment for the site Worker's public route, and (later) the
  `robjhornby.com` DNS delegation when that becomes concrete.
- **Wrangler (`infra/cloudflare/workers/site/`)**: the site Worker's code, its R2 bucket binding,
  its route/custom domain attachment, and its own deploy. Also: the `analysis-container` Worker
  project continues to own the R2 API token/secrets that the container job uses for both reading
  pipeline Parquet and writing site objects.
- **Scripts (`infra/cloudflare/scripts/`)**: none required for publication under this decision —
  this is the concrete case where avoiding Pages/Workers-assets deploys also avoids needing the
  "Pages direct upload" narrow-script carve-out from issue 31. If a future need re-introduces Pages
  (e.g., a marketing-style front end with a build step), that script slot is still available.

## Assumptions (reversible)

- **Dedicated `basement-site` R2 bucket, separate from the ingest pipeline bucket.** Reversible:
  could instead use a `site/` prefix inside the existing pipeline bucket. Kept separate here so a
  bug in the public-facing Worker's key-mapping logic cannot expose raw email or CSV objects from
  the ingest bucket — narrower blast radius for negligible extra cost (one more R2 bucket).
- **No edge caching configured on the site Worker initially** (no Custom Domain cache rules, no
  explicit `Cache-Control`, or a short `max-age`). Reversible: traffic is expected to be the owner
  plus occasional shared links, so cache-miss latency for two small HTML files is not a concern yet.
  Add a Custom Domain + purge-by-URL only if latency or R2 request volume becomes a real cost/perf
  issue.
- **The site Worker serves only the two known filenames** (`index.html`,
  `physics-report.html`) plus a `/` → `index.html` redirect, not a general-purpose static file
  server. Reversible: generalize to a prefix-listing or manifest-driven router if the site grows
  more pages; a manifest object (matching the "small manifest objects" pattern already used for
  ingest) is the natural next step rather than hardcoding filenames.
- **The container job writes site objects directly** rather than going through a Queue, Workflow,
  or the site Worker itself. Reversible: if atomicity across multiple files matters later (e.g.
  avoiding a reader seeing a new `index.html` referencing an unwritten new asset), switch to
  writing a versioned prefix (`site/<content-hash>/...`) plus a manifest pointer object, and have
  the Worker resolve "current" through the manifest — deferred because both HTML files are
  currently self-contained with no cross-file dependency.
- **`robjhornby.com` publication is out of scope for this decision** beyond noting that a Worker
  custom domain/route satisfies it equally well under any of the three options; the actual domain
  wiring is deferred to whenever that becomes a concrete, prioritized step.

## Sources

- [Migrate from Pages to Workers](https://developers.cloudflare.com/workers/static-assets/migration-guides/migrate-from-pages/)
- [Static Assets · Cloudflare Workers docs](https://developers.cloudflare.com/workers/static-assets/)
- [Increased static asset limits for Workers · Changelog](https://developers.cloudflare.com/changelog/2025-09-02-increased-static-asset-limits/)
- [Public buckets · Cloudflare R2 docs](https://developers.cloudflare.com/r2/buckets/public-buckets/)
- [Purge by single-file · Cloudflare Cache docs](https://developers.cloudflare.com/cache/how-to/purge-cache/purge-by-single-file/)
- [Enable cache in an R2 bucket · Cloudflare Cache docs](https://developers.cloudflare.com/cache/interaction-cloudflare-products/r2/)
- `prototypes/cloudflare-container-duckdb-analysis/prototype.py` (existing `publish_to_r2` R2 write
  path, verified locally in issue 32).
