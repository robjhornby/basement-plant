# Basement Dehumidifier Prototype Notes

Prototype status: throwaway.

Question answered: how far can the existing three thermohygrometer CSVs get toward a useful basement dampness dashboard without extra user input, room dimensions, or an events CSV?

One command:

```bash
uv run python prototypes/basement_dehumidifier/prototype.py
```

Output:

- `prototypes/basement_dehumidifier/report.html`

## Current Inference

- The basement sensor is inferred as `Thermo-hygrometer_Export Data_202601031200_202607031200.csv` because it has the highest humidity and lowest temperature.
- The dehumidifier signal is inferred to start at `2026-07-01 18:25`.
- The seven days before that inferred start average `86.78%` RH and `13.798 g/m3` absolute humidity.
- The post-start period through `2026-07-03 12:00` averages `65.28%` RH and `10.722 g/m3` absolute humidity.
- The headline improvement is therefore `-21.50 percentage points` RH and `-3.076 g/m3` absolute humidity.
- The first 36 hours after the inferred start have a median rebound rate of `2.643 g/m3/hr`.
- The latest 36 hours have a median rebound rate of `2.414 g/m3/hr`.

## Interpretation

This is directionally encouraging but not enough data for a leak/no-leak conclusion. The latest rebound rate is lower than the first 36-hour window, which suggests the room may be drying, but the window is short and confounded by dehumidifier movement, fan addition, and sensor movement.

The useful prototype metric is the off-cycle rebound rate after a drying trough. It uses absolute humidity rather than RH alone so temperature changes have less influence. This should remain more comparable across equipment placement and sensor movement than daily average RH, though major airflow/sensor changes still matter.

## Useful Next Inputs

- Exact dehumidifier install time, if known.
- Events CSV with timestamp, event type, and notes for dehumidifier movement, fan addition, sensor movement, windows/doors opened, and unusual weather.
- Approximate room dimensions and whether the room is open to other spaces.
- Dehumidifier model, target RH setting, and whether it drains continuously or stops when a tank fills.
- Sensor placement height and distance from dehumidifier/fan/walls before and after moves.

## Prototype Limits

- It uses heuristic cycle detection from local RH extrema, not a validated state model.
- It does not model outside weather, wall/floor moisture storage, air exchange, or dehumidifier extraction rate.
- It does not separate equipment/sensor events because those data are not present yet.
- It depends on Plotly.js from a CDN when viewing the generated HTML.
