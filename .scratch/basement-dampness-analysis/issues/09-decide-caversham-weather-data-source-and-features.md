# Decide Caversham weather data source and features

Type: research
Status: resolved
Parent: ../map.md
Blocked by: 01

## Question

Which external weather data source should be used for Caversham, UK, and which weather features should feed the model or dashboard?

Compare practical sources for rainfall, outdoor temperature, outdoor relative humidity, and possibly pressure or wind. Evaluate historical availability, update cadence, cost, API friction, licensing, station proximity, and suitability for correlation with basement moisture behavior.

## Answer

Use Open-Meteo as the default external weather source for Caversham, with Environment Agency rainfall station `270397` as a local rain-gauge supplement.

The supporting research note is [Caversham weather data source and features](../research/09-caversham-weather-data-source-and-features.md).

The first pipeline should fetch hourly Open-Meteo data for approximately `51.47, -0.97`, `timezone=Europe/London`, with `temperature_2m`, `relative_humidity_2m`, `dew_point_2m`, `precipitation`, `rain`, `pressure_msl` or `surface_pressure`, `wind_speed_10m`, and `wind_direction_10m`. Use temperature/RH/dew point to derive outdoor absolute humidity and indoor-outdoor absolute-humidity differences. Use rain to build rolling totals and lag features against basement rebound/drying metrics.

Use Environment Agency station `270397` for 15-minute tipping-bucket rainfall readings. It is near the Caversham coordinate and returned readings for the current indoor-data window. Treat it as an observed local rainfall cross-check rather than exact house rainfall.

Do not use Met Office Weather DataHub for the first prototype: its observations are high quality but require account/API-key setup and the Land Observations product exposes only recent data. Reject Met Office DataPoint because it is decommissioned.

Weather claims in the dashboard should be caveated: Open-Meteo is gridded/reanalysis/model weather for a coordinate, while EA rainfall is a nearby gauge. Rain-correlated basement changes are evidence for follow-up investigation, not proof of moisture ingress.
