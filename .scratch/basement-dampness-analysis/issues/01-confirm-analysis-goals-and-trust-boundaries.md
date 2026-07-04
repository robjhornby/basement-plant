# Confirm analysis goals and trust boundaries

Type: grilling
Status: resolved
Parent: ../map.md

## Question

What should this project optimize for first, and which assumptions from the prototype PRD should be trusted, rejected, or treated as tentative?

Resolve by interviewing the user one question at a time. Confirm the primary near-term outcome, likely among:

- a reliable local analysis library,
- a publishable dashboard,
- a physics/metrology report,
- an automated ingestion system,
- a leak/rain diagnosis workflow,
- or a deliberately balanced first slice across several of these.

Also confirm what counts as an acceptable answer: directional evidence, calibrated confidence bounds, formal uncertainty budget, actionable household decision, or article-quality explanation.

## Answer

The first serious slice should optimize for a reliable local analysis library. The dashboard, automated ingestion system, and physics/metrology report should be treated as downstream consumers of that analysis core rather than primary goals for the first implementation.

The acceptable answer shape is quantitative-but-provisional evidence. The analysis should use an explicit measurement uncertainty model and propagate uncertainty through derived values such as averages, fits, and rate calculations. Early iterations may use estimated input uncertainties where calibration certificates or product-specific evidence are unavailable, but the direction of travel is a formal uncertainty budget. If calibration data is unavailable, the project should make that failure explicit and choose estimated uncertainties or another basis deliberately.

Measurement uncertainty and caveats are separate concepts:

- Measurement uncertainty is quantitative and belongs in the physical modelling and calculations.
- Caveats are qualitative explanatory text about model limits, confounders, pros/cons, and interpretation risks.

The core analysis should build evidence about three physical hypotheses:

- steady-state leaking: ongoing moisture ingress independent of short-term weather;
- weather-related leaking: moisture ingress associated with rain or outdoor weather;
- basement drying: gradual reduction in stored moisture after the dehumidifier was added, assuming the walls/floor may have started saturated.

The current prototype should be trusted only as evidence of useful analytical directions, not as settled truth.

Keep as promising directions:

- absolute humidity rather than RH-only analysis;
- cycle and rebound-rate analysis as potential drying/leaking signals;
- comparing basement readings against other locations for household context.

Treat as tentative:

- inferred basement sensor;
- inferred dehumidifier start;
- detected dehumidifier cycles;
- current headline improvement values;
- current rebound-rate trend.

Reject as production assumptions:

- automatic leak/no-leak interpretation;
- unstated sensor accuracy;
- no weather model;
- no intervention timeline;
- no formal uncertainty propagation.

The user wants to be involved in the architecture decision for how MetroloPy or another uncertainty library integrates with DuckDB and/or Polars, including whether UDF-style integration is appropriate.
