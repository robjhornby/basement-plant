# Build weather-inclusive end-to-end prototype

Type: prototype
Status: resolved
Parent: ../map.md
Blocked by: 02, 09, 13, 14

## Question

What is the smallest local end-to-end prototype that loads the basement sensor CSVs, adds local weather/outdoor humidity data, runs the first useful calculations, and generates locally viewable static web pages quickly enough to support iterative modelling decisions?

Build this after the existing data/prototype assumptions are profiled, the Caversham weather source is chosen, the local static site views are defined, and the Python project baseline is in place. It should prioritize fast feedback from visible data and calculations over deep physical modelling. Use it to help decide later how much modelling sophistication is justified.

Use `data/basement_events.csv` as a first-class input. The prototype should overlay events on plots and calculate metrics within event-bounded periods rather than relying on the old inferred dehumidifier boundary or broad first/latest windows that cross fan, sensor-placement, and dehumidifier-orientation changes.

Use [Intervention, Room, And Device Context](../research/04-intervention-room-and-device-context.md) for sensor labels, room/device context, event-period definitions, and caveats to display or preserve in generated outputs.

Do not include SES, S3, Gmail forwarding, `robjhornby.com` publishing, Cloudflare Pages, AWS deployment, or server automation in this prototype. Those are later-phase work after the local CSV-to-static-site flow is useful.

## Answer

The smallest useful local end-to-end prototype is now the package command:

```bash
uv run basement
```

It loads the three local thermohygrometer CSV exports from `data/`, treats `data/basement_events.csv` as a first-class event-boundary input, fetches and caches Open-Meteo hourly outdoor temperature/RH/dew point/rain for Caversham, fetches and caches Environment Agency station `270397` rainfall readings, derives absolute humidity for indoor and outdoor readings, calculates event-bounded period metrics, and writes a self-contained static dashboard to:

```text
build/basement-site/index.html
```

The implementation lives in `src/basement_analysis/static_site.py`, with the CLI in `src/basement_analysis/cli.py`. `README.md` documents the command and the `--refresh-weather` option.

The generated dashboard includes:

- latest run/data freshness cards;
- basement RH and absolute-humidity summary values;
- outdoor absolute humidity and indoor-minus-outdoor absolute humidity;
- Environment Agency rainfall total for available readings;
- cautious hypothesis evidence for basement drying, weather-related leaking, and steady-state leaking;
- daily basement trends;
- basement-versus-outdoor moisture chart;
- EA rainfall chart;
- raw RH context for basement, bedroom, and living-room sensors;
- event-bounded period metrics keyed to the current intervention timeline.

This prototype deliberately keeps modelling shallow. It is useful enough for fast local iteration and exposes the next structural question: how the static dashboard and the physics/metrology report should share calculated summary objects without duplicating analysis logic.

Verification:

```bash
uv run basement --refresh-weather
uv run ruff format --check .
uv run ruff check .
uv run pyright
uv run pytest
```

All verification commands passed. A temporary localhost browser render of `build/basement-site/index.html` also showed the cards, SVG charts, and event-bounded table rendering coherently.
