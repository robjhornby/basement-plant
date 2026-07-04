# Design rain and pipe leak analysis strategy

Type: research
Status: resolved
Parent: ../map.md
Blocked by: 05, 09

## Question

What analysis strategy can distinguish rain-correlated ingress from a constant low-rate moisture source such as a pipe leak?

Use the confirmed hypotheses and chosen weather features. Propose candidate signals, lagged correlations, intervention-aware models, baseline/dehumidifier cycle normalization, expected signatures, minimum data duration, and failure modes where the data cannot distinguish the causes.

Use [Intervention, Room, And Device Context](../research/04-intervention-room-and-device-context.md) to avoid confusing intervention effects with ingress signals. In particular, visible floor water dried and has not reappeared, visual observations are opportunistic rather than continuous, extractor ventilation changed at dehumidifier setup, and routine door/household activity will remain an unlogged confounder.

## Answer

Use an intervention-aware, evidence-weighted strategy rather than a single classifier. The supporting research note is [Rain And Pipe Leak Analysis Strategy](../research/10-rain-and-pipe-leak-analysis-strategy.md).

The next prototype should calculate basement/control/outdoor absolute humidity, rain rolling totals, rain lag features, wet/dry period labels, dehumidifier-cycle rebound metrics, and caveat flags for event proximity, source mismatch, data gaps, and sensor placement. It should compare basement-specific residual moisture against rain exposure within event-bounded periods, then run guarded lag scans and matched wet/dry comparisons before attempting any simple residual model.

Expected signatures:

- `Weather-related leaking`: repeated basement-specific absolute-humidity or rebound-rate increases after rain at plausible, stable lags, stronger when Open-Meteo and EA station `270397` agree on rain, and not mirrored by bedroom/living-room sensors.
- `Steady-state leaking`: persistent basement-specific rebound or extraction demand through dry periods after accounting for outdoor moisture, intervention period, and dehumidifier cycle state. Report this only as "compatible with steady-state leaking" without direct plumbing evidence.
- `Basement drying`: declining rebound/extraction demand over comparable dry periods, especially as the initial fabric reservoir dries.
- `Whole-house humidity change`: basement and control sensors moving together with outdoor absolute humidity.
- `Sensor/dehumidifier artifact`: apparent effects aligned with sensor moves, extractor shutdown, fan addition, dehumidifier orientation, or cycle-detection thresholds.

Current data supports exploratory screening only. A sanity check of EA station `270397` over the current indoor-data span found 12 wet days, only 4 days at or above `1 mm`, and only 2 days at or above `5 mm`; post-dehumidifier data has too little rain exposure and too many intervention changes for confident rain-vs-steady discrimination.

[Build weather-inclusive end-to-end prototype](17-build-weather-inclusive-end-to-end-prototype.md) should implement the descriptive dashboard, rain features, and candidate-event table before any dashboard/publication decision relies on rain or steady-leak claims.
