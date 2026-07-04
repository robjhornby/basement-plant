# Profile existing sensor data and prototype assumptions

Type: research
Status: resolved
Parent: ../map.md

## Question

What does the existing local dataset actually contain, and which prototype assumptions are supported, weak, or contradicted by the CSVs?

Inspect `data/*.csv`, `prototypes/basement_dehumidifier/prototype.py`, `prototypes/basement_dehumidifier/PRD.md`, `prototypes/basement_dehumidifier/NOTES.md`, and the generated report if useful. Produce a short markdown asset covering sensor count, date range, sampling cadence, missingness, column semantics, current inferred basement sensor, current inferred dehumidifier start, obvious intervention signatures, and risks in the rebound-rate heuristic.

## Answer

Research asset: [Existing sensor data and prototype assumptions](../research/02-existing-sensor-data-and-prototype-assumptions.md)

The dataset contains three one-minute thermohygrometer CSV exports with `Time`, `Temperature_Celsius`, and `Relative Humidity_Percent`, covering roughly `2026-02-13 19:46-19:51` through `2026-07-03 12:00`. The files have meaningful missingness, mostly April gaps of several hours to about a week, so production ingestion must treat gaps explicitly.

The prototype's basement-sensor inference is strongly supported: the unnumbered thermohygrometer has the highest median RH (`71.2%`) and lowest median temperature (`15.6 C`). The inferred dehumidifier boundary of `2026-07-01 18:25` is a defensible analysis boundary, but the CSVs more directly support active drying beginning around `2026-07-01 20:40`, when RH starts a large fall and temperature rises.

The rebound-rate heuristic is useful as an exploratory Basement drying signal, but weak as standalone evidence. It finds repeated drying/rebound cycles after the July 1 transition, with lower later rebound rates, but the result is confounded by unlabelled intervention events, possible sensor/fan/dehumidifier movement, weather/outdoor humidity, shorter later cycles, and data gaps.
