# X-Sense STH51 Manual Notes

Source: X-Sense `STH51` user manual supplied by the user.

Local PDF copy: [Manual_STH51_20240506.pdf](Manual_STH51_20240506.pdf)

PDF metadata from local `pdfinfo` extraction:

- Created: `2024-05-09`
- Modified: `2024-05-09`
- Pages: 35
- Applies to: X-Sense `STH51` Smart Thermometer Hygrometer

These notes contain stable product and manual facts only. Project-specific sensor placement, inferred room labels, event history, and analysis decisions belong in the wayfinder issue tracker or analysis data files.

## Purchased Kit

User-confirmed kit: `3 Pack STH51 & 1 Base Station SBS50`.

Purchase listing:

- https://www.amazon.co.uk/dp/B0C5XDRN9B?ref_=ppx_hzsearch_conn_dt_b_fed_asin_title_1&th=1

Product/listing description supplied by the user: "X-Sense Smart WiFi Hygrometer Thermometer, Wireless Temperature Monitor Humidity Sensor with Notification Alert, Free Data Storage Export, Compatible with Alexa, for Greenhouse, Home, Office".

## Device Roles

- `STH51`: temperature and relative-humidity measuring sensor.
- `SBS50`: base station used for wireless connectivity and data delivery; not a temperature/RH measurement source in the current dataset.
- All three current CSV-producing sensors are user-confirmed to be the same `STH51` model.

## App And Export

- App named in the manual: X-Sense Home Security app.
- The manual describes CSV export after entering an email address and selecting the date/time range.
- The manual supports scheduled export options: daily, weekly, and monthly.
- The user's current setup exports CSV files daily to Gmail.

## Operating Range

| Property | Value |
| --- | --- |
| Operating temperature | `-20 C` to `60 C` |
| Operating humidity | `0% RH` to `100% RH` |

## Manufacturer Accuracy

Temperature accuracy:

| Range | Typical accuracy | Maximum accuracy |
| --- | --- | --- |
| `-20 C` to `0 C` | `+-0.2 C` | approximately `+-0.4 C` to `+-0.7 C` |
| `0 C` to `60 C` | `+-0.2 C` | `+-0.4 C` |

Humidity accuracy:

| Range | Typical accuracy | Maximum accuracy |
| --- | --- | --- |
| `0% RH` to `10% RH` | `+-2% RH` | `+-3.5% RH` |
| `10% RH` to `90% RH` | `+-2% RH` to `+-3% RH` | `+-3.5% RH` to `+-5% RH` |
| `90% RH` to `100% RH` | `+-2% RH` | `+-3.5% RH` |

The manual notes that humidity accuracy is measured at a constant `25 C`; if temperature changes, accuracy may be affected.

## Calibration Evidence Boundary

No sensor-specific calibration certificates are available for the three physical sensors.

Later measurement-uncertainty work should use the manufacturer specification as the documented evidence source, then add explicit estimated uncertainty components for effects not covered by the manual, including:

- sensor-to-sensor bias;
- drift;
- placement;
- airflow exposure;
- temperature-change effects on RH accuracy;
- CSV quantization or resolution.
