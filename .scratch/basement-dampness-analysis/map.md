# Basement dampness analysis wayfinding map

Label: wayfinder:map

## Notes

This effort is about turning the existing basement thermohygrometer CSV prototype into a physically defensible analysis, automated ingestion pipeline, and publishable dashboard/reporting system.

Standing preferences and constraints:

- Treat `prototypes/basement_dehumidifier/PRD.md` and `prototypes/basement_dehumidifier/NOTES.md` as low-trust prototype artifacts. They are useful evidence of what has been tried, not settled requirements.
- Confirm user-facing claims before hardening them. The user explicitly wants most product, physics, calibration, uncertainty, ingestion, and dashboard assumptions clarified or confirmed.
- Use `/grilling` and `/domain-modeling` whenever a ticket needs user confirmation or sharper terminology.
- Use research tickets for external sources such as X-Sense sensor specifications, calibration/certification evidence, ISO/GUM/MetroloPy material, weather data APIs, DuckDB/DuckLake hosting, and dashboard deployment options.
- Existing local data is in `data/*.csv`; the current prototype infers basement sensor, dehumidifier start, absolute humidity, and dehumidifier cycles heuristically.
- For Python implementation, prefer type hints everywhere, full-name `snake_case` variables, modern Python practices, focused modules, Ruff linting/formatting, and tests around analysis behavior.
- The likely analytical themes are dampness improvement, rain-correlated moisture ingress, possible constant low-rate pipe leak ingress, dehumidifier/fan/sensor intervention effects, and uncertainty propagation into reported values.
- The user is interested in metrology, GUM-style uncertainty analysis, MetroloPy, physics explanations, publishable dashboard output on `robjhornby.com`, and blog/article-grade explanations.
- The user wants an end-to-end prototype again soon, including local weather/outdoor humidity data, because short cycles seeing data and calculations in plots/results should guide later decisions about how deep the physical modelling needs to be.
- Keep early wayfinding agile: ask the user only for high-level facts that materially affect direction now, record obvious or reversible details as assumptions, and defer depth until a later research, prototype, model, or dashboard ticket makes the detail consequential.

## Decisions so far

- [Confirm analysis goals and trust boundaries](issues/01-confirm-analysis-goals-and-trust-boundaries.md) — optimize first for a reliable local analysis library with quantitative-but-provisional measurement uncertainty, qualitative caveats, and evidence about steady-state leaking, weather-related leaking, and basement drying.
- [Profile existing sensor data and prototype assumptions](issues/02-profile-existing-sensor-data-and-prototype-assumptions.md) — the CSVs strongly support the inferred basement sensor and evening `2026-07-01` active-drying transition, but gap handling and event labels are required before trusting rebound-rate evidence.
- [Identify sensor models and calibration evidence](issues/03-identify-sensor-models-and-calibration-evidence.md) — all three CSV-producing sensors are X-Sense `STH51` thermohygrometers connected through an `SBS50` base station; no sensor-specific calibration certificates are available, so uncertainty work must use manufacturer specs plus explicit estimates.
- [Confirm intervention and sensor placement timeline](issues/04-confirm-intervention-and-sensor-placement-timeline.md) — `data/basement_events.csv` is now the intervention timeline; use `2026-07-01 21:00` as the physical dehumidifier event, split analysis periods at interventions, and use [Intervention, Room, And Device Context](research/04-intervention-room-and-device-context.md) for room geometry, placement, ventilation, device state, and caveats.
- [Define dampness and leak hypotheses](issues/05-define-dampness-and-leak-hypotheses.md) — use the canonical first-pass hypothesis set, treat current data as progress toward a future `Dry baseline`, and avoid placement-sensitive inference across sensor moves unless later prototypes prove a measure robust.
- [Establish physics model scope and equations](issues/06-establish-physics-model-scope-and-equations.md) — use a small vapour-pressure-based psychrometric core with absolute humidity as the main metric, optional dew point for explanation, and a mass-balance vocabulary whose physical rates stay caveated until weather, ventilation, and tank-volume data constrain them.
- [Research MetroloPy, GUM, and sensor uncertainty plan](issues/07-research-metrolopy-gum-and-sensor-uncertainty-plan.md) — use a visible GUM-style uncertainty budget, Type B sensor/spec components, approximate 95% coverage intervals for reporting, and MetroloPy at analysis/report boundaries rather than as hidden tabular storage.
- [Prototype uncertainty bounds in report values and charts](issues/08-prototype-uncertainty-bounds-in-report-values-and-charts.md) — show approximate 95% coverage intervals for headline absolute humidity, daily means, and rebound rates; same-sensor changes can be much tighter than absolute levels only when the cancellation assumption is explicit.
- [Decide Caversham weather data source and features](issues/09-decide-caversham-weather-data-source-and-features.md) — use Open-Meteo hourly coordinate weather for outdoor moisture context and Environment Agency station `270397` as the local 15-minute rainfall cross-check.
- [Design rain and pipe leak analysis strategy](issues/10-design-rain-and-pipe-leak-analysis-strategy.md) — distinguish rain-correlated ingress from steady moisture only with intervention-aware absolute-humidity residuals, rain lag features, matched wet/dry comparisons, and cautious "compatible with" language; current data is exploratory only.
- [Clarify email ingestion and hosting constraints](issues/11-clarify-email-ingestion-and-hosting-constraints.md) — use Gmail filtered forwarding to SES inbound in `eu-west-2`, store raw emails privately in S3, process by recoverable batch Python first, provision AWS/Cloudflare with OpenTofu, and publish static generated artifacts before any live dashboard.

## Fog

- The exact dashboard shape is still foggy until the user confirms the key questions, first views, and which analysis outputs deserve publication. The privacy posture now allows public raw measurement plots and derived/caveated results, while keeping raw emails, CSV files, device IDs, exact address/location, and credentials private.
- The database schema and DuckLake partitioning/storage design should wait until desired dashboard queries are clearer; do not let that block an early local weather-inclusive prototype.
- The final physics explainer/report structure should wait until the model scope and uncertainty treatment have been chosen.
- Blog/article topics are promising, especially basement drying physics and uncertainty propagation, but should wait until the project has one or two validated analytical results.
- Alerting, anomaly detection, and automated leak warnings may be useful later, but the acceptable false-positive/false-negative tradeoff is not yet clear.
- Sensor placement strategy, new sensors, or auxiliary measurements may become important after the current dataset and uncertainty budget are understood.
