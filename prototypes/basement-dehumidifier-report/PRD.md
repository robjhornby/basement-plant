# PRD: Basement Dampness Analysis Prototype

## Problem Statement

The basement has persistent dampness, and the user wants to understand whether conditions are improving after adding a dehumidifier or whether continuing moisture ingress suggests a leak or other structural wet source. The available data is minute-level temperature and relative humidity from three house locations. The basement data contains visible dehumidifier cut-on/cut-off cycles, but there are confounding changes such as dehumidifier movement, fan addition, and sensor movement.

The immediate need is a prototype web interface that shows the basement data from the dehumidifier period and offers a simple metric for whether dampness is improving.

## Solution

Build a disposable local analysis prototype that loads the three CSV exports with Polars, infers the basement sensor, infers the start of the dehumidifier period from the data, computes humidity and absolute-humidity metrics, detects dehumidifier cycle segments, and renders an interactive HTML report using Plotly.js.

The first improvement metric is the off-cycle moisture rebound rate: after a drying trough, measure how quickly absolute humidity rises before the next drying phase. A falling rebound rate over time is treated as directional evidence that the basement is drying. A steady or increasing rebound rate, especially after controlling for temperature and known events, would be evidence to investigate ongoing water ingress.

## User Stories

1. As a homeowner, I want to see the basement humidity data since the dehumidifier started, so that I can visually inspect the cut-on/cut-off cycles.
2. As a homeowner, I want the app to infer which CSV is the basement sensor, so that I can get an initial result without manual setup.
3. As a homeowner, I want the app to infer when the dehumidifier signal begins, so that the initial analysis focuses on the relevant period.
4. As a homeowner, I want to compare pre-dehumidifier and post-dehumidifier humidity, so that I can see the immediate effect of the intervention.
5. As a homeowner, I want the app to show absolute humidity alongside RH, so that temperature changes do not dominate the interpretation.
6. As a homeowner, I want detected drying and rebound cycles listed, so that I can inspect the raw events behind the metric.
7. As a homeowner, I want a simple dampness-improvement metric, so that I can decide whether to keep collecting data or investigate a leak.
8. As a homeowner, I want all three locations shown for context, so that I can distinguish basement-specific behavior from whole-house humidity changes.
9. As a homeowner, I want the prototype to run locally from the CSVs, so that I do not need to upload house sensor data elsewhere.
10. As a future analyst, I want known intervention events to be representable later, so that dehumidifier movement, fan addition, and sensor movement can be controlled for.
11. As a future analyst, I want the model to support physical inputs later, so that room size, airflow, and dehumidifier capacity can improve the interpretation.
12. As a future analyst, I want the prototype to be disposable, so that validated ideas can be rebuilt cleanly rather than preserving exploratory code.

## Implementation Decisions

- Use Polars as the primary data engine for CSV ingestion, time sorting, daily aggregation, and chart downsampling.
- Keep the first prototype as a generated static HTML report rather than adding a web framework dependency.
- Use Plotly.js for interactive charts because it provides zooming, panning, hover inspection, multiple axes, and reliable local HTML embedding.
- Infer the basement sensor by ranking sensors by high median RH and low median temperature.
- Infer the dehumidifier start by finding the first large high-to-low RH transition on the first day with a large humidity range.
- Compute absolute humidity from temperature and RH using a Magnus-style saturation vapor pressure formula.
- Detect cycles from smoothed five-minute samples and local extrema.
- Treat trough-to-peak intervals as rebound/off-cycle intervals and peak-to-trough intervals as drying/on-cycle intervals.
- Use median rebound absolute-humidity rate over comparable recent windows as the first dampness-improvement metric.
- Keep the prototype under a clearly named prototype folder with notes documenting the assumptions and limits.

## Testing Decisions

- No automated tests are required for this throwaway prototype.
- Verification should focus on external behavior: the command runs, the HTML report is generated, charts render, and headline metrics match the data.
- For a production version, tests should cover CSV parsing, absolute humidity calculation, dehumidifier start inference, cycle segmentation, and metric stability against missing samples.
- The highest future seam should be a pure analysis module that accepts normalized sensor readings and optional event annotations, then returns chart-ready series and metric tables.

## Out of Scope

- Leak diagnosis or a definitive dampness conclusion.
- A calibrated room physics model with air exchange, wall moisture storage, dehumidifier capacity, or outside weather.
- A persistent database or production web app.
- Manual event editing UI.
- Automated import from sensors or home automation systems.
- Marimo notebook interactivity, unless chosen in a later iteration.

## Further Notes

This PRD was saved locally because the repo has no configured issue tracker metadata and no GitHub remote. If an issue tracker is added later, this document can be copied into a `ready-for-agent` issue.

The current prototype result is directionally encouraging: after the inferred dehumidifier start at `2026-07-01 18:25`, average RH drops from `86.78%` over the prior seven days to `65.28%`, and latest median rebound absolute-humidity rate is slightly lower than the first 36-hour window. The data window is short and confounded by equipment/sensor changes, so this is not yet strong evidence.
