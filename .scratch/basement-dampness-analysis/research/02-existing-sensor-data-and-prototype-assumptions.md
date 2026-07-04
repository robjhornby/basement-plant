# Existing sensor data and prototype assumptions

## Question

What does the existing local dataset actually contain, and which prototype assumptions are supported, weak, or contradicted by the CSVs?

## Sources

- `data/Thermo-hygrometer_Export Data_202601031200_202607031200.csv`
- `data/Thermo-hygrometer 2_Export Data_202601031200_202607031200.csv`
- `data/Thermo-hygrometer 3_Export Data_202601031200_202607031200.csv`
- `prototypes/basement_dehumidifier/prototype.py`
- `prototypes/basement_dehumidifier/PRD.md`
- `prototypes/basement_dehumidifier/NOTES.md`
- `prototypes/basement_dehumidifier/report.html`

## Dataset profile

The local dataset contains three CSV exports, each with the same schema:

- `Time`
- `Temperature_Celsius`
- `Relative Humidity_Percent`

The files are in reverse chronological file order, but parse cleanly when sorted by `Time`. All three sensors cover roughly `2026-02-13 19:46-19:51` through `2026-07-03 12:00`.

| Source file | Prototype location | Rows | Time range | Median cadence | Missing minutes estimate | Major gaps |
| --- | --- | ---: | --- | ---: | ---: | --- |
| `Thermo-hygrometer_Export Data_202601031200_202607031200.csv` | `Basement (inferred)` | 190,535 | `2026-02-13 19:46` to `2026-07-03 12:00` | 1 min | 10,600 | `2026-04-04 14:29` to `2026-04-10 23:30`; `2026-04-11 02:49` to `2026-04-11 12:30`; `2026-04-26 11:28` to `2026-04-26 22:16` |
| `Thermo-hygrometer 2_Export Data_202601031200_202607031200.csv` | `Location 2` | 190,256 | `2026-02-13 19:48` to `2026-07-03 12:00` | 1 min | 10,877 | `2026-04-04 14:29` to `2026-04-11 16:30`; `2026-04-26 14:16` to `2026-04-26 22:16` |
| `Thermo-hygrometer 3_Export Data_202601031200_202607031200.csv` | `Location 3` | 190,230 | `2026-02-13 19:51` to `2026-07-03 12:00` | 1 min | 10,900 | `2026-04-04 14:29` to `2026-04-11 15:30`; `2026-04-26 12:51` to `2026-04-26 22:16` |

Most missingness is concentrated in April. There are also small one-to-three-minute gaps and a shared `2026-03-29 00:59` to `2026-03-29 02:00` gap. Any production analysis should make gap handling explicit before estimating rates, cycle durations, or daily aggregates.

## Sensor summaries

The unnumbered sensor is clearly distinct from the other two: colder and much more humid by RH. It is only slightly higher than the other sensors by mean absolute humidity over the whole dataset, because its lower temperature reduces saturation capacity.

| Prototype location | Rows | Mean temp C | Median temp C | Mean RH % | Median RH % | Mean absolute humidity g/m3 |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| `Basement (inferred)` | 190,535 | 16.02 | 15.6 | 73.426 | 71.2 | 10.076 |
| `Location 2` | 190,256 | 20.74 | 19.6 | 52.699 | 54.4 | 9.635 |
| `Location 3` | 190,230 | 21.34 | 20.5 | 51.591 | 51.2 | 9.792 |

The current basement-sensor inference is supported by the CSVs. The prototype ranks locations by high median RH and low median temperature; the unnumbered export wins both criteria.

## Inferred dehumidifier start

The prototype infers `2026-07-01 18:25` as the dehumidifier-period start. This is a defensible analysis boundary but should not yet be treated as the confirmed physical install time.

The day-level basement data support a major transition around July 1-2:

| Day | Samples | Min RH % | Mean RH % | Max RH % | Mean temp C | Mean absolute humidity g/m3 |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| `2026-06-28` | 1,440 | 70.4 | 84.75 | 87.2 | 19.29 | 14.038 |
| `2026-06-29` | 1,440 | 83.2 | 86.84 | 89.6 | 18.05 | 13.371 |
| `2026-06-30` | 1,440 | 86.4 | 88.57 | 90.4 | 17.85 | 13.479 |
| `2026-07-01` | 1,440 | 55.2 | 85.69 | 90.4 | 18.06 | 13.145 |
| `2026-07-02` | 1,440 | 54.4 | 63.92 | 74.4 | 19.60 | 10.783 |
| `2026-07-03` | 721 | 55.2 | 63.03 | 68.0 | 18.32 | 9.859 |

The exact `18:25` boundary is weaker. Fifteen-minute basement bins remain near `89.6-90.2%` RH from `2026-07-01 17:30` through `20:30`. The first detected strong drying segment starts at `2026-07-01 20:40` and runs to `22:20`, taking RH from about `89.92%` to `57.76%` while temperature rises from the high `17.x C` range to above `20 C`.

Interpretation: the CSVs strongly support "active drying began on the evening of 2026-07-01" and support using `2026-07-01 18:25` as the prototype's post-period boundary. They do not independently prove that equipment was installed or switched on at exactly `18:25`.

## Obvious intervention signatures

The clearest intervention signature is the evening of `2026-07-01`:

- Before `20:40`, basement RH is near `90%` and temperature is flat around `17.7 C`.
- From `20:40` to `22:20`, RH drops by roughly `32 percentage points`; temperature rises by roughly `3 C`.
- Afterward, repeated drying/rebound cycles appear through the end of the file.

There is also a pre-dehumidifier anomaly on `2026-06-28`: basement RH reaches a daily minimum of `70.4%`, far below adjacent days, while the numbered sensors also show hot/dry conditions. This could be weather, ventilation, sensor placement, or another event. It should not be used as direct evidence of basement drying without weather/event context.

The April gaps are data availability signatures, not physical dampness signatures.

## Rebound-rate heuristic

The current heuristic detects cycles from smoothed five-minute samples and local extrema:

- peak-to-trough segments are labelled `drying`
- trough-to-peak segments are labelled `rebound`
- segments shorter than 15 minutes, longer than 8 hours, or with less than 3 percentage points RH change are filtered out

Against the current post-period data, it finds 71 segments: 36 drying and 35 rebound. Early rebound rates are visibly higher than later ones:

| Period | Rebound count | Median rebound absolute-humidity rate g/m3/hr | Median rebound duration |
| --- | ---: | ---: | ---: |
| First 12 hours after inferred start | 6 | 3.291 | 40 min |
| First 24 hours after inferred start | 17 | 3.065 | 40 min |
| Latest 12 hours in file | 12 | 2.151 | 20 min |
| First 36 hours in prototype report | 30 | 2.643 | 35 min |
| Latest 36 hours in prototype report | 34 | 2.414 | 35 min |

Supported: rebound absolute-humidity rate is a plausible exploratory indicator for basement drying because it uses off-cycle moisture return rather than only mean RH.

Weak: the detected later cycles are often shorter, and equipment/sensor movement is unlabelled. A lower rebound rate may reflect basement drying, but it may also reflect dehumidifier placement, fan airflow, sensor placement, control setpoint behavior, tank/drain behavior, or outdoor air changes.

Contradicted or at least overstated: treating the latest lower rebound rate as reliable evidence of reduced moisture ingress. The trend is directionally encouraging, not yet physically defensible.

## Implications for later tickets

- `Confirm intervention and sensor placement timeline` should pin down the actual dehumidifier install/switch-on time, fan addition, sensor movement, drain/tank behavior, and any known ventilation events around `2026-06-28` and `2026-07-01`.
- `Establish physics model scope and equations` should treat absolute humidity as useful but insufficient without air volume, exchange, dehumidifier extraction, surface moisture storage, and event context.
- `Design rain and pipe leak analysis strategy` should not use the current rebound heuristic alone as evidence for or against steady-state leaking or weather-related leaking.
- `Build weather-inclusive end-to-end prototype` should include gap-aware ingestion, event overlays, and weather/outdoor humidity before hardening any Basement drying claim.
