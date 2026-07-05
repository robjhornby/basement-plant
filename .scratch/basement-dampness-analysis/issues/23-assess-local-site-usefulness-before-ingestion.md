# Assess local site usefulness before ingestion

Type: grilling
Status: resolved
Parent: ../map.md
Blocked by: 24

## Question

Is the local CSV-to-static-site workflow useful enough to start the later ingestion phase, or should the roadmap add more local analysis/reporting tickets first?

Use the local-first decision in [Refocus roadmap on local CSV-to-static-site first](21-refocus-roadmap-on-local-csv-to-static-site-first.md), the generated dashboard from [Build weather-inclusive end-to-end prototype](17-build-weather-inclusive-end-to-end-prototype.md), and the dashboard/report boundary from [Design static generator dashboard/report boundary](22-design-static-generator-dashboard-report-boundary.md).

Review the locally generated site output, not just the code shape. Decide whether it is now useful enough for repeated owner-analyst feedback from local CSV files. If not, add the next local tickets and keep ingestion blocked. If yes, unblock [Prototype raw email CSV processing state](19-prototype-raw-email-csv-processing-state.md) as the first ingestion-phase ticket.

## Answer

The local CSV-to-static-site workflow is useful enough to start the later ingestion phase.

Assessment basis:

- `uv run basement` regenerated `build/basement-site/index.html` and `build/basement-site/physics-report.html` from local data, reporting 571,021 sensor rows, 3,384 weather hours, and 2,680 rain readings.
- The dashboard exposes the owner-analyst feedback loop needed before ingestion: latest data freshness, basement RH and absolute humidity, indoor-minus-outdoor absolute humidity, EA rainfall total, cautious hypothesis evidence, daily trends, basement-versus-outdoor moisture, rainfall, raw multi-sensor RH context, and event-bounded period metrics.
- The physics/metrology report is not final, but it is good enough for iteration: it links back to the dashboard, explains the psychrometric model, shares hypothesis evidence and charts, adds event comparability flags, shows an initial uncertainty-budget scaffold, and separates caveats from measurement uncertainty.
- Browser review confirmed both pages render coherently. Visual check artifacts: [dashboard screenshot](../../../output/playwright/basement-dashboard.png) and [physics report screenshot](../../../output/playwright/basement-physics-report.png).

Known limitations are acceptable for this phase rather than blockers: numeric GUM-style intervals are still deferred, the report table is dense, and the analysis remains cautious about placement, airflow, weather-source mismatch, and dehumidifier control-cycle artifacts. Those limits are visible in the generated site, so they can be improved through ordinary local analysis/report iterations while ingestion work begins.

No new local analysis/reporting wayfinder ticket is needed before ingestion. With this ticket resolved, [Prototype raw email CSV processing state](19-prototype-raw-email-csv-processing-state.md) becomes the next unblocked ingestion-phase frontier ticket.
