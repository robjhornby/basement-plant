# pyright: basic
"""PROTOTYPE — throwaway. Build theme-neutral chart payloads for the redesign mockups.

Reads the curated dataset snapshot in build/ticket-09-site/curated-data and writes
payloads.json next to this script. Run from the repo root:

    uv run python prototypes/site-redesign-mockups/build_payloads.py
"""

from __future__ import annotations

import json
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

from basement_analysis.curated_dataset import load_curated_dataset
from basement_analysis.static_site import chart_timestamp_seconds
from basement_analysis.summaries import (
    SENSOR_CHART_RECENT_DAYS,
    aggregate_sensor_readings_for_chart,
    series_points,
)

REPO_ROOT = Path(__file__).resolve().parents[2]
CURATED_DIR = REPO_ROOT / "build" / "ticket-09-site" / "curated-data"
OUTPUT_PATH = Path(__file__).resolve().parent / "payloads.json"
WEEK_SECONDS = 7 * 24 * 3600

Points = list[tuple[datetime, float]]


def union_chart(
    series_defs: list[dict[str, Any]],
    band_defs: list[dict[str, Any]],
) -> tuple[list[Any], list[dict[str, Any]], list[dict[str, Any]]]:
    """Merge per-series (timestamp, value) points onto one x grid, uPlot-style."""
    all_ts = sorted(
        {
            ts
            for definition in series_defs + band_defs
            for key in ("points", "lower_points", "upper_points")
            for ts, _v in definition.get(key, [])
        }
    )
    data: list[Any] = [[chart_timestamp_seconds(ts) for ts in all_ts]]
    series_out = []
    for definition in series_defs:
        by_ts = dict(definition["points"])
        data.append([by_ts.get(ts) for ts in all_ts])
        series_out.append(
            {
                "name": definition["name"],
                "role": definition["role"],
                "scale": definition["scale"],
                "kind": definition.get("kind", "line"),
                "digits": definition.get("digits", 1),
                "unit": definition.get("unit", ""),
            }
        )
    bands_out = []
    for definition in band_defs:
        lower_by_ts = dict(definition["lower_points"])
        upper_by_ts = dict(definition["upper_points"])
        bands_out.append(
            {
                "role": definition["role"],
                "scale": definition["scale"],
                "lower": [lower_by_ts.get(ts) for ts in all_ts],
                "upper": [upper_by_ts.get(ts) for ts in all_ts],
            }
        )
    return data, series_out, bands_out


def main() -> None:
    dataset = load_curated_dataset(CURATED_DIR)
    readings = dataset.sensor_readings
    dataset_end = max(r.timestamp for r in readings)
    chart_sensors = aggregate_sensor_readings_for_chart(
        readings, recent_start=dataset_end - timedelta(days=SENSOR_CHART_RECENT_DAYS)
    )

    def pts(location: str, metric: str, stat: str = "mean") -> Points:
        return series_points(chart_sensors, location, metric, statistic=stat)  # type: ignore[arg-type]

    events = [
        {"timestamp": chart_timestamp_seconds(e.timestamp), "description": e.description}
        for e in dataset.events
    ]

    # Hero: basement relative humidity + temperature + absolute humidity, one axis per measure.
    hero_series = [
        {
            "name": "Relative humidity",
            "role": "basementRh",
            "scale": "rh",
            "unit": "%",
            "points": pts("Basement", "relative_humidity_pct"),
        },
        {
            "name": "Temperature",
            "role": "basementTemp",
            "scale": "temp",
            "unit": "°C",
            "points": pts("Basement", "temperature_c"),
        },
        {
            "name": "Absolute humidity",
            "role": "basementAh",
            "scale": "ah",
            "unit": "g/m³",
            "points": pts("Basement", "absolute_humidity_g_m3"),
        },
    ]
    hero_bands = [
        {
            "role": "basementRh",
            "scale": "rh",
            "lower_points": pts("Basement", "relative_humidity_pct", "min"),
            "upper_points": pts("Basement", "relative_humidity_pct", "max"),
        },
        {
            "role": "basementTemp",
            "scale": "temp",
            "lower_points": pts("Basement", "temperature_c", "min"),
            "upper_points": pts("Basement", "temperature_c", "max"),
        },
        {
            "role": "basementAh",
            "scale": "ah",
            "lower_points": pts("Basement", "absolute_humidity_g_m3", "min"),
            "upper_points": pts("Basement", "absolute_humidity_g_m3", "max"),
        },
    ]
    hero_data, hero_series_out, hero_bands_out = union_chart(hero_series, hero_bands)
    hero = {
        "id": "hero",
        "title": "Basement conditions",
        "height": 340,
        "data": hero_data,
        "series": hero_series_out,
        "bands": hero_bands_out,
        "axes": [
            {"scale": "rh", "label": "Relative humidity / %", "side": "left"},
            {"scale": "temp", "label": "Temperature / °C", "side": "right"},
            {"scale": "ah", "label": "Absolute humidity / g/m³", "side": "right"},
        ],
        "events": events,
        "initialWindowSeconds": WEEK_SECONDS,
    }

    # Chart 2: basement vs outdoor absolute humidity, rainfall bars beneath.
    weather_points = [
        (h.timestamp, h.absolute_humidity_g_m3) for h in sorted(dataset.weather_hours, key=lambda h: h.timestamp)
    ]
    rain_by_hour: dict[datetime, float] = {}
    for reading in dataset.rain_readings:
        hour = reading.timestamp.replace(minute=0, second=0, microsecond=0)
        rain_by_hour[hour] = rain_by_hour.get(hour, 0.0) + reading.rainfall_mm
    rain_points = sorted(rain_by_hour.items())
    moisture_series = [
        {
            "name": "Basement absolute humidity",
            "role": "basementAh",
            "scale": "ah",
            "unit": "g/m³",
            "points": pts("Basement", "absolute_humidity_g_m3"),
        },
        {
            "name": "Outdoor absolute humidity",
            "role": "outdoorAh",
            "scale": "ah",
            "unit": "g/m³",
            "points": weather_points,
        },
        {
            "name": "Rainfall",
            "role": "rain",
            "scale": "rain",
            "unit": "mm per hour",
            "kind": "bar",
            "points": rain_points,
            "digits": 2,
        },
    ]
    moisture_bands = [
        {
            "role": "basementAh",
            "scale": "ah",
            "lower_points": pts("Basement", "absolute_humidity_g_m3", "min"),
            "upper_points": pts("Basement", "absolute_humidity_g_m3", "max"),
        },
    ]
    moisture_data, moisture_series_out, moisture_bands_out = union_chart(
        moisture_series, moisture_bands
    )
    moisture = {
        "id": "moisture",
        "title": "Basement versus outdoor moisture",
        "height": 320,
        "data": moisture_data,
        "series": moisture_series_out,
        "bands": moisture_bands_out,
        "axes": [
            {"scale": "ah", "label": "Absolute humidity / g/m³", "side": "left"},
            {"scale": "rain", "label": "Rainfall / mm per hour", "side": "right"},
        ],
        "events": events,
        "initialWindowSeconds": WEEK_SECONDS,
    }

    # Charts 3-5: basement vs bedroom vs living room, one chart per measure.
    room_locations = (
        ("Basement", "basementRh"),
        ("Bedroom", "bedroomRh"),
        ("Living room", "livingRoomRh"),
    )
    room_measures = (
        ("rooms-rh", "Room relative humidity", "relative_humidity_pct", "rh", "%"),
        ("rooms-temp", "Room temperature", "temperature_c", "temp", "°C"),
        ("rooms-ah", "Room absolute humidity", "absolute_humidity_g_m3", "ah", "g/m³"),
    )
    room_charts = []
    for chart_id, title, metric, scale, unit in room_measures:
        room_series = []
        room_bands = []
        for location, role in room_locations:
            room_series.append(
                {
                    "name": location,
                    "role": role,
                    "scale": scale,
                    "unit": unit,
                    "points": pts(location, metric),
                }
            )
            room_bands.append(
                {
                    "role": role,
                    "scale": scale,
                    "lower_points": pts(location, metric, "min"),
                    "upper_points": pts(location, metric, "max"),
                }
            )
        rooms_data, rooms_series_out, rooms_bands_out = union_chart(room_series, room_bands)
        measure_word = title.removeprefix("Room ").capitalize()
        room_charts.append(
            {
                "id": chart_id,
                "title": title,
                "height": 280,
                "data": rooms_data,
                "series": rooms_series_out,
                "bands": rooms_bands_out,
                "axes": [{"scale": scale, "label": f"{measure_word} / {unit}", "side": "left"}],
                "events": events,
                "initialWindowSeconds": WEEK_SECONDS,
            }
        )

    basement_latest = max(
        (r for r in readings if r.location == "Basement"), key=lambda r: r.timestamp
    )
    payload = {
        "latest": {
            "timestamp": basement_latest.timestamp.strftime("%d %b %Y, %H:%M"),
            "relative_humidity_pct": round(basement_latest.relative_humidity_pct, 1),
            "temperature_c": round(basement_latest.temperature_c, 1),
            "absolute_humidity_g_m3": round(basement_latest.absolute_humidity_g_m3, 1),
        },
        "charts": [hero, moisture, *room_charts],
    }
    def compact(value: Any) -> Any:
        if isinstance(value, float):
            rounded = round(value, 2)
            return int(rounded) if rounded == int(rounded) else rounded
        if isinstance(value, list):
            return [compact(item) for item in value]
        if isinstance(value, dict):
            return {key: compact(item) for key, item in value.items()}
        return value

    OUTPUT_PATH.write_text(json.dumps(compact(payload), separators=(",", ":")), encoding="utf-8")
    sizes = {c["id"]: len(c["data"][0]) for c in payload["charts"]}
    print(f"wrote {OUTPUT_PATH} ({OUTPUT_PATH.stat().st_size/1e6:.2f} MB), x-grid sizes {sizes}")


if __name__ == "__main__":
    main()
