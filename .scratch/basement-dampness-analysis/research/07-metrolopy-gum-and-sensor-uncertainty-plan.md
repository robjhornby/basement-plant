# MetroloPy, GUM, And Sensor Uncertainty Plan

This asset resolves [Research MetroloPy, GUM, and sensor uncertainty plan](../issues/07-research-metrolopy-gum-and-sensor-uncertainty-plan.md).

## Recommendation

Use GUM-style uncertainty budgeting, but keep the first implementation deliberately small and inspectable:

1. Represent each raw `STH51` temperature/RH reading as an estimate plus named uncertainty components.
2. Convert every component to a standard uncertainty before propagation.
3. Propagate through the established psychrometric core: saturation vapour pressure, vapour pressure, absolute humidity, and optional dew point.
4. Store and test the uncertainty model as ordinary Python functions first; let MetroloPy carry units, standard uncertainties, expanded uncertainties, correlations, and Monte Carlo checks inside those functions.
5. Report dashboard intervals as approximate 95% coverage intervals, not as calibration-grade confidence intervals.

For the early dashboard/report, the default headline wording should be close to:

> Absolute humidity: `x +/- U g/m3`, where `U` is an approximate 95% coverage interval (`k = 2`) from the stated sensor and modelling assumptions.

Avoid saying the basement is "proven" wetter/drier by less than the relevant interval unless the comparison is a within-sensor, event-bounded comparison where common components plausibly cancel.

## Authoritative Sources

- BIPM/JCGM, [JCGM 100:2008, Guide to the expression of uncertainty in measurement](https://www.bipm.org/documents/20126/2071204/JCGM_100_2008_E.pdf). This is the primary GUM source for combined standard uncertainty, covariance, the law of propagation of uncertainty, expanded uncertainty, and coverage factors.
- BIPM/JCGM, [JCGM 101:2008, Supplement 1 to the GUM, propagation of distributions using a Monte Carlo method](https://www.bipm.org/documents/20126/2071204/JCGM_101_2008_E.pdf). This is the primary source for Monte Carlo propagation when linearization or normal/t assumptions are weak.
- NIST, [Technical Note 1297](https://www.nist.gov/pml/nist-technical-note-1297). NIST's practical web version is useful for Type B uncertainty, combined standard uncertainty, and the convention of reporting expanded uncertainty with `k = 2` for many practical measurements.
- MetroloPy, [official documentation](https://nrc-cnrc.github.io/MetroloPy/_build/html/hand_made_doc.html) and [API reference](https://nrc-cnrc.github.io/MetroloPy/_build/html/metrolopy.html). The `gummy` object represents a value with standard or expanded uncertainty and units; the package supports uncertainty budget tables, Monte Carlo propagation, degrees of freedom, correlations, covariance, and expanded uncertainty.
- X-Sense, [STH51/SBS50 user manual PDF](https://download.x-sense.com/de/STH51_SBS50_User_Manual.pdf), plus the maintained local notes at [X-Sense STH51 Manual Notes](../../../docs/reference/x-sense-sth51-manual-notes.md). These are the project evidence for device accuracy and the explicit absence of sensor-specific calibration certificates.
- NPL, [Dew point and relative humidity conversion](https://www.npl.co.uk/resources/q-a/dew-point-and-relative-humidity). This supports the project decision to convert through vapour pressure and saturation vapour pressure.

## GUM Principles To Use

The calculation should distinguish these quantities:

- `x`: best estimate of the measured or derived value.
- `u`: standard uncertainty, expressed like a standard deviation.
- `uc`: combined standard uncertainty after propagation.
- `U`: expanded uncertainty for reporting, commonly `U = k * uc`.
- `k`: coverage factor; use `k = 2` as the first approximate 95% reporting convention unless a later ticket justifies Student-t or Monte Carlo quantile intervals.
- covariance/correlation: required when inputs are not independent.

Use Type A evaluation for variation estimated from data, such as repeated readings or residual variability. Use Type B evaluation for manufacturer specs, calibration certificate values, resolution, drift estimates, placement estimates, and other judgement-based components. NIST TN 1297 explicitly treats manufacturer specifications and calibration reports as Type B evidence.

The first implementation should not hide Type B judgements inside a single magic number. Keep an uncertainty budget with named rows, source, distribution, half-width or standard uncertainty, and whether the component is random, per-device, common-mode, or placement-specific.

## Sensor Uncertainty Budget

The current evidence boundary is:

- All three CSV-producing sensors are X-Sense `STH51` units.
- No sensor-specific calibration certificates are available.
- The X-Sense manual gives operating range and manufacturer accuracy only.
- The manual states humidity accuracy is measured at constant `25 C`; changed temperature may affect accuracy.
- CSV export currently gives one decimal place for temperature and RH.

Recommended first-pass components:

| Component | Applies to | First-pass representation | Notes |
| --- | --- | --- | --- |
| Temperature manufacturer accuracy | Each temperature reading | Type B rectangular distribution using the manual's maximum accuracy for the current temperature band | In the basement's above-freezing range this is usually `+/-0.4 C` maximum, unless data fall below `0 C`. |
| RH manufacturer accuracy | Each RH reading | Type B rectangular distribution using the manual's maximum accuracy for the current RH band | Use `+/-3.5% RH` in the central range where applicable; use the larger edge-band value near `0-10%` or `90-100% RH`. |
| Temperature quantization | CSV temperature | Type B rectangular half-width `0.05 C` | From one-decimal CSV output. |
| RH quantization | CSV RH | Type B rectangular half-width `0.05% RH` | From one-decimal CSV output. |
| Drift | Each physical sensor over time | Explicit estimated Type B component, initially sensitivity-only | No drift spec has been found in the project evidence. |
| Placement/microclimate | Sensor/location period | Separate scenario component, not a hidden sensor component | Especially important around the recorded sensor move and basement airflow changes. |
| Sensor-to-sensor bias | Cross-sensor comparisons | Scenario component or co-location estimate when available | Do not treat bedroom/living/basement sensors as perfectly interchangeable. |
| Autocorrelation | Time-window means/slopes | Effective sample size or block/bootstrap method | Do not divide by raw `sqrt(n)` for one-minute time series without checking autocorrelation. |

When a specification is stated only as a maximum error and gives no confidence level, a rectangular distribution is a conservative and transparent first choice: standard uncertainty `u = a / sqrt(3)`, where `a` is the half-width. Run sensitivity views using typical versus maximum manual accuracy if the visual conclusions depend on the choice.

At a representative `18 C`, `70% RH` reading, the established psychrometric equation gives about `10.7 g/m3` absolute humidity. Using only `+/-0.4 C` temperature max accuracy and `+/-3.5% RH` RH max accuracy as rectangular components gives a rough combined standard uncertainty near `0.34 g/m3`, or `U ~= 0.69 g/m3` at `k = 2`. This is an orientation check only, not a fixed project-wide interval; it varies with temperature, RH, and budget choices.

## Correlation And Cancellation Rules

Uncertainty propagation should not assume all readings are independent.

Use these defaults until better evidence exists:

- Within one sensor and one stable placement period, calibration bias and drift components are correlated across readings. They do not shrink when calculating a daily mean.
- For a change measured by the same sensor over a short period, some fixed bias cancels. Quantization and short-term noise do not fully cancel.
- Across different physical STH51 sensors, do not assume cancellation. Treat device-specific components as independent unless co-location data says otherwise.
- Across same-model sensors, some manufacturer/model uncertainty may be common-mode. Keep a sensitivity scenario for common RH or temperature offset when comparing rooms.
- RH and temperature from the same device may be coupled by the device's compensation algorithm, but the manual does not provide covariance. Start independent for point propagation, then add a sensitivity scenario if conclusions depend on fine distinctions.

In MetroloPy, correlation can be represented either by using a shared uncertain offset variable in multiple readings or by using its multivariate/covariance support. The shared-offset pattern is easier to audit in early project code:

```python
from math import sqrt
from metrolopy import gummy

temperature_bias_c = gummy(0, 0.4 / sqrt(3), unit="degC", name="STH51 temperature accuracy")
temperature_quantization_c = gummy(0, 0.05 / sqrt(3), unit="degC", name="CSV temperature quantization")

temperature_c = gummy(18.0, 0, unit="degC", name="temperature reading")
temperature_c = temperature_c + temperature_bias_c + temperature_quantization_c
```

For many readings from the same sensor, reuse the same `temperature_bias_c` object where the bias should be common. Create separate objects where components should be independent.

## Propagation Through Psychrometrics

The established physics ticket chose:

```text
e_s_pa = 611.2 * exp((17.62 * T_c) / (243.12 + T_c))
e_pa = (RH_pct / 100) * e_s_pa
absolute_humidity_g_m3 = 1000 * e_pa / (461.5 * (T_c + 273.15))
```

The uncertainty model should wrap `T_c` and `RH_pct` before these equations are evaluated. For ordinary basement conditions, this smooth nonlinear model is suitable for law-of-propagation checks. Monte Carlo should be used as a validation path when:

- RH is near `0%` or `100%`;
- dew point intervals are visibly asymmetric;
- values are clipped or constrained;
- the dashboard displays quantiles rather than symmetric `+/- U`;
- conclusions depend on close differences.

Dew point should inherit the same uncertainty treatment, but it should remain explanatory. Condensation-risk claims still require surface temperature, which is not currently measured.

## MetroloPy Use

MetroloPy is a good fit for the project, with boundaries:

- Use `gummy` values for point calculations with units and uncertainty.
- Use `u` for standard uncertainty internally; use `U`, `k`, or `p` only at reporting boundaries.
- Use `utype`/`name` labels or a parallel project budget table so assumptions remain visible.
- Use Budget tables for research/report artifacts, not as the only machine-readable record.
- Use Monte Carlo support to compare against linearized propagation for representative readings and edge cases.
- Keep uncertainty objects out of DuckDB/Polars storage at first. Store scalar estimates plus metadata, and reconstruct uncertainty objects at analysis/report boundaries.

Do not let MetroloPy make the assumptions disappear. The main project artifact should still expose the budget rows, chosen distributions, coverage factor, and source references.

## Reporting Rules

For chart/report values:

- Prefer "approximate 95% coverage interval" over "95% confidence interval" for Type B-heavy consumer-sensor outputs.
- Always state `k` or the Monte Carlo quantile method.
- Round values to match the uncertainty, not the raw CSV resolution.
- Show uncertainty bands for absolute humidity and derived summary metrics before adding them to every raw time-series point.
- Use event-bounded comparisons and state whether the comparison is same-sensor or cross-sensor.
- For rates and slopes, include missing-data handling, event boundaries, and autocorrelation/effective-sample-size assumptions.

## Implementation Shape

The next prototype should build a small uncertainty module with these functions:

- `sensor_temperature_budget(temperature_c, sensor_id, period_id) -> BudgetedQuantity`
- `sensor_relative_humidity_budget(relative_humidity_pct, sensor_id, period_id) -> BudgetedQuantity`
- `absolute_humidity_with_uncertainty(temperature, relative_humidity) -> BudgetedQuantity`
- `dew_point_with_uncertainty(temperature, relative_humidity) -> BudgetedQuantity`
- `coverage_interval(quantity, coverage_probability=0.95) -> CoverageInterval`

The project should keep a simple, serializable budget representation alongside MetroloPy objects. A later pipeline ticket can decide whether that representation is a dataclass, Polars struct, DuckDB table, or report-only object.

## Open Caveats

- The X-Sense material found so far is a consumer manual/spec, not calibration evidence for these three devices.
- No authoritative STH51 drift, long-term stability, hysteresis, response-time, or covariance information has been found.
- Placement and airflow effects may dominate sensor-spec uncertainty during intervention periods; they require event-aware analysis rather than purely metrological propagation.
- Weather, ventilation, and tank-volume uncertainty are separate model uncertainties and should not be folded into sensor measurement uncertainty without labels.

No new wayfinder tickets are needed from this resolution. [Prototype uncertainty bounds in report values and charts](../issues/08-prototype-uncertainty-bounds-in-report-values-and-charts.md) can now proceed, and [Prototype uncertainty-library pipeline integration](../issues/16-prototype-uncertainty-library-pipeline-integration.md) remains the right later place to decide how far MetroloPy objects should enter the production pipeline.
