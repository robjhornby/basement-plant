# Implement shared summary and report page

Type: task
Status: resolved
Parent: ../map.md
Blocked by: 22

## Question

How should the current local static site implementation be refactored so the dashboard and physics/metrology report are generated from one shared analysis summary contract?

Use [Static Generator Dashboard/Report Boundary](../../../prototypes/static-generator-dashboard-report-boundary/README.md) as the target boundary. Implement the smallest production slice that extracts shared summary dataclasses/building logic from `src/basement_analysis/static_site.py`, renders the existing dashboard from that summary without changing its analytical content, and adds a first `physics-report.html` page generated from the same summary.

Keep the work local CSV-to-static-site only. Do not add SES, S3, Gmail forwarding, public hosting, or live dashboard infrastructure. Add focused tests for summary construction and page output so the next wayfinding ticket can assess the local site's usefulness before ingestion work begins.

## Answer

Implemented the first shared-summary production slice.

- Added `src/basement_analysis/summaries.py` with frozen summary/source dataclasses, `build_site_analysis_summary(...)`, shared event-bounded period summaries, metric cards, chart specs, hourly rainfall chart data, hypothesis assessments, caveats, and initial uncertainty budget rows.
- Refactored `src/basement_analysis/static_site.py` so `index.html` renders from `SiteAnalysisSummary` instead of recomputing dashboard values in the renderer.
- Added `physics-report.html`, generated from the same `SiteAnalysisSummary`, with shared hypothesis evidence, report charts, event-bounded period metrics including comparability flags, caveats, and the first uncertainty-budget table.
- Updated `uv run basement`/CLI output to write both `build/basement-site/index.html` and `build/basement-site/physics-report.html`.
- Added focused tests in `tests/test_static_site_summary.py` for summary construction, period splitting, rain chart aggregation, dashboard output, and report output.

Verification:

- `uv run ruff check src tests`
- `uv run pytest`
- `uv run pyright`
- `uv run basement`
