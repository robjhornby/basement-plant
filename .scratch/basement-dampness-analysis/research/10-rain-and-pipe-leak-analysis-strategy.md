# Rain And Pipe Leak Analysis Strategy

This asset resolves [Design rain and pipe leak analysis strategy](../issues/10-design-rain-and-pipe-leak-analysis-strategy.md).

## Decision

Use an intervention-aware, evidence-weighted strategy rather than a single classifier. The first analysis should report whether the data is more compatible with `Weather-related leaking`, `Steady-state leaking`, `Whole-house humidity change`, continued `Basement drying`, or an artifact. It should not claim to prove a pipe leak or rain ingress from thermohygrometer data alone.

The immediate implementation should have three stages:

1. Build event-bounded moisture signals from basement, bedroom, and living-room sensors.
2. Add outdoor absolute humidity and rainfall lag features from Open-Meteo and Environment Agency station `270397`.
3. Compare rain-linked signatures against non-rain residual rebound/extraction demand within comparable operating periods.

Current data is enough for exploratory screening, not confident discrimination. The EA rain gauge sanity check for the indoor-data span (`2026-02-13` through `2026-07-03`) found 12 wet days, only 4 days at or above `1 mm`, and only 2 days at or above `5 mm`. Post-dehumidifier data currently contains too little rain exposure and too many intervention changes to distinguish rain ingress from a steady low-rate source.

## Source-Backed Constraints

- Open-Meteo remains the continuous weather source: fetch hourly temperature, relative humidity, dew point, precipitation/rain, pressure, and wind fields for the Caversham coordinate. It supplies coordinate weather rather than a house-local measurement, so treat it as context and feature generation, not ground truth for rain at the wall.
- Environment Agency station `270397` remains the local rainfall cross-check. The rainfall API exposes station metadata and readings, including station/measure period and units; keep this source separate from Open-Meteo rather than merging it away.
- EA hydrology/rainfall readings can include quality, missingness, validity, and value fields. Preserve those fields and exclude or flag invalid/missing readings before calculating event totals.
- Relative humidity alone is not a suitable cross-temperature moisture metric. Use the psychrometric core from [Physics Model Scope And Equations](06-physics-model-scope-and-equations.md): vapour pressure, absolute humidity, and optional dew point.
- Building moisture causes overlap. EPA and WHO guidance both distinguish rainwater/surface-water/groundwater sources, plumbing water, indoor/outdoor humidity, humid-air leakage, vapour diffusion, capillary movement, condensation, ventilation, and insufficient dehumidification. That supports reporting competing explanations rather than a binary result.
- A damp basement can behave like a continuing moisture source even without an active pipe leak. EPA moisture guidance notes that damp basements or crawlspaces may add a large daily vapour load, so persistent rebound is not automatically plumbing evidence.
- Rain-day observations can mislead: condensation or outdoor-humidity ventilation effects can appear during rain and be mistaken for direct rainwater ingress. Compare rain timing against outdoor absolute humidity, control-room sensors, and dew point/surface-temperature plausibility where available.
- Ventilation can change indoor humidity and building-envelope pressure relationships. The extractor shutdown at dehumidifier setup is therefore a major confounder, not just a background detail.
- Antecedent wetness matters. Rainfall amount, intensity, and preceding wet conditions affect water movement; use rolling totals and time-since-rain features rather than same-hour rain alone.
- GUM/NIST-style uncertainty thinking applies: define the measurand, inputs, and uncertainty components before treating a reported rate or difference as meaningful. Here the key uncertainty components include sensor specs, sensor placement, weather-source mismatch, event timestamps, missing data, and unlogged door/household activity.
- Treat this as observational evidence. Correlation patterns need supporting physical context, repeated events, and direct inspection/logged observations before they become causal claims.

Primary source links:

- Open-Meteo Historical Weather API: https://open-meteo.com/en/docs/historical-weather-api
- Environment Agency Rainfall API: https://environment.data.gov.uk/flood-monitoring/doc/rainfall
- Environment Agency Hydrology API reference: https://environment.data.gov.uk/hydrology/doc/reference
- EPA Moisture Control Guidance for Building Design, Construction and Maintenance: https://www.epa.gov/sites/default/files/2014-08/documents/moisture-control.pdf
- NWS hydrology training, runoff factors and antecedent soil moisture: https://training.weather.gov/nwstc/Hydrology/HYDRO/BHModule/BH-unit4.HTML
- WHO Guidelines for Indoor Air Quality: Dampness and Mould, moisture control and ventilation: https://www.ncbi.nlm.nih.gov/books/NBK143947/
- NIST Technical Note 1900, uncertainty evaluation: https://nvlpubs.nist.gov/nistpubs/TechnicalNotes/NIST.TN.1900.pdf
- JCGM 100:2008, Guide to the expression of uncertainty in measurement: https://www.bipm.org/documents/20126/2071204/JCGM_100_2008_E.pdf

## Candidate Signals

### Core moisture signals

Calculate these at a regular analysis cadence, initially hourly for weather-aligned metrics and 5- or 15-minute for dehumidifier-cycle metrics:

- `basement_absolute_humidity_g_m3`
- `bedroom_absolute_humidity_g_m3`
- `living_room_absolute_humidity_g_m3`
- `outdoor_absolute_humidity_g_m3`
- `basement_minus_outdoor_ah_g_m3`
- `basement_minus_control_ah_g_m3`, where the control is bedroom, living room, or their robust average
- `basement_rh_pct` and `basement_dew_point_c` as explanatory/context metrics
- `dehumidifier_cycle_phase`, if detectable: drying, rebound, unknown
- `rebound_ah_rate_g_m3_h`, only within post-dehumidifier comparable operating periods
- `drying_ah_rate_g_m3_h`, only as a dehumidifier/control indicator, not as an ingress rate by itself

### Rain and weather features

Build these separately for Open-Meteo rain and EA station rain:

- Rain totals over `1h`, `3h`, `6h`, `12h`, `24h`, and `48h`.
- Lagged rain totals from `0h` to `72h`, initially hourly.
- Event rainfall features: event total, maximum 15-minute burst from EA readings, maximum hourly rain, event duration, and time since last rain.
- Antecedent-wetness proxies: previous `24h`, `48h`, `72h`, and `7d` rain totals.
- Wet-period labels: dry, active rain, post-rain `0-12h`, post-rain `12-24h`, post-rain `24-48h`, post-rain `48-72h`.
- Outdoor absolute humidity, outdoor dew point, wind speed/direction, and pressure as context features.
- `rain_source_agreement`: whether Open-Meteo and EA both detect the wetting episode.

Rain features should be used as event exposure variables. Do not infer house-local rain impact from one source alone without caveat.

### Intervention and artifact features

Every summary, plot, and model should include:

- `analysis_period` from [Intervention, Room, And Device Context](04-intervention-room-and-device-context.md).
- Indicators for extractor state, dehumidifier state, circulation fan state, sensor placement, and dehumidifier orientation.
- Gap flags and sample-count coverage.
- Whole-house control changes from bedroom/living-room sensors.

The `2026-07-01 21:00` extractor/dehumidifier change and the `2026-07-02 14:40` sensor move should split models. Do not fit a single rain/leak model across those boundaries.

## Expected Signatures

### Weather-related leaking

Evidence becomes stronger when all or most of these repeat across multiple wet episodes:

- Basement absolute humidity or rebound rate increases after rain with a plausible lag, initially searched across `0-72h`.
- The response is basement-specific: bedroom/living-room sensors do not show a similar increase at the same time.
- The response scales roughly with rolling rain amount, rain duration, or repeated wet days.
- The response is stronger when Open-Meteo and EA agree on rain than when only one source indicates rain.
- The signal appears within the same event-bounded operating period, not only across intervention boundaries.
- The same lag family recurs across events, rather than moving wherever the strongest coincidence happens.

Rain evidence remains weak if the signal appears only once, coincides with a sensor move or equipment change, or is mirrored by whole-house sensors and outdoor absolute humidity.

### Steady-state leaking

Evidence becomes stronger when:

- Non-rain periods still show persistent basement-specific rebound after dehumidifier off-cycles.
- Rebound/extraction demand remains elevated after the initial drying reservoir should be declining.
- The baseline residual is present across dry periods and is not mirrored by bedroom/living-room controls.
- Rain terms explain little extra variation once intervention period, outdoor absolute humidity, and dehumidifier cycle state are included.
- Future tank-empty volumes, if logged, show ongoing extracted water that cannot plausibly be explained by air moisture alone.

This should be reported as "compatible with steady-state leaking" unless there is direct plumbing evidence. A pipe leak is one possible steady-state source, not the only one.

### Basement drying / reservoir release

Evidence favours ongoing drying rather than new ingress when:

- Rebound rates decline over time within the same operating configuration.
- Dehumidifier drying cycles shorten or off-cycle rebound weakens after controlling for outdoor moisture.
- The trend is monotonic or smoothly decaying rather than rain-pulse-shaped.
- Tank extraction, if later recorded, declines over comparable dry periods.

Early post-dehumidifier data should assume reservoir release is a dominant candidate explanation.

### Whole-house humidity change

Evidence favours whole-house/outdoor coupling when:

- Basement, bedroom, and living-room absolute humidity move together.
- Outdoor absolute humidity changes explain the direction and timing.
- Rain timing adds little beyond outdoor moisture and control-room movement.

Whole-house changes do not rule out a basement problem, but they weaken claims that a specific rain or pipe source caused a basement-only event.

### Sensor or dehumidifier artifacts

Evidence favours artifact when:

- Apparent changes align with sensor moves, fan addition, dehumidifier orientation changes, or extractor shutdown.
- The signal is strongest in RH but not absolute humidity.
- The signal exists only at cycle extrema or depends heavily on the cycle-detection parameters.
- The signal changes when the analysis cadence, smoothing window, or cycle threshold changes.

## Model Strategy

### 1. Descriptive event-bounded dashboard

Start with plots and tables, because this data has confounding interventions:

- Time series of basement/control/outdoor absolute humidity.
- Basement RH and temperature as secondary panels.
- Rain bars from EA station `270397` plus Open-Meteo rain.
- Vertical event markers for all basement events.
- Period-level summaries: mean AH, median AH, slope, rebound rate distribution, wet/dry coverage, and sample coverage.

This stage should answer: "where are candidate rain responses and are they visually event-confounded?"

### 2. Matched wet/dry comparisons

For each event-bounded period with enough data:

- Define wet windows by rolling EA/Open-Meteo rain and lag class.
- Match each wet/post-rain window with nearby dry windows in the same intervention period.
- Compare basement-specific residual moisture:

```text
basement_specific_ah =
    basement_absolute_humidity_g_m3
  - robust_average(control_absolute_humidity_g_m3)
```

Also compare:

```text
outdoor_adjusted_basement_ah =
    basement_absolute_humidity_g_m3
  - outdoor_absolute_humidity_g_m3
```

Report effect sizes with uncertainty bands or bootstrap intervals. Prefer medians and robust slopes because dehumidifier cycles create non-normal residuals.

### 3. Lag scan with guardrails

Run a constrained lag scan:

- Candidate lags: `0-72h`, hourly.
- Rain exposures: rolling `1h`, `3h`, `6h`, `12h`, `24h`, `48h`.
- Outcomes: basement-specific AH residual, rebound AH rate, dehumidifier off-cycle peak AH, and period-level AH slope.
- Stratify by analysis period; do not pool across sensor-placement or extractor-state boundaries unless explicitly shown as a sensitivity check.

Guardrails:

- Pre-register the lag grid in code/report metadata so later charts do not quietly cherry-pick the best-looking lag.
- Require repeated support across multiple rain events before calling a rain response.
- Report the full lag profile, not only the maximum.

### 4. Simple residual model

After plots and matching, fit a small model only if there are enough events:

```text
basement_specific_ah_t =
    period_intercept
  + drying_time_term
  + outdoor_ah_term
  + rain_lag_terms
  + cycle_state_term
  + residual_t
```

Use this as an explanatory decomposition, not a causal proof. With the current data volume, prefer regularized or deliberately small models over flexible machine-learning fits.

For dehumidifier-cycle windows, a second model can use rebound segments:

```text
rebound_ah_rate =
    period_intercept
  + elapsed_time_since_dehumidifier_start
  + recent_rain_lag_terms
  + outdoor_ah
  + cycle_duration_or_start_ah
  + residual
```

Only fit this within stable post-dehumidifier configurations. The current post-dehumidifier window is too short and too intervention-heavy for a confident fit.

### 5. Sensitivity analysis

Every result should be re-run with:

- Open-Meteo rain only.
- EA rain only.
- Both-source-agree wet windows only.
- Bedroom control only, living-room control only, and robust average control.
- Different analysis cadences: hourly and 15-minute where appropriate.
- Alternative cycle thresholds.
- Exclusion of windows around logged interventions, initially `+/- 2h` and widened for sensor moves/equipment changes.

Claims survive only if the direction and timing remain broadly stable.

## Minimum Data Duration

Use these thresholds:

- `Exploratory`: current full indoor history plus weather join. Suitable for identifying candidate events and testing the pipeline.
- `Weak evidence`: at least `5-8` meaningful wet episodes, including several above `1 mm/day`, with unconfounded dry comparison windows in the same operating period.
- `Moderate evidence`: at least `10-15` meaningful wet episodes across multiple weeks/months, including repeated post-dehumidifier wet events and enough dry days to estimate baseline rebound.
- `Stronger evidence`: a full seasonal spread with stable sensor placement, logged tank volumes, and direct observations of damp patches/floor water when available.

The current dataset appears to meet only the exploratory threshold for rain response. It does not yet provide enough post-dehumidifier rain exposure for confident rain-vs-steady discrimination.

## Failure Modes

The data cannot distinguish rain ingress from steady-state leaking when:

- Rain events are too few, too small, or clustered too close together.
- All wet events coincide with interventions, sensor moves, tank-full periods, or large household activity.
- Outdoor absolute humidity and whole-house sensors move in the same direction as the basement.
- The apparent rain lag changes substantially between events.
- Dehumidifier control-cycle artifacts dominate the outcome metric.
- The signal is smaller than sensor/placement/weather-source uncertainty.
- There is no direct plumbing, visual wetness, tank-volume, or material-moisture evidence to break the tie.

In those cases, report the result as unresolved and recommend more data or direct inspection rather than forcing a classification.

## Implementation Requirements For The Next Prototype

- Keep raw indoor, Open-Meteo, and EA rainfall source tables separately.
- Normalize timestamps to `Europe/London` before joining.
- Derive absolute humidity with the same formula for indoor and outdoor readings.
- Store weather source metadata: provider, coordinate/station id, units, fetch timestamp, endpoint, and source cadence.
- Generate rain rolling totals and lag features in a reusable feature module.
- Read `data/basement_events.csv` as first-class model input and expose analysis periods in every output table.
- Produce a "rain response candidates" table with event time, rain source agreement, lag, basement response, control response, intervention proximity, and caveat flags.
- Make every chart able to show uncertainty/caveat flags even before full GUM propagation is implemented.

## Recommended Report Language

Use:

- "The data is compatible with..."
- "A basement-specific increase followed rain by..."
- "This is exploratory because..."
- "This pattern is not mirrored by the upstairs sensors..."
- "This does not prove a pipe leak."

Avoid:

- "Rain caused..."
- "Pipe leak detected..."
- "No leak..."
- "The basement is dry..."

## Effect On The Wayfinding Map

[Build weather-inclusive end-to-end prototype](../issues/17-build-weather-inclusive-end-to-end-prototype.md) should implement the descriptive dashboard, rain features, and candidate-event table before any dashboard/publication decision relies on rain or steady-leak claims.

[Prototype uncertainty bounds in report values and charts](../issues/08-prototype-uncertainty-bounds-in-report-values-and-charts.md) should later turn the caveat flags and source uncertainty into visible uncertainty bands.
