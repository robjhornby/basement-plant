# Design static generator dashboard/report boundary

Type: prototype
Status: open
Parent: ../map.md
Blocked by: 17

## Question

How should the local static generator structure the dashboard/report outputs and shared analysis summary objects so the dense dashboard and explanatory physics/metrology report do not duplicate calculations?

Use the real shape exposed by [Build weather-inclusive end-to-end prototype](17-build-weather-inclusive-end-to-end-prototype.md) and the report structure from [Physics And Metrology Report Mock](../prototypes/15-physics-and-metrology-report-mock.md). Decide which values are calculated once in the analysis layer, which are presentation-only, and how generated dashboard pages, report pages, metadata, caveats, and appendices should share the same summary data.
