# Physics And Metrology Report Mock

This prototype resolves [Plan physics and metrology report artifact](../issues/15-plan-physics-and-metrology-report-artifact.md). It is a rough content model for a locally generated explanatory report, not final copy and not a production template.

## Prototype Decision

The physics/metrology artifact should be a companion explanation page linked from the dense local dashboard, not the dashboard's first screen. The first dashboard should stay analytical and scannable; this report should explain why the numbers mean what they claim to mean, what assumptions sit behind them, and where the evidence is still weak.

Recommended first generated form:

- one static Markdown/HTML page generated alongside the local dashboard;
- owner-analyst audience first;
- explicit report date, data window, event-period coverage, and analysis version;
- cautious claim language, with "compatible with" and "not yet distinguishable" where appropriate;
- formulas and uncertainty assumptions visible enough to audit;
- publication/blog polish deferred until the analysis produces stable results worth publishing.

## Page Role

Use this page when the owner wants to answer:

- What physical quantity is the dashboard really plotting?
- Why is absolute humidity preferred over relative humidity for this analysis?
- What does the uncertainty band include, and what does it exclude?
- How should drying, rain-related ingress, and steady leaking be interpreted from this dataset?
- Which caveats stop the current data from proving a cause?

Do not use this page as:

- a live dashboard replacement;
- a public article in its first version;
- a leak diagnosis certificate;
- a hidden appendix that only developers can understand.

## Proposed Report Structure

### 1. Report Header

Purpose: identify the generated artifact and its evidential boundary.

Required fields:

- `report_generated_at`
- `data_window_start`
- `data_window_end`
- `analysis_version`
- `weather_sources`
- `sensor_models`
- `event_timeline_version`

Example copy:

> This report explains the physical model behind the local basement dampness dashboard for data from `DATA_WINDOW_START` to `DATA_WINDOW_END`. It is an exploratory homeowner analysis using consumer thermohygrometers, public weather data, and a recorded intervention timeline. It can show patterns compatible with drying, weather-related moisture, or steady moisture ingress; it cannot prove the source of water on its own.

### 2. Plain-Language Finding Summary

Purpose: give the owner a short reading of the dashboard without burying caveats.

Use 3 to 5 generated bullets:

- what changed since the dehumidifier/intervention period began;
- whether basement absolute humidity is trending down, stable, or rebounding;
- whether recent rain has a visible corresponding basement-specific response;
- whether current evidence is compatible with steady moisture ingress;
- which caveat dominates the current interpretation.

Example copy:

> The current data is strongest for active basement drying after the dehumidifier setup. Evidence for rain-related ingress is still exploratory because the post-dehumidifier period contains limited rain exposure and several intervention changes. Persistent rebound during dry periods should be reported as compatible with ongoing moisture release or steady ingress, not as proof of a pipe leak.

### 3. Why Relative Humidity Is Not Enough

Purpose: explain the key modelling choice before showing equations.

Core points:

- RH depends strongly on temperature.
- The same water vapour amount can have different RH at different temperatures.
- Absolute humidity in `g/m3` is the main cross-temperature moisture metric.
- RH remains useful for dehumidifier control, mould-risk context, and comfort.

Include a small generated example when available:

```text
At the same temperature period, basement absolute humidity changed from
PRE_AH +/- PRE_U g/m3 to POST_AH +/- POST_U g/m3.
```

### 4. Psychrometric Calculation

Purpose: show the core equations in inspectable form.

Display these equations with named units:

```text
e_s_pa = 611.2 * exp((17.62 * T_c) / (243.12 + T_c))
e_pa = (RH_pct / 100) * e_s_pa
absolute_humidity_g_m3 = 1000 * e_pa / (461.5 * (T_c + 273.15))
```

Optional explanatory outputs:

- dew point, for condensation/surface-risk explanation;
- approximate air water mass, only as a scale check using the current `17.5 m3` room volume estimate.

Required caveat:

> Air water mass is only a scale check. A basement can release or receive much more water from walls, floor, ventilation, rain pathways, or a leak than is present in the air at any one moment.

### 5. Event Periods And Comparability

Purpose: prevent misleading before/after comparisons.

Render the event-bounded periods from `data/basement_events.csv` and mark whether each period is suitable for:

- broad trend summary;
- rebound-rate analysis;
- rain comparison;
- cross-sensor comparison.

Required warning:

> Metrics are compared within event-bounded periods where possible. Broad windows that cross extractor, dehumidifier, fan, orientation, or sensor-placement changes are not treated as directly comparable.

### 6. Uncertainty Budget

Purpose: expose the GUM-style assumptions behind reported values.

Render a compact budget table:

| Component | Applies to | First-pass treatment | Included in headline interval? |
| --- | --- | --- | --- |
| Temperature manufacturer accuracy | STH51 readings | Type B rectangular | yes |
| RH manufacturer accuracy | STH51 readings | Type B rectangular | yes |
| CSV quantization | one-decimal exports | Type B rectangular | yes |
| Sensor drift | physical sensor over time | named estimate/sensitivity | maybe |
| Sensor placement and airflow | event period | caveat or scenario | no, unless modelled |
| Weather-source mismatch | rain/outdoor context | caveat or scenario | no, unless modelled |
| Door and household activity | residual confounder | caveat | no |

Use wording close to:

> Intervals are approximate 95% coverage intervals from the stated sensor and modelling assumptions, using `k = 2` unless the report says otherwise. They are not calibration certificates and do not include every real-world confounder.

### 7. Reading Values And Comparisons

Purpose: explain what the dashboard's intervals mean.

Rules to state:

- absolute levels keep manufacturer sensor uncertainty visible;
- same-sensor changes over a stable placement period may be tighter if common bias plausibly cancels;
- cross-sensor comparisons should not assume cancellation;
- daily means and slopes must account for autocorrelation and missing data;
- rebound rates are directional evidence, not source attribution by themselves.

Example copy:

> A same-sensor before/after change can have a narrower interval than either absolute level, but only when the sensor, placement, and operating regime are comparable. This report labels that assumption explicitly. It is not reused for bedroom-vs-basement or living-room-vs-basement comparisons.

### 8. Moisture Balance Vocabulary

Purpose: give the owner the conceptual model without pretending all terms are fitted.

Show the balance as vocabulary:

```text
dM_air/dt =
    G_weather_related_leaking
  + G_steady_state_leaking
  + G_reservoir_release
  + G_ventilation
  + G_internal_exchange
  - R_dehumidifier
  - S_condensation_or_adsorption
```

Then explicitly split fitted from unfitted:

- currently quantified: measured indoor moisture state, event-bounded summaries, slopes/rebound metrics, rain features, outdoor context;
- currently not fitted as physical rates: wall/floor reservoir capacity, ventilation rate, steady leak rate, weather-ingress flow rate, condensation sink.

### 9. Hypothesis Evidence

Purpose: align report language with the dashboard's cautious hypothesis panel.

Use the same hypothesis labels as the dashboard:

- `Basement drying`
- `Weather-related leaking`
- `Steady-state leaking`
- `Whole-house humidity change`
- `Sensor/dehumidifier artifact`

For each hypothesis, render:

- evidence supporting it;
- evidence against or weakening it;
- current confidence wording;
- next observation that would strengthen or weaken the case.

Claim-language ladder:

| Evidence state | Allowed wording |
| --- | --- |
| Single confounded episode | "a candidate pattern" |
| Repeated but not isolated | "compatible with" |
| Repeated, basement-specific, event-stable | "evidence for" |
| Direct corroborating observation plus data | "strong evidence for" |

Avoid:

- "proves a pipe leak";
- "rules out rain ingress";
- "dry" without defining the metric;
- "no leak" from absence of thermohygrometer evidence.

### 10. Rain And Steady-Leak Interpretation

Purpose: explain the strategy before the user sees lag scans or matched wet/dry tables.

Required elements:

- Open-Meteo gives continuous coordinate weather context;
- Environment Agency station `270397` gives local rainfall cross-check;
- rain features use rolling totals and lags, initially across `0h` to `72h`;
- matched wet/dry comparisons must stay inside comparable event periods;
- current data is exploratory until there are enough wet episodes after major interventions.

Example copy:

> Rain-related ingress should appear as repeated basement-specific moisture or rebound responses after rain at plausible, stable lags. A steady source should remain visible through dry periods after accounting for outdoor moisture, event period, and dehumidifier cycle state. Current thermohygrometer evidence can make either explanation more or less plausible, but direct inspection or plumbing evidence is needed for a firm diagnosis.

### 11. What Would Change The Conclusion

Purpose: make the report useful as an investigation tool, not just a description.

Generated prompts:

- More post-dehumidifier rain events with stable sensor/dehumidifier placement.
- Tank-empty timestamps and approximate collected litres.
- Co-location check between STH51 sensors.
- Surface temperature measurements for condensation-risk claims.
- Direct observations of new wet patches, visible water, plumbing work, or building work.
- A longer stable dry period after the initial reservoir release declines.

### 12. Technical Appendix

Purpose: keep the main narrative readable while preserving auditability.

Include:

- formula sources and constants;
- uncertainty budget rows and distributions;
- event period table;
- data coverage and missingness summary;
- rain source coverage and quality flags;
- lag grid used for rain scanning;
- analysis code version and input file hashes when available.

## Static Site Placement

Recommended local navigation:

- dashboard page: dense current-state and plots;
- report page: this explanatory artifact;
- optional appendix anchors inside the report rather than separate pages at first.

Dashboard links should use terse labels:

- `Methods`
- `Uncertainty`
- `Evidence`

The report can be generated after the dashboard data model exists. It should consume the same summary objects rather than redoing analysis separately.

## Publication Adaptation Later

For `robjhornby.com` or blog use, create a separate public-pass decision before publishing. Public adaptation should:

- remove or generalize detailed timestamps if privacy requires it;
- turn the owner-analyst caveats into reader-facing explanation;
- include fewer raw diagnostics;
- add diagrams only after the model and claims have stabilized;
- keep source and uncertainty notes, but move deep audit tables to collapsible sections or an appendix.

## Newly Sharp Follow-Up

This ticket makes one next implementation question sharp:

> How should the local static generator structure the dashboard/report outputs and shared analysis summary objects so the dense dashboard and explanatory report do not duplicate calculations?

That question should be handled after the weather-inclusive end-to-end prototype shows the first real local page shape.
