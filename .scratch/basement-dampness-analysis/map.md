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

## Decisions so far

- [Confirm analysis goals and trust boundaries](issues/01-confirm-analysis-goals-and-trust-boundaries.md) — optimize first for a reliable local analysis library with quantitative-but-provisional measurement uncertainty, qualitative caveats, and evidence about steady-state leaking, weather-related leaking, and basement drying.
- [Profile existing sensor data and prototype assumptions](issues/02-profile-existing-sensor-data-and-prototype-assumptions.md) — the CSVs strongly support the inferred basement sensor and evening `2026-07-01` active-drying transition, but gap handling and event labels are required before trusting rebound-rate evidence.
- [Identify sensor models and calibration evidence](issues/03-identify-sensor-models-and-calibration-evidence.md) — all three CSV-producing sensors are X-Sense `STH51` thermohygrometers connected through an `SBS50` base station; no sensor-specific calibration certificates are available, so uncertainty work must use manufacturer specs plus explicit estimates.
- [Confirm intervention and sensor placement timeline](issues/04-confirm-intervention-and-sensor-placement-timeline.md) — `data/basement_events.csv` is now the intervention timeline; use `2026-07-01 21:00` as the physical dehumidifier event, split analysis periods at interventions, and use [Intervention, Room, And Device Context](research/04-intervention-room-and-device-context.md) for room geometry, placement, ventilation, device state, and caveats.

## Fog

- The exact dashboard shape is still foggy until the user confirms audience, privacy posture, key questions, and which analysis outputs deserve publication.
- The database schema and DuckLake partitioning/storage design should wait until the automated email ingestion constraints and desired dashboard queries are clearer; do not let that block an early local weather-inclusive prototype.
- The final physics explainer/report structure should wait until the model scope and uncertainty treatment have been chosen.
- Blog/article topics are promising, especially basement drying physics and uncertainty propagation, but should wait until the project has one or two validated analytical results.
- Alerting, anomaly detection, and automated leak warnings may be useful later, but the acceptable false-positive/false-negative tradeoff is not yet clear.
- Sensor placement strategy, new sensors, or auxiliary measurements may become important after the current dataset and uncertainty budget are understood.
