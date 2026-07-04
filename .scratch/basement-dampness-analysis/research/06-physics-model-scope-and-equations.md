# Physics Model Scope And Equations

This asset resolves [Establish physics model scope and equations](../issues/06-establish-physics-model-scope-and-equations.md). It defines the first defensible physical model for the basement dampness analysis and separates settled physics from assumptions that still need user input or later measurement.

## Recommendation

Use a small psychrometric core first:

1. Treat each STH51 reading as dry-bulb air temperature `T_c` in `degC` and relative humidity `RH_pct` in percent.
2. Convert `T_c` and `RH_pct` to water-vapour partial pressure `e_pa`, absolute humidity / vapour density `rho_v_g_m3`, and optionally dew point `T_dew_c`.
3. Use event-bounded periods from [Intervention, Room, And Device Context](04-intervention-room-and-device-context.md) before calculating averages, rates, or comparisons.
4. Use absolute humidity changes and rebound rates as the first quantitative moisture signal. Keep RH as a comfort/control and mould-risk context metric, not as the main cross-temperature comparison.
5. Use room air volume only for scale checks and later tank-volume consistency checks. Do not infer building-fabric water mass from air-water mass alone.
6. Keep a moisture mass-balance equation in the model vocabulary, but fit only simplified rates until ventilation, tank-water volume, and outdoor weather data are present.

## Settled Physics

### Relative humidity is a pressure ratio

Relative humidity should be interpreted as the ratio between water-vapour partial pressure and saturation vapour pressure at the same temperature:

```text
RH_pct = 100 * e_pa / e_s_pa(T_c)
e_pa = (RH_pct / 100) * e_s_pa(T_c)
```

NPL describes conversion between relative humidity and dew point as requiring the intermediate water-vapour pressure and saturation-vapour-pressure steps, not a direct conversion. Vaisala gives the same pressure-ratio definition. WMO-No. 8 is the canonical meteorological measurement reference for humidity observations.

Sources:

- NPL, [How do I convert between dew point and relative humidity?](https://www.npl.co.uk/resources/q-a/dew-point-and-relative-humidity)
- Vaisala, [The many faces of water vapor](https://www.vaisala.com/en/application-note/many-faces-of-water-vapor-relative-humidity-dewpoint-mixing-ratio)
- WMO, [Guide to Instruments and Methods of Observation, WMO-No. 8](https://community.wmo.int/site/knowledge-hub/programmes-and-initiatives/instruments-and-methods-of-observation-programme-imop/guide-instruments-and-methods-of-observation-wmo-no-8)

### Saturation vapour pressure

For current basement temperatures, use the Magnus formula over liquid water:

```text
T_c = temperature in degC
e_s_pa = 611.2 * exp((17.62 * T_c) / (243.12 + T_c))
```

This is directly aligned with the NPL formula. It is valid for the basement's expected above-freezing range and is close to the prototype's current formula:

```text
prototype: e_s_hpa = 6.112 * exp((17.67 * T_c) / (T_c + 243.5))
recommended: e_s_pa = 611.2 * exp((17.62 * T_c) / (243.12 + T_c))
```

The prototype calculation is therefore physically sound for a first pass, but the production code should name the formula, constants, units, and source explicitly.

### Absolute humidity / vapour density

Use the ideal-gas relation for water vapour:

```text
T_k = T_c + 273.15
R_v = 461.5 J kg^-1 K^-1
rho_v_kg_m3 = e_pa / (R_v * T_k)
rho_v_g_m3 = 1000 * e_pa / (R_v * T_k)
```

If `e` is in hPa, this is equivalent to the prototype's:

```text
rho_v_g_m3 = 216.7 * e_hpa / T_k
```

Use `rho_v_g_m3` as the main derived moisture metric for comparisons across temperature changes. This is the current prototype's strongest modelling choice.

### Dew point

Dew point is useful as an interpretive output, especially for condensation/surface-risk explanations, but it should not replace absolute humidity as the main analysis metric.

From the same Magnus formula:

```text
gamma = ln(e_pa / 611.2)
T_dew_c = 243.12 * gamma / (17.62 - gamma)
```

Only present dew point when the caveat is clear: condensation risk depends on surface temperature, which is not currently measured.

### Air water mass

With room air volume `V_m3`:

```text
M_air_g = rho_v_g_m3 * V_m3
delta_M_air_g = delta_rho_v_g_m3 * V_m3
```

Use the current geometric air volume as an approximate scale check:

```text
V_m3 ~= 3.12 * 3.07 * 1.83 ~= 17.5 m3
```

At `10 g/m3`, the air contains only about `175 g` of water vapour. A `3 g/m3` decrease in air moisture is only about `52 g` in the air. The MeacoDry Arete Two 25L tank holds `4.8 L`, and manufacturer extraction ratings are in litres per day, so most extracted water must come from reservoirs and ingress rather than the initial air water alone.

Sources:

- Project context, [Intervention, Room, And Device Context](04-intervention-room-and-device-context.md)
- Local manual notes, [MeacoDry Arete Two 20L/25L Manual Notes](../../../docs/reference/meaco-arete-two-25l-manual-notes.md)

## First-Pass Moisture Balance

Use this as the conceptual model:

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

Where:

- `M_air` is water vapour mass in basement air, preferably grams.
- `G_weather_related_leaking` is moisture ingress associated with rain or outdoor weather.
- `G_steady_state_leaking` is ongoing ingress not explained by short-term weather.
- `G_reservoir_release` is water released from walls, floor, and other building fabric during Basement drying.
- `G_ventilation` is net water-vapour exchange with outdoor or indoor air.
- `G_internal_exchange` covers unlogged door opening, household coupling, and mixing with the rest of the house.
- `R_dehumidifier` is water removed by the dehumidifier.
- `S_condensation_or_adsorption` is water leaving air into surfaces or materials.

Only a simplified version is identifiable from current data. The first implementation should estimate event-bounded means, slopes, cycle/rebound rates, and weather/context comparisons rather than fitting every term in this equation.

### Ventilation term

For later use, the direct outdoor ventilation term can be expressed as:

```text
Q_m3_h = air exchange flow rate
rho_v_out_g_m3 = outdoor absolute humidity
rho_v_in_g_m3 = basement absolute humidity
G_ventilation_g_h = Q_m3_h * (rho_v_out_g_m3 - rho_v_in_g_m3)
```

Current caveat: `Q_m3_h` is unknown, passive vents remain open, the extractor fan changed state at `2026-07-01 21:00`, and the door state is intentionally unlogged. Therefore, ventilation should be a caveated confounder in the first analysis, not a fitted physical parameter unless later evidence constrains it.

### Dehumidifier extraction

When tank water is measured:

```text
R_dehumidifier_kg_h ~= tank_water_litres / elapsed_hours
R_dehumidifier_g_h ~= 1000 * tank_water_litres / elapsed_hours
```

This assumes water density near `1 kg/L`, which is sufficient relative to current sensor and event uncertainty. Until tank volume and tank-full/tank-emptied events are logged, dehumidifier cycle patterns are evidence of control behaviour, not a measured extraction rate.

Manual performance ratings can be used as plausibility bounds, not as observed extraction:

- `15 L/day` at `27 C`, `60% RH`.
- `25 L/day` at `30 C`, `80% RH`.

The basement is cooler than those rating conditions, so actual extraction may be lower.

## What To Include In The First Defensible Model

Include now:

- `temperature_c`
- `relative_humidity_pct`
- `saturation_vapour_pressure_pa`
- `vapour_pressure_pa`
- `absolute_humidity_g_m3`
- `dew_point_c`, optional but useful for explanation
- event-bounded summary statistics
- uncertainty propagation hooks for sensor temperature and RH uncertainty
- explicit caveats for sensor-placement artifact, dehumidifier control-cycle artifact, ventilation, and missing weather

Use carefully:

- `air_water_mass_g`, only as a scale check with approximate `17.5 m3` volume
- dehumidifier on/off cycle durations and rebound rates, only within comparable event-bounded periods
- bedroom/living-room sensors as context for Whole-house humidity change, not perfect controls

Do not include yet:

- fitted wall/floor storage capacity
- fitted ventilation rate
- fitted steady-state leaking rate in physical units
- inferred dehumidifier litres removed from AH drops alone
- surface condensation prediction without surface temperature
- cross-placement before/after comparisons that ignore the `2026-07-02 14:40` sensor move

## Assumptions Needing User Input Or Later Measurement

The first implementation can proceed with explicit defaults, but these assumptions should remain visible:

- Effective basement air volume: start with `17.5 m3`; refine only if air-mass scale checks become important.
- Atmospheric pressure: use standard pressure or local weather-station pressure for any humidity-ratio work; absolute-humidity from vapour density does not need pressure.
- Ventilation rate and path: currently unknown because passive vents, door leakage, and extractor state all matter.
- Tank water volume: future tank-empty events should record approximate litres and time.
- Surface temperatures: needed before making condensation-risk claims.
- Sensor microclimate: post-move and pre-move sensor readings should not be merged for placement-sensitive claims without sensitivity checks.
- Outdoor absolute humidity and rainfall: required before distinguishing Weather-related leaking from Whole-house humidity change and Basement drying.

## Implementation Notes

- Prefer function names that carry units, for example `saturation_vapour_pressure_pa`, `vapour_pressure_pa`, and `absolute_humidity_g_m3`.
- Keep constants in one module with source comments.
- Validate the production equation against the existing prototype over typical basement conditions before replacing it.
- Store formula choice and source in report metadata so later uncertainty/report work can cite it.
- Treat missing data and event boundaries before resampling or fitting rates.

## Sources Checked

- NPL, [How do I convert between dew point and relative humidity?](https://www.npl.co.uk/resources/q-a/dew-point-and-relative-humidity)
- WMO, [Guide to Instruments and Methods of Observation, WMO-No. 8](https://community.wmo.int/site/knowledge-hub/programmes-and-initiatives/instruments-and-methods-of-observation-programme-imop/guide-instruments-and-methods-of-observation-wmo-no-8)
- PsychroLib, [API Documentation](https://psychrometrics.github.io/psychrolib/api_docs.html)
- Lawrence Berkeley National Laboratory, [CDL Psychrometrics](https://obc.lbl.gov/specification/cdl/latest/help/CDL_Psychrometrics.html)
- NOAA Air Resources Laboratory, [READY Moisture Calculator](https://www.ready.noaa.gov/READYmoistcal.php)
- Vaisala, [The many faces of water vapor](https://www.vaisala.com/en/application-note/many-faces-of-water-vapor-relative-humidity-dewpoint-mixing-ratio)
