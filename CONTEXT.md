# Basement Dampness Analysis

This context defines the language for analysing basement dampness from thermohygrometer data, physical moisture models, and supporting explanatory material.

## Language

**Measurement uncertainty**:
Quantitative uncertainty associated with measurements and values derived from them, propagated through calculations such as averages, fits, and rate estimates using calibration data or explicit estimates.
_Avoid_: Caveats, error bars without a stated basis

**Caveat**:
Qualitative explanatory text that states limitations, tradeoffs, missing inputs, or interpretation risks in the chosen analysis approach.
_Avoid_: Measurement uncertainty

**Steady-state leaking**:
Ongoing moisture ingress that continues independently of short-term weather events and competes with the basement's drying process.
_Avoid_: Leak, dampness

**Weather-related leaking**:
Moisture ingress whose timing or rate is materially associated with rain or other outdoor weather conditions.
_Avoid_: Rain correlation

**Basement drying**:
Reduction over time in stored moisture in the basement walls, floor, air, and contents after active drying begins, separate from any additional moisture ingress.
_Avoid_: Dampness improvement

**Tank-full event**:
Moment when the dehumidifier's internal tank becomes full enough that water extraction may stop or the control behaviour changes.
_Avoid_: Tank emptied, dehumidifier off

**Tank-emptied event**:
Moment when the dehumidifier's internal tank is emptied and normal water extraction can resume if the unit had stopped or throttled because the tank was full.
_Avoid_: Tank full, maintenance

**STH51 thermohygrometer**:
The X-Sense temperature and relative-humidity sensor model that produced all three current CSV sensor datasets.
_Avoid_: Thermometer, hygrometer, generic sensor

**SBS50 base station**:
The X-Sense communication hub used by the STH51 thermohygrometers to connect and export data; it is not a temperature or relative-humidity measurement source in this dataset.
_Avoid_: Sensor, measuring device

**Manufacturer specification**:
Published model-level accuracy or operating information from the STH51 manual, used as evidence when sensor-specific calibration certificates are unavailable.
_Avoid_: Calibration certificate, measured calibration
