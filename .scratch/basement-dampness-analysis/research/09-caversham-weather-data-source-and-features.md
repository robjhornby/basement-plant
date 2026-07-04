# Caversham weather data source and features

## Decision

Use Open-Meteo as the default external weather source for the first weather-inclusive basement prototype, and add Environment Agency rainfall station `270397` as a local rainfall cross-check.

Do not use Met Office Weather DataHub as the first prototype source. It is a useful later comparator for recent official station observations, but it needs account/API-key setup and its Land Observations product only exposes the past 48 hours. Do not use the old Met Office DataPoint API; it has been decommissioned.

## Recommended source contract

Fetch hourly Open-Meteo historical weather for Caversham/Reading coordinates, initially `latitude=51.47`, `longitude=-0.97`, with `timezone=Europe/London`.

Use these hourly fields:

- `temperature_2m`: outdoor air temperature for comparing indoor/outdoor thermal conditions.
- `relative_humidity_2m`: outdoor RH for context only; do not compare directly with basement RH without temperature correction.
- `dew_point_2m`: a stable outdoor moisture indicator and a useful check on absolute-humidity calculations.
- `precipitation` and `rain`: hourly wetting signal for correlation against basement moisture rebound or delayed ingress.
- `pressure_msl` or `surface_pressure`: optional diagnostic/context feature; keep it out of the first causal model unless it proves useful.
- `wind_speed_10m` and `wind_direction_10m`: optional ventilation/exposure proxies; useful if later evidence suggests wind-driven rain or wind-dependent air exchange.

Derive these local features in the pipeline:

- Outdoor absolute humidity, using the same formula as indoor readings.
- Outdoor vapour pressure or vapour-pressure deficit if the later physics/uncertainty work wants pressure-style terms.
- Indoor minus outdoor absolute humidity.
- Rolling rain totals over 1h, 3h, 6h, 12h, 24h, and 48h.
- Rain lag features against basement rebound/drying metrics, initially 0h to 72h.
- Weather period labels: dry, light rain, sustained rain, post-rain.

For rainfall, fetch EA station `270397` readings as 15-minute tipping-bucket rain in mm. A coordinate search around Caversham found station `270397` at about `51.44172, -0.937391`, roughly 3.7 km from `51.47, -0.97`, and a direct API request returned 15-minute readings for the current indoor-data window. Treat this as a gauge observation, not necessarily the exact rain at the house.

## Candidate comparison

### Open-Meteo

Best first choice.

- It supports coordinate-based historical weather requests through `/v1/archive`, with latitude/longitude, start/end date, hourly variables, units, and timezone parameters.
- It exposes the required model variables: temperature, relative humidity, dew point, precipitation/rain, pressure, wind speed, and wind direction.
- Its historical data combines observations with reanalysis/model output and fills gaps spatially, so it is continuous and easy to align with indoor sensor data.
- The documented historical datasets include hourly ECMWF IFS at 9 km from 2017 to present with 6-hour updates and no delay, plus ERA5 and ERA5-Land back to 1940/1950 with a 5-day delay.
- The free/open-access tier is adequate for prototyping: no API key for non-commercial evaluation, with published limits of 10,000 calls/day and 300,000 calls/month. Attribution is required because the weather data is CC BY 4.0.
- Main weakness: rain is gridded/modelled, not a house-local gauge. Use EA rainfall to validate/cross-check wetting episodes.

Primary sources:

- https://open-meteo.com/en/docs/historical-weather-api
- https://open-meteo.com/en/pricing

Verified prototype URL shape:

```text
https://archive-api.open-meteo.com/v1/archive?latitude=51.47&longitude=-0.97&start_date=2026-06-28&end_date=2026-07-03&hourly=temperature_2m,relative_humidity_2m,dew_point_2m,precipitation,rain,pressure_msl,surface_pressure,wind_speed_10m,wind_direction_10m&timezone=Europe%2FLondon
```

### Environment Agency rainfall API

Best rainfall supplement.

- It provides rainfall station metadata and readings without registration, under the Open Government Licence.
- Station searches support `lat`, `long`, and `dist`; station metadata includes WGS84 coordinates, grid reference, measures, period, and unit.
- Nearby station `270397` provides `rainfall-tipping_bucket_raingauge-t-15_min-mm`, i.e. 15-minute rainfall totals in mm.
- Readings are paged; ingestion should use `_limit`/`_offset` or date-windowed requests and should preserve source station id.
- Main weakness: it only covers rainfall. It cannot supply outdoor temperature/RH/dew point for moisture balance.

Primary source:

- https://environment.data.gov.uk/flood-monitoring/doc/rainfall

Verified station/search URL shapes:

```text
https://environment.data.gov.uk/flood-monitoring/id/stations?parameter=rainfall&lat=51.47&long=-0.97&dist=20
https://environment.data.gov.uk/flood-monitoring/id/stations/270397/readings?startdate=2026-06-28&enddate=2026-07-03
```

### Met Office Weather DataHub

Do not use for the first prototype.

- Land Observations are high-quality official ground-station observations, with maintained stations, hourly observations, and 9 parameters.
- The product is recent-only: past 48 hours, hourly update cadence, JSON delivery.
- It requires registration, subscription, and an API key header. Some plans are free up to limits, but the account/subscription flow is friction compared with Open-Meteo and EA open endpoints.
- It remains a good future comparator if the dashboard needs a named official observation station or if recent validation against official observations matters.

Primary sources:

- https://datahub.metoffice.gov.uk/docs/g/category/observations/overview
- https://datahub.metoffice.gov.uk/support/faqs

### Met Office DataPoint

Reject.

- The service is decommissioned and no longer available.

Primary source:

- https://www.metoffice.gov.uk/services/data/datapoint

## Suitability for basement dampness analysis

For the next end-to-end prototype, use Open-Meteo features for the continuous moisture balance and trend charts, then layer EA rainfall as an observed wetting event series. This gives a low-friction, reproducible pipeline that can run over the existing CSV history and update daily/hourly without credentials.

The dashboard should clearly label Open-Meteo values as gridded/reanalysis/model weather for the requested coordinate, not as a calibrated house-local weather station. Rainfall conclusions should prefer converging evidence: Open-Meteo rain plus EA station `270397` rain plus delayed changes in basement absolute-humidity rebound. A rain-correlated signal should be treated as a lead for further investigation, not proof of ingress.

## Implementation notes

- Store weather source metadata with every ingested row: provider, endpoint, latitude, longitude, timezone, fetch timestamp, model/source if returned, units, and station id where relevant.
- Keep weather times timezone-aware. Indoor CSV timestamps appear local; the first prototype should normalize to Europe/London before joining.
- Resample outdoor hourly weather to the indoor analysis cadence only after deriving hourly features; avoid pretending modelled weather has minute-level precision.
- Join EA 15-minute rainfall separately from Open-Meteo hourly rain, then create common rolling rainfall features.
- Cache raw API responses or normalized source tables so later analysis changes do not repeatedly call public APIs.
