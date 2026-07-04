# Research MetroloPy, GUM, and sensor uncertainty plan

Type: research
Status: resolved
Parent: ../map.md
Blocked by: 03, 06

## Question

How should measurement uncertainty be represented and propagated for this project using MetroloPy and GUM-style principles?

Use primary or authoritative sources where possible. Cover sensor temperature/RH uncertainty, calibration evidence or absence, resolution, drift, correlation between measurements, uncertainty propagation through absolute humidity/dew-point calculations, coverage factor or 95% interval reporting, and how MetroloPy can encode the calculation without hiding important assumptions.

## Answer

Research asset: [MetroloPy, GUM, And Sensor Uncertainty Plan](../research/07-metrolopy-gum-and-sensor-uncertainty-plan.md)

Use a GUM-style uncertainty budget with standard uncertainty as the internal representation and approximate 95% coverage intervals for report/dashboard output. Treat the X-Sense `STH51` manufacturer accuracy as Type B evidence, because no per-sensor calibration certificates are available; model CSV one-decimal quantization separately; keep drift, placement, airflow, sensor-to-sensor bias, and autocorrelation as visible named components rather than hidden padding.

MetroloPy is a good fit for point propagation and reporting support, especially `gummy` values, units, expanded uncertainty, budget tables, Monte Carlo checks, and correlation/covariance handling. The production pipeline should still keep uncertainty assumptions in a simple serializable project budget, then reconstruct MetroloPy objects at analysis/report boundaries rather than storing uncertainty objects inside DuckDB or Polars tables in the first pass.

No new wayfinder tickets were added. [Prototype uncertainty bounds in report values and charts](08-prototype-uncertainty-bounds-in-report-values-and-charts.md) and [Prototype uncertainty-library pipeline integration](16-prototype-uncertainty-library-pipeline-integration.md) already cover the next sharp questions.
