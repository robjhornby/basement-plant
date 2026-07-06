# Refactor static site render/write boundary

Type: task
Status: resolved
Parent: ../map.md

## Question

Should `build_static_site` split "render HTML strings" from "write to a `Path`" cleanly enough that
the hosted container job can call the same render functions and hand the strings to R2 writes,
without disturbing the local `uv run basement` filesystem behavior?

Surfaced by [Design Cloudflare static publication](30-design-cloudflare-static-publication.md):
the chosen publication path has the analysis Container job upload rendered
`index.html`/`physics-report.html` directly to the site R2 bucket, so rendering must be callable
without a filesystem destination.

## Answer

Yes. Split `basement_analysis.static_site.build_static_site`'s final write step into two small
functions, without touching the existing `render_index_html`/`render_physics_report_html` pure
renderers (they already took only a `SiteAnalysisSummary` and returned a string, so no change was
needed there):

- `render_site_pages(summary: SiteAnalysisSummary) -> dict[str, str]` — a pure function returning a
  relative-object-path -> rendered-HTML mapping, `{"index.html": ..., "physics-report.html": ...}`.
  This is the seam a future hosted Container job calls directly, handing each mapping entry to an
  R2 `put_object` keyed by the same relative path, with no filesystem involved.
- `write_site_pages(pages: Mapping[str, str], output_dir: Path) -> dict[str, Path]` — a thin writer
  that creates `output_dir` (and any nested parent directories implied by a relative path),
  `write_text`s each entry, and returns a relative-path -> written-`Path` mapping.

`build_static_site` now ends with `written_paths = write_site_pages(render_site_pages(summary),
output_dir)` and builds `BuildResult` from `written_paths["index.html"]` /
`written_paths["physics-report.html"]` instead of constructing `Path`s and calling
`.write_text(...)` inline. Curated-dataset Parquet writing (`write_curated_dataset`) was already a
separate concern from HTML page writing and is unchanged.

Files changed:
- `src/basement_analysis/static_site.py` — added `render_site_pages`/`write_site_pages`, refactored
  `build_static_site`'s write step to use them, added `Mapping` to the `collections.abc` import.
- `tests/test_static_site_summary.py` — added `test_render_site_pages_returns_relative_path_to_html_mapping`
  (mapping keys/values match the existing pure renderers) and
  `test_write_site_pages_persists_mapping_under_output_dir` (writer creates nested parent dirs and
  persists exact content, keyed by relative path). Existing `tests/test_curated_dataset.py` coverage
  of `build_static_site` end-to-end filesystem output was left as-is and still passes.

Verification:
- `uv run ruff format --check .` — pass (11 files already formatted).
- `uv run ruff check .` — pass (all checks passed).
- `uv run pyright` — pass (0 errors, 0 warnings, 0 informations).
- `uv run pytest` — pass (9 passed).
- Byte-identical local build check: stashed the refactor, ran
  `uv run basement --reuse-curated --curated-data-dir build/basement-site/curated-data
  --output-dir <scratch>/site-before` against the pre-refactor code (no network calls, reusing the
  existing curated Parquet dataset), restored the refactor, ran the same command into
  `<scratch>/site-after`, and `diff -rq site-before site-after` reported no differences —
  `index.html` and `physics-report.html` are byte-identical before and after the refactor.

No new dependencies, no R2/boto3/cloud code added, `infra/cloudflare/` and other `.scratch` files
untouched.
