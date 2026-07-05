# Design static generator dashboard/report boundary

Type: prototype
Status: resolved
Parent: ../map.md
Blocked by: 17

## Question

How should the local static generator structure the dashboard/report outputs and shared analysis summary objects so the dense dashboard and explanatory physics/metrology report do not duplicate calculations?

Use the real shape exposed by [Build weather-inclusive end-to-end prototype](17-build-weather-inclusive-end-to-end-prototype.md), especially `src/basement_analysis/static_site.py`, `src/basement_analysis/cli.py`, `README.md`, and the generated local output at `build/basement-site/index.html` after running `uv run basement`. Also use the report structure from [Physics And Metrology Report Mock](../prototypes/15-physics-and-metrology-report-mock.md).

Decide which values are calculated once in the analysis layer, which are presentation-only, and how generated dashboard pages, report pages, metadata, caveats, and appendices should share the same summary data. Produce a concrete boundary proposal that is detailed enough for the next implementation ticket: likely shared summary dataclasses or typed dictionaries, generator responsibilities, file/page outputs, and where uncertainty/caveat text should be assembled.

## Answer

Prototype asset: [Static Generator Dashboard/Report Boundary](../prototypes/22-static-generator-dashboard-report-boundary.md)

The local static generator should use one shared `SiteAnalysisSummary` contract for both the dense dashboard and the explanatory physics/metrology report. The analysis layer should calculate sensor/weather/rain joins, psychrometric values, event-bounded period summaries, chart series, caveat ids, uncertainty budget rows, and hypothesis assessments once. Dashboard and report renderers should only choose layout, page density, chart styling, caveat verbosity, and appendix expansion.

The first implementation should extract shared frozen dataclasses and `build_site_analysis_summary(...)`, render the existing `index.html` from that summary without changing its analytical content, and add `physics-report.html` from the same summary using the earlier physics/metrology report mock. JSON export can be optional/debug-first until publication or snapshot testing needs it.

New ticket added: [Implement shared summary and report page](24-implement-shared-summary-and-report-page.md). [Assess local site usefulness before ingestion](23-assess-local-site-usefulness-before-ingestion.md) now waits for that implementation, because the local site should be assessed after the report page exists rather than after the boundary proposal alone.
