# Static site assets one-off generation and test-suite cleanup

Labels: ready-for-agent

## Problem Statement

Two defects surfaced during review of the dehumidifier next-full estimate implementation
(2026-07-18):

1. `build_static_site` re-derives all 8 Frutiger Aero binary assets (0.56 MB total) from the
   committed source art on every run — resizing the tall scene to 3 widths and re-encoding
   every WEBP with `method=6` — even though the derived files are deterministic functions of
   static source images and depend on no data. This wastes ~11 s of CPU in every daily site
   build and is the sole cause of the four slowest tests in the suite (~11 s each, ~44 s of a
   ~45 s suite run).
2. The tank-estimator snapshot validation shipped as a permanent pytest test
   (`tests/test_tank_estimator_snapshot_validation.py`) although the PRD said validation is
   one-off, not CI. It also asserts extraction-cycle counts against a superseded exploration
   table (91/135/149 ± 8) and carries a comment referring to "the owner's table" — out-of-band
   context that must never appear in code.

## Solution

Generate the Frutiger Aero derived assets once with a one-off script that stays in the
codebase, commit the derived files as static repo content, and make `build_static_site` copy
them into the output directory instead of rendering them. Delete the two tests that exist only
to exercise image generation. Convert the tank-estimator snapshot validation into a one-off
script that prints the inferred timeline, with no cycle-count assertions, and delete the pytest
file. The two end-to-end pipeline tests in `tests/test_curated_dataset.py` are kept unchanged;
they become fast automatically once the build stops encoding images.

## Decisions (owner-confirmed 2026-07-18)

- The implemented estimator is now the reference: the spec-verbatim thresholds produce
  86/130/142 extraction cycles on the July snapshot, and the original exploration counts
  (91/135/149) are superseded and must not be asserted anywhere. Event timestamps and fill
  durations already reproduce within minutes and need no re-validation in CI.
- Code comments and docstrings must describe only the current state of the codebase,
  understandable to any future maintainer. No references to "the owner", conversations,
  exploration sessions, or other out-of-band context anywhere in code.
- Asset generation was a one-off task. The generation code remains in the codebase as a script
  so the derived files can be regenerated if the source art changes, but it is not part of
  `build_static_site`.
- This work is a separate change from the dehumidifier next-full estimate branch. The staged
  tank work stays reviewable against its own PRD; land this either as its own commit(s) on top
  or as its own branch, without entangling the two diffs.

## Implementation Decisions

### Asset pipeline restructure

- Add a `scripts/` directory (plain `uv run` scripts, not `[project.scripts]` entries).
- Move `render_frutiger_aero_assets`, `render_site_assets`, and their image helpers
  (`webp_bytes`, `resized_to_width`, `horizontally_seamless`, `key_product_shot`,
  `unblend_white`, crop/overlap constants — everything whose only consumer is asset
  generation) out of `src/basement_analysis/static_site.py` into
  `scripts/generate_frutiger_aero_assets.py`. The script renders the assets and writes them,
  including `manifest.json`, to the committed static location.
- Commit the 8 derived files (7 WEBPs + `manifest.json`) under
  `src/basement_analysis/site_assets/frutiger_aero/derived/assets/frutiger-aero/`, preserving
  the published relative paths (`assets/frutiger-aero/…`). Source art stays where it is.
- `build_static_site`'s render/write phases copy the committed derived tree into
  `output_dir` byte-for-byte, preserving relative paths. Content types and the
  `public, max-age=600, no-transform` cache-control behaviour of the workflow's sync steps
  are unchanged; the `.github/workflows/basement-site.yml` sync commands need no edits
  because the output-directory layout is identical.
- `write_site_assets` survives only if the copy step still needs it; delete any code whose
  only remaining consumer was build-time rendering. `Image`/PIL imports leave
  `static_site.py` entirely.

### Tank snapshot validation restructure

- Delete `tests/test_tank_estimator_snapshot_validation.py`.
- Add `scripts/print_tank_timeline.py`: loads the curated snapshot from
  `local/r2-parquet-snapshot` (error message, not a skip, when absent), runs
  `estimate_tank_history`, and prints the fill intervals with durations and cycle counts, the
  tank-emptied events, the state, and the footer text — the same report the deleted test
  printed. No assertions of any kind; it is a human-run inspection tool.
- No code anywhere asserts extraction-cycle counts against fixed expected values.

### Comment hygiene (applies to the staged tank diff before it lands)

- Remove the comment block in the deleted validation test as part of its deletion; audit the
  rest of the staged tank diff for any remaining out-of-band references (none are known in
  `tank_estimator.py` itself, whose docstrings describe thresholds and model only).

## Testing Decisions

- Delete `test_render_site_assets_derives_production_frutiger_aero_manifest` and
  `test_write_site_assets_persists_generated_binary_assets` from
  `tests/test_static_site_summary.py`; they test one-off generation and are not replaced.
- Keep `test_static_site_builds_from_curated_parquet_path` and
  `test_build_static_site_can_write_private_report_for_local_analysis` unchanged; after the
  restructure each must run in well under 1 s. Their existing assertions must keep passing —
  they are the proof the copy step works.
- If those two tests do not already assert that a derived asset lands in the output directory,
  extend one of them with a single existence check for
  `assets/frutiger-aero/manifest.json` in the built site.
- Full-suite target after this change: `uv run pytest` completes in ~2 s (from ~45 s).
- `uv run pytest`, `uv run ruff check .`, `uv run pyright` all pass.

## Out of Scope

- Any change to the published site's appearance, asset bytes, URLs, or caching headers.
- Any change to the estimator's detection thresholds, model, footer text, or the rest of the
  staged dehumidifier work.
- Workflow (`basement-site.yml`) edits.
- Re-deriving or re-tuning ground truth for the estimator; predicted-vs-actual tracking.

## Further Notes

- Origin: review session 2026-07-18. The suite slowness predated the dehumidifier branch
  (verified by timing HEAD in a clean worktree: same four tests, same ~11 s each); the tank
  tests themselves all run in under 1 s and touch no network — the snapshot loader takes the
  local-`Path` branch, so R2 code is unreachable from tests.
