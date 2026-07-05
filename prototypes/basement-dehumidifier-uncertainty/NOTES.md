# Basement Uncertainty Prototype Notes

Prototype status: throwaway.

Question answered: what would it look like to carry first-pass measurement uncertainty through key report values and show approximate 95% coverage intervals on charts?

One command:

```bash
uv run python prototypes/basement-dehumidifier-uncertainty/prototype.py
```

Output:

- `prototypes/basement-dehumidifier-uncertainty/report.html`

## Current Run

- Basement sensor: `Basement (inferred)`.
- Physical dehumidifier event: `2026-07-01 21:00`, loaded from `data/basement_events.csv`.
- Pre-install mean absolute humidity: `13.77 +/- 0.74 g/m3`.
- Post-install mean absolute humidity: `10.52 +/- 0.73 g/m3`.
- Same-sensor post-minus-pre change: `-3.25 +/- 0.09 g/m3`.
- Latest median rebound rate: `2.41 +/- 0.10 g/m3/hr`.

## Verdict

Uncertainty intervals are useful and legible for headline absolute-humidity values, daily mean absolute humidity, and rebound-rate points. The raw time-series band is readable at 15-minute grouping, but it should stay visually secondary because it can easily become chart clutter.

The most useful dashboard distinction is between absolute levels and same-sensor changes. Absolute mean humidity carries a visibly large interval from manufacturer RH accuracy, but a same-sensor pre/post change can be much tighter when fixed sensor accuracy is allowed to cancel. The UI should state that cancellation assumption clearly.

Rebound-rate intervals are meaningful enough to show, but they warn against over-reading small trend changes. On this short dataset, the latest rebound rate remains useful as a directional metric, not a decisive leak/no-leak result.

## Budget Used

- Temperature manufacturer accuracy: `+/-0.4 C`, rectangular Type B.
- Relative humidity manufacturer accuracy: `+/-3.5 %RH`, rectangular Type B.
- Temperature CSV quantization: `+/-0.05 C`, rectangular Type B.
- RH CSV quantization: `+/-0.05 %RH`, rectangular Type B.
- Coverage factor: `k = 2`, labelled as approximate 95% coverage interval.

## Important Limits

- Placement, airflow, drift, weather, ventilation, dehumidifier extraction, and moisture-reservoir model uncertainty are not included.
- Daily means do not divide fixed sensor accuracy by raw sample count; only quantization is treated as an independent reading component.
- Same-sensor change intervals assume common manufacturer accuracy components mostly cancel through sensitivity differences. Cross-sensor comparisons should not reuse that cancellation.
