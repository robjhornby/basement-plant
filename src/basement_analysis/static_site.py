from __future__ import annotations

import csv
import html
import json
import math
import re
import shutil
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import date, datetime
from functools import lru_cache
from pathlib import Path
from typing import cast
from urllib.parse import urlencode
from urllib.request import urlopen
from zoneinfo import ZoneInfo

from basement_analysis.curated_dataset import (
    CuratedDataRoot,
    join_curated_data_path,
    load_curated_dataset,
    write_curated_dataset,
)
from basement_analysis.observability import PhaseRecorder
from basement_analysis.summaries import (
    ENVIRONMENT_AGENCY_RAIN_STATION,
    ChartSeries,
    ChartSpec,
    Event,
    PeriodSummary,
    RainChartSpec,
    RainReading,
    SensorReading,
    SiteAnalysisSummary,
    WeatherHour,
    absolute_humidity_g_m3,
    build_site_analysis_summary,
)

CAVERSHAM_LATITUDE = 51.47
CAVERSHAM_LONGITUDE = -0.97
LOCAL_TIMEZONE = "Europe/London"
LATEST_CHART_WINDOW_SECONDS = 7 * 24 * 60 * 60
VENDORED_UPLOT_DIR = Path(__file__).parent / "vendor" / "uplot"
SITE_ASSETS_DIR = Path(__file__).parent / "site_assets" / "frutiger_aero" / "derived"
FRUTIGER_AERO_ASSET_PREFIX = "assets/frutiger-aero"
# Aero palette roles keyed by (chart title, series name): the prototype's single-measure
# room charts colour the basement series with the shared basement blue (`basementRh`), not
# the hero chart's temperature orange, so one series name can need different roles per chart.
AERO_CHART_SERIES_ROLES = {
    ("Basement conditions", "Relative humidity"): "basementRh",
    ("Basement conditions", "Temperature"): "basementTemp",
    ("Absolute humidity", "Basement"): "basementAh",
    ("Absolute humidity", "Bedroom"): "bedroom",
    ("Absolute humidity", "Living room"): "livingRoom",
    ("Absolute humidity", "Outdoor"): "outdoorAh",
    ("Absolute humidity", "Rainfall"): "rain",
    ("Temperature", "Basement"): "basementRh",
    ("Temperature", "Bedroom"): "bedroom",
    ("Temperature", "Living room"): "livingRoom",
    ("Temperature", "Outdoor"): "outdoor",
    ("Relative humidity", "Basement"): "basementRh",
    ("Relative humidity", "Bedroom"): "bedroom",
    ("Relative humidity", "Living room"): "livingRoom",
    ("Relative humidity", "Outdoor"): "outdoor",
}

type JsonValue = None | bool | int | float | str | list[JsonValue] | dict[str, JsonValue]

SENSOR_FILE_LABELS = {
    "Thermo-hygrometer_Export Data_202601031200_202607031200.csv": "Basement",
    "Thermo-hygrometer 2_Export Data_202601031200_202607031200.csv": "Bedroom",
    "Thermo-hygrometer 3_Export Data_202601031200_202607031200.csv": "Living room",
}
SENSOR_FILENAME_LABEL_PATTERNS = (
    (re.compile(r"^Thermo-hygrometer_Export Data_.*\.csv$"), "Basement"),
    (re.compile(r"^Thermo-hygrometer 2_Export Data_.*\.csv$"), "Bedroom"),
    (re.compile(r"^Thermo-hygrometer 3_Export Data_.*\.csv$"), "Living room"),
)


@dataclass(frozen=True)
class BuildResult:
    index_path: Path
    private_report_path: Path | None
    curated_dataset_dir: CuratedDataRoot
    sensor_row_count: int
    weather_hour_count: int
    rain_reading_count: int
    newest_sensor_reading: datetime


def parse_local_datetime(raw_value: str) -> datetime:
    return datetime.strptime(raw_value, "%Y/%m/%d %H:%M")


def format_timestamp(timestamp: datetime) -> str:
    return timestamp.strftime("%Y-%m-%d %H:%M")


def format_optional_float(value: float | None, digits: int = 2) -> str:
    if value is None or not math.isfinite(value):
        return "n/a"
    return f"{value:.{digits}f}"


def slugify_identifier(value: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")
    return slug or "chart"


def aero_chart_series_role(chart_title: str, series_name: str) -> str:
    return AERO_CHART_SERIES_ROLES.get((chart_title, series_name), slugify_identifier(series_name))


@lru_cache(maxsize=1)
def load_uplot_javascript() -> str:
    return (VENDORED_UPLOT_DIR / "uPlot.iife.min.js").read_text(encoding="utf-8")


@lru_cache(maxsize=1)
def load_uplot_css() -> str:
    return (VENDORED_UPLOT_DIR / "uPlot.min.css").read_text(encoding="utf-8")


def render_json_script(script_id: str, payload: Mapping[str, JsonValue]) -> str:
    serialized_payload = (
        json.dumps(payload, ensure_ascii=False, separators=(",", ":"))
        .replace("<", "\\u003c")
        .replace(">", "\\u003e")
    )
    return (
        f'<script type="application/json" id="{html.escape(script_id)}">'
        f"{serialized_payload}</script>"
    )


def chart_timestamp_seconds(timestamp: datetime) -> int:
    local_zone = ZoneInfo(LOCAL_TIMEZONE)
    aware_timestamp = (
        timestamp.replace(tzinfo=local_zone)
        if timestamp.tzinfo is None
        else timestamp.astimezone(local_zone)
    )
    return round(aware_timestamp.timestamp())


def chart_value(value: float | None) -> float | None:
    # Chart tooltips show 2 decimals; 3 keeps a guard digit while avoiding
    # full float64 repr precision, which dominates inline payload weight.
    return None if value is None else round(value, 3)


def load_sensor_readings(data_dir: Path) -> list[SensorReading]:
    readings: list[SensorReading] = []
    for csv_path in sorted(data_dir.rglob("Thermo-hygrometer*.csv")):
        location = sensor_location_for_filename(csv_path.name)
        with csv_path.open(newline="", encoding="utf-8-sig") as csv_file:
            reader = csv.DictReader(csv_file)
            for row in reader:
                timestamp = parse_local_datetime(required_csv_value(row, "Time"))
                temperature_c = float(required_csv_value(row, "Temperature_Celsius"))
                relative_humidity_pct = float(required_csv_value(row, "Relative Humidity_Percent"))
                readings.append(
                    SensorReading(
                        timestamp=timestamp,
                        location=location,
                        temperature_c=temperature_c,
                        relative_humidity_pct=relative_humidity_pct,
                        absolute_humidity_g_m3=absolute_humidity_g_m3(
                            temperature_c, relative_humidity_pct
                        ),
                    )
                )
    return sorted(readings, key=lambda reading: (reading.location, reading.timestamp))


def sensor_location_for_filename(filename: str) -> str:
    if filename in SENSOR_FILE_LABELS:
        return SENSOR_FILE_LABELS[filename]
    normalized_filename = re.sub(r"[_\s]+", " ", filename)
    if normalized_filename.startswith("Thermo-hygrometer Export Data "):
        return "Basement"
    if normalized_filename.startswith("Thermo-hygrometer 2 Export Data "):
        return "Bedroom"
    if normalized_filename.startswith("Thermo-hygrometer 3 Export Data "):
        return "Living room"
    for pattern, label in SENSOR_FILENAME_LABEL_PATTERNS:
        if pattern.match(filename):
            return label
    return Path(filename).stem.split("_Export", 1)[0]


def required_csv_value(row: dict[str, str | None], key: str) -> str:
    value = row.get(key)
    if value is None:
        raise ValueError(f"Missing required CSV column {key!r}")
    return value


def load_events(data_dir: Path) -> list[Event]:
    events_path = data_dir / "basement_events.csv"
    events: list[Event] = []
    with events_path.open(newline="", encoding="utf-8-sig") as csv_file:
        reader = csv.DictReader(csv_file)
        for row in reader:
            events.append(
                Event(
                    timestamp=parse_local_datetime(required_csv_value(row, "Time")),
                    description=required_csv_value(row, "Event"),
                )
            )
    return sorted(events, key=lambda event: event.timestamp)


def fetch_json(cache_path: Path, url: str, refresh: bool) -> dict[str, object]:
    if cache_path.exists() and not refresh:
        with cache_path.open(encoding="utf-8") as cache_file:
            return cast(dict[str, object], json.load(cache_file))

    cache_path.parent.mkdir(parents=True, exist_ok=True)
    with urlopen(url, timeout=30) as response:
        payload = cast(dict[str, object], json.load(response))
    with cache_path.open("w", encoding="utf-8") as cache_file:
        json.dump(payload, cache_file, indent=2, sort_keys=True)
    return payload


def fetch_open_meteo_weather(
    start_date: date,
    end_date: date,
    cache_dir: Path,
    refresh: bool,
) -> list[WeatherHour]:
    query = urlencode(
        {
            "latitude": CAVERSHAM_LATITUDE,
            "longitude": CAVERSHAM_LONGITUDE,
            "start_date": start_date.isoformat(),
            "end_date": end_date.isoformat(),
            "hourly": ",".join(
                [
                    "temperature_2m",
                    "relative_humidity_2m",
                    "dew_point_2m",
                    "precipitation",
                    "rain",
                ]
            ),
            "timezone": LOCAL_TIMEZONE,
        }
    )
    url = f"https://archive-api.open-meteo.com/v1/archive?{query}"
    cache_path = cache_dir / f"open_meteo_{start_date.isoformat()}_{end_date.isoformat()}.json"
    payload = fetch_json(cache_path, url, refresh)
    hourly = cast(dict[str, Sequence[object]], payload["hourly"])

    times = cast(Sequence[str], hourly["time"])
    temperatures = nullable_numeric_sequence(hourly["temperature_2m"])
    relative_humidities = nullable_numeric_sequence(hourly["relative_humidity_2m"])
    dew_points = nullable_numeric_sequence(hourly["dew_point_2m"])
    precipitation = nullable_numeric_sequence(hourly["precipitation"])
    rain = nullable_numeric_sequence(hourly["rain"])

    weather_hours: list[WeatherHour] = []
    for index, raw_time in enumerate(times):
        temperature_c = temperatures[index]
        relative_humidity_pct = relative_humidities[index]
        dew_point_c = dew_points[index]
        precipitation_mm = precipitation[index]
        rain_mm = rain[index]
        if (
            temperature_c is None
            or relative_humidity_pct is None
            or dew_point_c is None
            or precipitation_mm is None
            or rain_mm is None
        ):
            # The archive API returns nulls for hours it has not backfilled yet; a fabricated
            # 0°C/0%RH reading would poison the curated history, so drop the hour instead.
            continue
        weather_hours.append(
            WeatherHour(
                timestamp=datetime.fromisoformat(raw_time),
                temperature_c=temperature_c,
                relative_humidity_pct=relative_humidity_pct,
                dew_point_c=dew_point_c,
                precipitation_mm=precipitation_mm,
                rain_mm=rain_mm,
                absolute_humidity_g_m3=absolute_humidity_g_m3(temperature_c, relative_humidity_pct),
            )
        )
    return weather_hours


def nullable_numeric_sequence(values: Sequence[object]) -> list[float | None]:
    result: list[float | None] = []
    for value in values:
        if isinstance(value, int | float):
            result.append(float(value))
        elif value is None:
            result.append(None)
        else:
            raise TypeError(f"Expected numeric API value, got {value!r}")
    return result


def fetch_environment_agency_rainfall(
    start_date: date,
    end_date: date,
    cache_dir: Path,
    refresh: bool,
) -> list[RainReading]:
    query = urlencode(
        {
            "startdate": start_date.isoformat(),
            "enddate": end_date.isoformat(),
            "_limit": 10000,
        }
    )
    url = (
        "https://environment.data.gov.uk/flood-monitoring/id/stations/"
        f"{ENVIRONMENT_AGENCY_RAIN_STATION}/readings?{query}"
    )
    cache_path = (
        cache_dir / f"environment_agency_{ENVIRONMENT_AGENCY_RAIN_STATION}_"
        f"{start_date.isoformat()}_{end_date.isoformat()}.json"
    )
    payload = fetch_json(cache_path, url, refresh)
    raw_items = cast(Sequence[dict[str, object]], payload.get("items", []))
    local_zone = ZoneInfo(LOCAL_TIMEZONE)
    readings: list[RainReading] = []
    for item in raw_items:
        raw_timestamp = item.get("dateTime")
        raw_value = item.get("value")
        if not isinstance(raw_timestamp, str) or not isinstance(raw_value, int | float):
            continue
        aware_timestamp = datetime.fromisoformat(raw_timestamp.replace("Z", "+00:00"))
        local_timestamp = aware_timestamp.astimezone(local_zone).replace(tzinfo=None)
        readings.append(RainReading(timestamp=local_timestamp, rainfall_mm=float(raw_value)))
    return sorted(readings, key=lambda reading: reading.timestamp)


def render_time_series_svg(
    series: Sequence[ChartSeries],
    events: Sequence[Event],
    y_label: str,
    height: int = 320,
) -> str:
    all_points = [point for chart_series in series for point in chart_series.points]
    if not all_points:
        return '<div class="empty">No data available.</div>'

    width = 1040
    left = 58
    right = 18
    top = 22
    bottom = 42
    plot_width = width - left - right
    plot_height = height - top - bottom
    min_time = min(timestamp for timestamp, _value in all_points)
    max_time = max(timestamp for timestamp, _value in all_points)
    min_value = min(value for _timestamp, value in all_points)
    max_value = max(value for _timestamp, value in all_points)
    if math.isclose(min_value, max_value):
        min_value -= 1.0
        max_value += 1.0
    padding = (max_value - min_value) * 0.08
    min_value -= padding
    max_value += padding

    def x_for(timestamp: datetime) -> float:
        total_seconds = (max_time - min_time).total_seconds()
        if total_seconds <= 0:
            return left
        elapsed_seconds = (timestamp - min_time).total_seconds()
        return left + (elapsed_seconds / total_seconds) * plot_width

    def y_for(value: float) -> float:
        return top + ((max_value - value) / (max_value - min_value)) * plot_height

    y_ticks = [min_value + ((max_value - min_value) * fraction / 4) for fraction in range(5)]
    grid_lines = "\n".join(
        (
            f'<line class="grid" x1="{left}" x2="{width - right}" '
            f'y1="{y_for(value):.1f}" y2="{y_for(value):.1f}" />'
            f'<text class="axis-label" x="{left - 8}" y="{y_for(value) + 4:.1f}" '
            f'text-anchor="end">{value:.1f}</text>'
        )
        for value in y_ticks
    )

    event_lines = "\n".join(
        (
            f'<line class="event-line" x1="{x_for(event.timestamp):.1f}" '
            f'x2="{x_for(event.timestamp):.1f}" y1="{top}" y2="{height - bottom}" />'
        )
        for event in events
        if min_time <= event.timestamp <= max_time
    )

    polylines = "\n".join(
        (
            f'<polyline class="series-line" stroke="{chart_series.color}" points="'
            + " ".join(
                f"{x_for(timestamp):.1f},{y_for(value):.1f}"
                for timestamp, value in chart_series.points
            )
            + f'"><title>{html.escape(chart_series.name)}</title></polyline>'
        )
        for chart_series in series
        if chart_series.points
    )
    legend_items = "".join(
        (
            '<span class="legend-item">'
            f'<span class="legend-swatch" style="background:{chart_series.color}"></span>'
            f"{html.escape(chart_series.name)}</span>"
        )
        for chart_series in series
    )

    escaped_y_label = html.escape(y_label)
    return f"""
    <div class="legend">{legend_items}</div>
    <svg class="chart" viewBox="0 0 {width} {height}" role="img"
      aria-label="{escaped_y_label}">
      <rect class="plot-bg" x="{left}" y="{top}" width="{plot_width}" height="{plot_height}" />
      {grid_lines}
      {event_lines}
      {polylines}
      <line class="axis" x1="{left}" x2="{width - right}"
        y1="{height - bottom}" y2="{height - bottom}" />
      <line class="axis" x1="{left}" x2="{left}" y1="{top}" y2="{height - bottom}" />
      <text class="axis-title" x="{left}" y="{height - 10}">{format_timestamp(min_time)}</text>
      <text class="axis-title" x="{width - right}" y="{height - 10}" text-anchor="end">
        {format_timestamp(max_time)}
      </text>
      <text class="axis-title" transform="translate(16 {height / 2:.1f}) rotate(-90)"
        text-anchor="middle">{escaped_y_label}</text>
    </svg>
    """


def render_chart_spec(chart: ChartSpec) -> str:
    fallback_html = '<p class="empty">Enable JavaScript to view the interactive chart.</p>'
    return render_uplot_time_series_chart(chart=chart, fallback_html=fallback_html)


def render_rain_svg_fallback(rain_chart: RainChartSpec) -> str:
    points = rain_chart.hourly_points
    if not points:
        return '<div class="empty">No Environment Agency rainfall readings available.</div>'

    height = rain_chart.height
    width = 1040
    left = 58
    right = 18
    top = 18
    bottom = 36
    plot_width = width - left - right
    plot_height = height - top - bottom
    min_time = points[0][0]
    max_time = points[-1][0]
    max_value = max(value for _timestamp, value in points) or 1.0
    bar_width = max(1.0, plot_width / len(points))

    def x_for(timestamp: datetime) -> float:
        total_seconds = (max_time - min_time).total_seconds()
        if total_seconds <= 0:
            return left
        return left + ((timestamp - min_time).total_seconds() / total_seconds) * plot_width

    bars = "\n".join(
        (
            f'<rect class="rain-bar" x="{x_for(timestamp):.1f}" '
            f'y="{top + plot_height - ((value / max_value) * plot_height):.1f}" '
            f'width="{bar_width:.1f}" height="{(value / max_value) * plot_height:.1f}" />'
        )
        for timestamp, value in points
    )
    return f"""
    <svg class="chart short-chart" viewBox="0 0 {width} {height}" role="img" aria-label="Rainfall">
      <rect class="plot-bg" x="{left}" y="{top}" width="{plot_width}" height="{plot_height}" />
      {bars}
      <line class="axis" x1="{left}" x2="{width - right}"
        y1="{height - bottom}" y2="{height - bottom}" />
      <line class="axis" x1="{left}" x2="{left}" y1="{top}" y2="{height - bottom}" />
      <text class="axis-label" x="{left - 8}" y="{top + 4}" text-anchor="end">{max_value:.1f}</text>
      <text class="axis-label" x="{left - 8}" y="{height - bottom + 4}" text-anchor="end">0</text>
      <text class="axis-title" x="{left}" y="{height - 8}">{format_timestamp(min_time)}</text>
      <text class="axis-title" x="{width - right}" y="{height - 8}" text-anchor="end">
        {format_timestamp(max_time)}
      </text>
      <text class="axis-title" transform="translate(16 {rain_chart.height / 2:.1f}) rotate(-90)"
        text-anchor="middle">{html.escape(rain_chart.y_label)}</text>
    </svg>
    """


def render_rain_chart_spec(rain_chart: RainChartSpec) -> str:
    fallback_html = '<p class="empty">Enable JavaScript to view the rainfall chart.</p>'
    return render_uplot_rain_chart(rain_chart=rain_chart, fallback_html=fallback_html)


def render_uplot_time_series_chart(chart: ChartSpec, fallback_html: str) -> str:
    all_timestamps = sorted(
        {
            timestamp
            for chart_series in chart.series
            for timestamp, _value in (
                chart_series.points + chart_series.min_points + chart_series.max_points
            )
        }
    )
    if not all_timestamps:
        return '<div class="empty">No data available.</div>'

    data: list[JsonValue] = [[chart_timestamp_seconds(timestamp) for timestamp in all_timestamps]]
    series_payload: list[JsonValue] = []
    bands_payload: list[JsonValue] = []
    for chart_series in chart.series:
        values_by_timestamp = dict(chart_series.points)
        data.append(
            [chart_value(values_by_timestamp.get(timestamp)) for timestamp in all_timestamps]
        )
        series_payload.append(
            {
                "name": chart_series.name,
                "role": aero_chart_series_role(chart.title, chart_series.name),
                "color": chart_series.color,
                "kind": chart_series.kind,
                "unit": chart_series.unit,
                "scale": chart_series.scale,
                "digits": 2 if chart_series.kind == "bar" else 1,
            }
        )
        if chart_series.min_points and chart_series.max_points:
            min_values_by_timestamp = dict(chart_series.min_points)
            max_values_by_timestamp = dict(chart_series.max_points)
            bands_payload.append(
                {
                    "name": chart_series.name,
                    "role": aero_chart_series_role(chart.title, chart_series.name),
                    "color": chart_series.color,
                    "scale": chart_series.scale,
                    "lower": [
                        chart_value(min_values_by_timestamp.get(timestamp))
                        for timestamp in all_timestamps
                    ],
                    "upper": [
                        chart_value(max_values_by_timestamp.get(timestamp))
                        for timestamp in all_timestamps
                    ],
                }
            )

    event_payload: list[JsonValue] = [
        {
            "timestamp": chart_timestamp_seconds(event.timestamp),
            "description": event.description,
        }
        for event in chart.event_markers
    ]
    chart_id = f"chart-{slugify_identifier(chart.title)}"
    covered_scales = {axis.scale for axis in chart.axes}
    payload: dict[str, JsonValue] = {
        "id": chart_id,
        "title": chart.title,
        "axes": [
            *[
                {
                    "scale": axis.scale,
                    "label": axis.label,
                    "side": axis.side,
                    "show": axis.show,
                    "size": 56 if axis.show else 0,
                }
                for axis in chart.axes
            ],
            *[
                {"scale": scale, "label": "", "side": "right", "show": False, "size": 0}
                for scale in sorted(
                    {series.scale for series in chart.series if series.scale not in covered_scales}
                )
            ],
        ],
        "height": chart.height,
        "data": data,
        "series": series_payload,
        "bands": bands_payload,
        "events": event_payload,
        "initialWindowSeconds": LATEST_CHART_WINDOW_SECONDS,
    }
    return render_interactive_chart(payload=payload, fallback_html=fallback_html)


def render_uplot_rain_chart(rain_chart: RainChartSpec, fallback_html: str) -> str:
    points = rain_chart.hourly_points
    if not points:
        return '<div class="empty">No Environment Agency rainfall readings available.</div>'

    chart_id = f"chart-{slugify_identifier(rain_chart.title)}"
    payload: dict[str, JsonValue] = {
        "id": chart_id,
        "title": rain_chart.title,
        "height": rain_chart.height,
        "data": [
            [chart_timestamp_seconds(timestamp) for timestamp, _value in points],
            [chart_value(value) for _timestamp, value in points],
        ],
        "series": [
            {
                "name": "Rainfall",
                "role": "rain",
                "color": "#2563eb",
                "kind": "bar",
                "unit": "mm per hour",
                "scale": "y",
                "digits": 2,
            }
        ],
        "axes": [
            {"scale": "y", "label": rain_chart.y_label, "side": "left", "show": True, "size": 56}
        ],
        "bands": [],
        "events": [],
        "initialWindowSeconds": LATEST_CHART_WINDOW_SECONDS,
    }
    return render_interactive_chart(payload=payload, fallback_html=fallback_html)


def render_interactive_chart(payload: Mapping[str, JsonValue], fallback_html: str) -> str:
    chart_id = str(payload["id"])
    payload_id = f"{chart_id}-payload"
    chart_height_value = payload["height"]
    if not isinstance(chart_height_value, int):
        raise TypeError(f"Chart height must be an integer, got {chart_height_value!r}")
    chart_title = str(payload["title"])
    escaped_chart_id = html.escape(chart_id)
    escaped_payload_id = html.escape(payload_id)
    return f"""
    <div class="chart-frame" data-chart-payload="{escaped_payload_id}">
      <div id="{escaped_chart_id}" class="interactive-chart"
        style="min-height: {chart_height_value}px" aria-label="{html.escape(chart_title)}">
      </div>
      {render_json_script(payload_id, payload)}
      <noscript>{fallback_html}</noscript>
    </div>
    """


def render_chart_styles() -> str:
    return f"""
    {load_uplot_css()}
    .chart-frame {{
      margin-top: 8px;
    }}
    .interactive-chart {{
      width: 100%;
      min-width: 0;
    }}
    .interactive-chart .uplot {{
      width: 100%;
      border: 1px solid var(--line);
      border-radius: 8px;
      background: #fff;
      overflow: hidden;
    }}
    .interactive-chart .u-over,
    .interactive-chart .u-under {{
      border-radius: 8px;
    }}
    .interactive-chart .u-over {{
      touch-action: pan-y;
      -webkit-touch-callout: none;
      -webkit-user-select: none;
      user-select: none;
    }}
    .interactive-chart .u-title {{
      display: none;
    }}
    .interactive-chart .u-legend {{
      color: var(--muted);
      font-size: 12px;
    }}
    .interactive-chart .u-legend .u-value {{
      color: var(--ink);
      font-variant-numeric: tabular-nums;
    }}
    .chart-actions {{
      display: flex;
      justify-content: flex-end;
      gap: 6px;
      margin: 0 0 6px;
    }}
    .chart-actions button {{
      min-width: 38px;
      height: 28px;
      border: 1px solid var(--line);
      border-radius: 6px;
      background: #fff;
      color: var(--muted);
      font: inherit;
      font-size: 12px;
      cursor: pointer;
    }}
    .chart-actions button[aria-pressed="true"] {{
      border-color: var(--accent);
      color: var(--accent);
      background: #eef7f5;
    }}
    .empty {{
      min-height: 120px;
      display: flex;
      align-items: center;
      justify-content: center;
      border: 1px solid var(--line);
      border-radius: 8px;
      color: var(--muted);
      background: #fbfcfd;
    }}
    """


def render_chart_runtime_scripts() -> str:
    return f"""
  <script>
{load_uplot_javascript()}
  </script>
  <script>
{CHART_BOOTSTRAP_JAVASCRIPT}
  </script>
"""


CHART_BOOTSTRAP_JAVASCRIPT = r"""
(function () {
  "use strict";

  var latestWindowLabel = "Week";
  var fullWindowLabel = "All";
  var aeroChartTheme = {
    roles: {
      basementRh: "#0b76c2",
      basementTemp: "#d96608",
      basementAh: "#0e9c60",
      outdoorAh: "#8a63e8",
      rain: "#1e46c9",
      bedroom: "#c93f8f",
      livingRoom: "#b07a00",
      outdoor: "#437fff"
    },
    inkMuted: "#4a7391",
    grid: "rgba(15, 127, 206, 0.14)",
    event: "rgba(15, 110, 175, 0.55)",
    bandAlpha: 0.14,
    axisFont: "12px 'Segoe UI', 'Helvetica Neue', sans-serif",
    axisLabelFont: "12px 'Segoe UI', 'Helvetica Neue', sans-serif"
  };

  function isAeroTheme() {
    return document.body.classList.contains("theme-aero");
  }

  function themedSeriesColor(series) {
    if (isAeroTheme() && series.role && aeroChartTheme.roles[series.role]) {
      return aeroChartTheme.roles[series.role];
    }
    return series.color;
  }

  function themedBandColor(band) {
    if (isAeroTheme() && band.role && aeroChartTheme.roles[band.role]) {
      return aeroChartTheme.roles[band.role];
    }
    return band.color;
  }

  function formatTimestamp(epochSeconds) {
    if (epochSeconds == null) {
      return "";
    }
    return new Date(epochSeconds * 1000).toLocaleString("en-GB", {
      day: "2-digit",
      month: "short",
      hour: "2-digit",
      minute: "2-digit"
    });
  }

  function formatSeriesValueWithUnit(value, series) {
    if (value == null || !Number.isFinite(value)) {
      return "\u2013";
    }
    var formattedValue = value.toFixed(series.digits);
    if (!series.unit) {
      return formattedValue;
    }
    return series.unit === "%" ? formattedValue + "%" : formattedValue + " " + series.unit;
  }

  function normalizeLineGaps(payload) {
    payload.series.forEach(function (series, seriesIndex) {
      if (series.kind !== "line") {
        return;
      }
      payload.data[seriesIndex + 1] = payload.data[seriesIndex + 1].map(function (value) {
        return value === null ? undefined : value;
      });
    });
    (payload.bands || []).forEach(function (band) {
      band.lower = band.lower.map(function (value) {
        return value === null ? undefined : value;
      });
      band.upper = band.upper.map(function (value) {
        return value === null ? undefined : value;
      });
    });
  }

  function drawEventBubbles(plot, xPosition) {
    var context = plot.ctx;
    var bottom = plot.bbox.top + plot.bbox.height;
    var count = 0;
    for (var yPosition = bottom - 9; yPosition > plot.bbox.top + 8; yPosition -= 26) {
      var radius = count % 2 === 0 ? 2.4 : 3.4;
      var offset = count % 2 === 0 ? -2.5 : 2.5;
      context.beginPath();
      context.arc(xPosition + offset, yPosition, radius, 0, Math.PI * 2);
      context.globalAlpha = 0.3;
      context.fill();
      context.globalAlpha = 1;
      context.stroke();
      count += 1;
    }
  }

  function eventMarkerPlugin(events) {
    return {
      hooks: {
        draw: [
          function (plot) {
            if (events.length === 0) {
              return;
            }
            var context = plot.ctx;
            var top = plot.bbox.top;
            var bottom = plot.bbox.top + plot.bbox.height;
            context.save();
            context.beginPath();
            context.rect(plot.bbox.left, plot.bbox.top, plot.bbox.width, plot.bbox.height);
            context.clip();
            context.strokeStyle = isAeroTheme() ? aeroChartTheme.event : "rgba(55, 65, 81, 0.45)";
            context.fillStyle = context.strokeStyle;
            context.lineWidth = 1;
            if (!isAeroTheme()) {
              context.setLineDash([4, 4]);
            }
            events.forEach(function (event) {
              var xPosition = plot.valToPos(event.timestamp, "x", true);
              if (xPosition >= plot.bbox.left && xPosition <= plot.bbox.left + plot.bbox.width) {
                if (isAeroTheme()) {
                  drawEventBubbles(plot, Math.round(xPosition) + 0.5);
                  return;
                }
                context.beginPath();
                context.moveTo(Math.round(xPosition) + 0.5, top);
                context.lineTo(Math.round(xPosition) + 0.5, bottom);
                context.stroke();
              }
            });
            context.restore();
          }
        ]
      }
    };
  }

  function hexToRgba(color, alpha) {
    var match = /^#?([a-f\d]{2})([a-f\d]{2})([a-f\d]{2})$/i.exec(color);
    if (match == null) {
      return color;
    }
    return "rgba(" + [
      parseInt(match[1], 16),
      parseInt(match[2], 16),
      parseInt(match[3], 16),
      alpha
    ].join(",") + ")";
  }

  function rangeBandPlugin(bands, timestamps) {
    return {
      hooks: {
        draw: [
          function (plot) {
            if (bands.length === 0) {
              return;
            }
            var context = plot.ctx;
            var left = plot.bbox.left;
            var right = plot.bbox.left + plot.bbox.width;
            context.save();
            context.globalCompositeOperation = "destination-over";
            bands.forEach(function (band) {
              var lowerSegment = [];
              var isDrawing = false;
              context.fillStyle = hexToRgba(
                themedBandColor(band),
                isAeroTheme() ? aeroChartTheme.bandAlpha : 0.14
              );

              function finishSegment() {
                if (!isDrawing || lowerSegment.length < 2) {
                  lowerSegment = [];
                  isDrawing = false;
                  return;
                }
                for (var index = lowerSegment.length - 1; index >= 0; index -= 1) {
                  context.lineTo(lowerSegment[index][0], lowerSegment[index][1]);
                }
                context.closePath();
                context.fill();
                lowerSegment = [];
                isDrawing = false;
              }

              timestamps.forEach(function (timestamp, index) {
                var lower = band.lower[index];
                var upper = band.upper[index];
                if (lower === undefined || upper === undefined) {
                  return;
                }
                if (
                  lower === null ||
                  upper === null ||
                  !Number.isFinite(lower) ||
                  !Number.isFinite(upper)
                ) {
                  finishSegment();
                  return;
                }
                var xPosition = plot.valToPos(timestamp, "x", true);
                if (xPosition < left - 4 || xPosition > right + 4) {
                  finishSegment();
                  return;
                }
                var upperY = plot.valToPos(upper, band.scale || "y", true);
                var lowerY = plot.valToPos(lower, band.scale || "y", true);
                if (!isDrawing) {
                  context.beginPath();
                  context.moveTo(xPosition, upperY);
                  isDrawing = true;
                } else {
                  context.lineTo(xPosition, upperY);
                }
                lowerSegment.push([xPosition, lowerY]);
              });
              finishSegment();
            });
            context.restore();
          }
        ]
      }
    };
  }

  function rainBarPlugin(payload) {
    if (!isAeroTheme()) {
      return { hooks: {} };
    }
    var barIndex = -1;
    payload.series.forEach(function (series, index) {
      if (series.kind === "bar") {
        barIndex = index;
      }
    });
    if (barIndex === -1) {
      return { hooks: {} };
    }
    var series = payload.series[barIndex];
    return {
      hooks: {
        draw: [
          function (plot) {
            var context = plot.ctx;
            var values = payload.data[barIndex + 1];
            var timestamps = payload.data[0];
            var zeroY = plot.valToPos(0, series.scale, true);
            context.save();
            context.beginPath();
            context.rect(plot.bbox.left, plot.bbox.top, plot.bbox.width, plot.bbox.height);
            context.clip();
            context.globalCompositeOperation = "destination-over";
            context.fillStyle = hexToRgba(themedSeriesColor(series), 0.9);
            timestamps.forEach(function (timestamp, index) {
              var value = values[index];
              if (value == null || !Number.isFinite(value) || value <= 0) {
                return;
              }
              var xLeft = plot.valToPos(timestamp - 1700, "x", true);
              var xRight = plot.valToPos(timestamp + 1700, "x", true);
              if (xRight < plot.bbox.left - 40 || xLeft > plot.bbox.left + plot.bbox.width + 40) {
                return;
              }
              var yPosition = plot.valToPos(value, series.scale, true);
              var width = Math.max(1, xRight - xLeft - 1);
              var height = Math.max(1, zeroY - yPosition);
              if (typeof context.roundRect === "function" && width >= 2 && height >= 2) {
                var radius = Math.min(width / 2, 3.5, height);
                context.beginPath();
                context.roundRect(xLeft, yPosition, width, height, [radius, radius, 0, 0]);
                context.fill();
                return;
              }
              context.fillRect(xLeft, yPosition, width, height);
            });
            context.restore();
          }
        ]
      }
    };
  }

  function waterFill(color) {
    return function (plot) {
      var top = plot.bbox.top;
      var height = plot.bbox.height;
      if (!Number.isFinite(top) || !Number.isFinite(height) || height <= 0) {
        return hexToRgba(color, 0.18);
      }
      var gradient = plot.ctx.createLinearGradient(0, top, 0, top + height);
      gradient.addColorStop(0, hexToRgba(color, 0.4));
      gradient.addColorStop(1, hexToRgba(color, 0.03));
      return gradient;
    };
  }

  function makeSeriesOptions(payload) {
    return [
      {
        label: "Time",
        value: function (_plot, value) {
          return formatTimestamp(value);
        }
      }
    ].concat(payload.series.map(function (series) {
      var options = {
        label: series.name,
        stroke: themedSeriesColor(series),
        fill: series.kind === "bar" ? themedSeriesColor(series) : undefined,
        width: series.kind === "bar" ? 0 : 2,
        scale: series.scale || "y",
        points: { show: false },
        value: function (_plot, value) {
          return formatSeriesValueWithUnit(value, series);
        }
      };
      if (series.kind === "bar") {
        options.paths = isAeroTheme()
          ? function () { return null; }
          : uPlot.paths.bars({ size: [0.74, Infinity, 1] });
      }
      if (
        isAeroTheme() &&
        payload.title === "Basement conditions" &&
        series.role === "basementRh"
      ) {
        options.fill = waterFill(themedSeriesColor(series));
        options.width = 2.5;
      }
      return options;
    }));
  }

  function dataBounds(payload) {
    var timestamps = payload.data[0];
    var minimum = timestamps[0];
    var maximum = timestamps[timestamps.length - 1];
    return {
      minimum: minimum,
      maximum: maximum,
      latestMinimum: Math.max(minimum, maximum - payload.initialWindowSeconds)
    };
  }

  function scaleValueBounds(payload, scaleKey) {
    var values = [];
    payload.series.forEach(function (series, seriesIndex) {
      if ((series.scale || "y") === scaleKey) {
        values = values.concat(payload.data[seriesIndex + 1]);
      }
    });
    (payload.bands || []).forEach(function (band) {
      if ((band.scale || "y") === scaleKey) {
        values = values.concat(band.lower, band.upper);
      }
    });
    var finiteValues = values.filter(function (value) {
      return value != null && Number.isFinite(value);
    });
    if (finiteValues.length === 0) {
      return { minimum: 0, maximum: 1 };
    }
    return {
      minimum: Math.min.apply(null, finiteValues),
      maximum: Math.max.apply(null, finiteValues)
    };
  }

  function scaleHasBars(payload, scaleKey) {
    return payload.series.some(function (series) {
      return (series.scale || "y") === scaleKey && series.kind === "bar";
    });
  }

  function makeScales(payload, bounds) {
    var scales = {
      x: { time: true, min: bounds.latestMinimum, max: bounds.maximum }
    };
    (payload.axes || [{ scale: "y" }]).forEach(function (axis) {
      var scaleKey = axis.scale || "y";
      var valueBounds = scaleValueBounds(payload, scaleKey);
      if (scaleHasBars(payload, scaleKey)) {
        // Bars keep a fixed full-history range so zooming in never inflates light rain.
        var barMaximum = Math.max(1, valueBounds.maximum * 1.15);
        scales[scaleKey] = { range: function () {
          return [0, barMaximum];
        } };
        return;
      }
      var minimum = valueBounds.minimum;
      var maximum = valueBounds.maximum;
      if (minimum === maximum) {
        minimum -= 1;
        maximum += 1;
      } else {
        var padding = (maximum - minimum) * 0.08;
        minimum -= padding;
        maximum += padding;
      }
      scales[scaleKey] = { range: function () {
        return [minimum, maximum];
      } };
    });
    return scales;
  }

  function makeAxes(payload) {
    var timeAxis = isAeroTheme() ? {
      stroke: aeroChartTheme.inkMuted,
      grid: { stroke: aeroChartTheme.grid, width: 1 },
      ticks: { stroke: aeroChartTheme.grid, width: 1 },
      font: aeroChartTheme.axisFont
    } : {};
    var shownCount = 0;
    return [timeAxis].concat(payload.axes.map(
      function (axis) {
        var shown = axis.show !== false;
        var firstShown = false;
        if (shown) {
          shownCount += 1;
          firstShown = shownCount === 1;
        }
        // Keys are only set when they carry a value: uPlot copies an explicit
        // undefined over its own axis defaults and later crashes resolving the font.
        var axisOptions = {
          scale: axis.scale || "y",
          label: axis.label || "",
          side: axis.side === "right" ? 1 : 3,
          show: shown,
          size: shown ? (axis.size || 56) : 0
        };
        if (!shown) {
          axisOptions.values = function () { return []; };
          axisOptions.ticks = { show: false };
          axisOptions.grid = { show: false };
          return axisOptions;
        }
        // Only the first visible value axis draws grid lines, matching the prototype;
        // extra axes would double-stripe the plot.
        if (!firstShown) {
          axisOptions.grid = { show: false };
        }
        if (isAeroTheme()) {
          axisOptions.ticks = { stroke: aeroChartTheme.grid, width: 1 };
          if (firstShown) {
            axisOptions.grid = { stroke: aeroChartTheme.grid, width: 1 };
          }
          axisOptions.stroke = aeroChartTheme.inkMuted;
          axisOptions.font = aeroChartTheme.axisFont;
          axisOptions.labelFont = aeroChartTheme.axisLabelFont;
          axisOptions.labelGap = 4;
        }
        return axisOptions;
      }
    ));
  }

  function clampRange(minimum, maximum, bounds) {
    var span = maximum - minimum;
    var fullSpan = bounds.maximum - bounds.minimum;
    if (span >= fullSpan) {
      return [bounds.minimum, bounds.maximum];
    }
    if (minimum < bounds.minimum) {
      maximum += bounds.minimum - minimum;
      minimum = bounds.minimum;
    }
    if (maximum > bounds.maximum) {
      minimum -= maximum - bounds.maximum;
      maximum = bounds.maximum;
    }
    return [Math.max(bounds.minimum, minimum), Math.min(bounds.maximum, maximum)];
  }

  function setRange(plot, minimum, maximum, bounds) {
    var clampedRange = clampRange(minimum, maximum, bounds);
    plot.setScale("x", { min: clampedRange[0], max: clampedRange[1] });
  }

  function addRangeControls(frame, plot, bounds) {
    // The aero chart cards carry a .chart-actions container in their header so the
    // buttons share the title row (prototype layout); the private report has no card
    // and keeps the buttons in a row of their own above the chart.
    var card = frame.closest(".chart-card");
    var controls = card ? card.querySelector(".chart-actions") : null;
    if (controls == null) {
      controls = document.createElement("div");
      controls.className = "chart-actions";
      frame.insertBefore(controls, frame.firstChild);
    }
    var latestButton = document.createElement("button");
    var fullButton = document.createElement("button");
    latestButton.type = "button";
    latestButton.textContent = latestWindowLabel;
    latestButton.setAttribute("aria-label", "Latest week");
    latestButton.setAttribute("aria-pressed", "true");
    fullButton.type = "button";
    fullButton.textContent = fullWindowLabel;
    fullButton.setAttribute("aria-label", "Full history");
    fullButton.setAttribute("aria-pressed", "false");
    latestButton.addEventListener("click", function () {
      setRange(plot, bounds.latestMinimum, bounds.maximum, bounds);
      latestButton.setAttribute("aria-pressed", "true");
      fullButton.setAttribute("aria-pressed", "false");
    });
    fullButton.addEventListener("click", function () {
      setRange(plot, bounds.minimum, bounds.maximum, bounds);
      latestButton.setAttribute("aria-pressed", "false");
      fullButton.setAttribute("aria-pressed", "true");
    });
    controls.append(latestButton, fullButton);
  }

  function addWheelNavigation(frame, plot, bounds) {
    var overlay = frame.querySelector(".u-over");
    if (overlay == null) {
      return;
    }
    overlay.addEventListener("wheel", function (event) {
      if (!event.shiftKey && !event.ctrlKey && !event.metaKey) {
        return;
      }
      event.preventDefault();
      var scale = plot.scales.x;
      var minimum = scale.min;
      var maximum = scale.max;
      var span = maximum - minimum;
      if (event.shiftKey) {
        var shift = event.deltaY * span * 0.0015;
        setRange(plot, minimum + shift, maximum + shift, bounds);
        return;
      }
      var rect = overlay.getBoundingClientRect();
      var pointerRatio = Math.min(Math.max((event.clientX - rect.left) / rect.width, 0), 1);
      var anchor = minimum + span * pointerRatio;
      var factor = event.deltaY > 0 ? 1.2 : 0.82;
      setRange(
        plot,
        anchor - (anchor - minimum) * factor,
        anchor + (maximum - anchor) * factor,
        bounds
      );
    }, { passive: false });
  }

  function addTouchNavigation(frame, plot, bounds) {
    var overlay = frame.querySelector(".u-over");
    if (overlay == null) {
      return;
    }
    var minimumSpanSeconds = 600;
    var directionSlopPixels = 8;
    var gesture = null;
    var touchStart = null;
    var pinchStartValues = null;

    function overlayLeft(touch) {
      return touch.clientX - overlay.getBoundingClientRect().left;
    }

    function scrubTo(touch) {
      var rect = overlay.getBoundingClientRect();
      plot.setCursor({
        left: touch.clientX - rect.left,
        top: touch.clientY - rect.top
      });
    }

    function beginPinch(touches) {
      gesture = "pinch";
      pinchStartValues = [
        plot.posToVal(overlayLeft(touches[0]), "x"),
        plot.posToVal(overlayLeft(touches[1]), "x")
      ];
    }

    function movePinch(touches) {
      var firstX = overlayLeft(touches[0]);
      var secondX = overlayLeft(touches[1]);
      var width = overlay.getBoundingClientRect().width;
      if (Math.abs(secondX - firstX) < 12 || width <= 0) {
        return;
      }
      var span =
        ((pinchStartValues[1] - pinchStartValues[0]) * width) / (secondX - firstX);
      if (!Number.isFinite(span) || span <= 0) {
        return;
      }
      span = Math.max(span, minimumSpanSeconds);
      var minimum = pinchStartValues[0] - (firstX / width) * span;
      setRange(plot, minimum, minimum + span, bounds);
    }

    overlay.addEventListener("touchstart", function (event) {
      if (event.touches.length >= 2) {
        event.preventDefault();
        beginPinch(event.touches);
        return;
      }
      gesture = null;
      touchStart = { x: event.touches[0].clientX, y: event.touches[0].clientY };
    }, { passive: false });

    overlay.addEventListener("touchmove", function (event) {
      if (gesture === "pinch") {
        if (event.touches.length >= 2) {
          event.preventDefault();
          movePinch(event.touches);
        }
        return;
      }
      if (gesture === "scroll" || touchStart == null || event.touches.length !== 1) {
        return;
      }
      var touch = event.touches[0];
      if (gesture == null) {
        var deltaX = Math.abs(touch.clientX - touchStart.x);
        var deltaY = Math.abs(touch.clientY - touchStart.y);
        if (Math.max(deltaX, deltaY) < directionSlopPixels) {
          return;
        }
        gesture = deltaX > deltaY ? "scrub" : "scroll";
      }
      if (gesture === "scrub") {
        event.preventDefault();
        scrubTo(touch);
      }
    }, { passive: false });

    function endTouch(event) {
      if (gesture == null && touchStart != null && event.changedTouches.length > 0) {
        scrubTo(event.changedTouches[0]);
      }
      if (event.touches.length === 0) {
        gesture = null;
        touchStart = null;
        pinchStartValues = null;
        return;
      }
      if (gesture === "pinch" && event.touches.length >= 2) {
        beginPinch(event.touches);
        return;
      }
      gesture = "scroll";
    }

    overlay.addEventListener("touchend", endTouch);
    overlay.addEventListener("touchcancel", endTouch);
  }

  function renderChart(frame) {
    var payloadScript = document.getElementById(frame.dataset.chartPayload);
    if (payloadScript == null) {
      return;
    }
    var payload = JSON.parse(payloadScript.textContent);
    normalizeLineGaps(payload);
    var host = frame.querySelector(".interactive-chart");
    var bounds = dataBounds(payload);
    var options = {
      title: payload.title,
      width: Math.max(320, host.clientWidth || frame.clientWidth || 720),
      height: payload.height,
      scales: makeScales(payload, bounds),
      axes: makeAxes(payload),
      cursor: {
        drag: { x: true, y: false, setScale: true },
        focus: { prox: 24 }
      },
      legend: { show: true, live: true },
      series: makeSeriesOptions(payload),
      plugins: [
        rangeBandPlugin(payload.bands || [], payload.data[0]),
        rainBarPlugin(payload),
        eventMarkerPlugin(payload.events)
      ]
    };
    var plot = new uPlot(options, payload.data, host);
    frame.chartPlot = plot;
    addRangeControls(frame, plot, bounds);
    addWheelNavigation(frame, plot, bounds);
    addTouchNavigation(frame, plot, bounds);
    if ("ResizeObserver" in window) {
      new ResizeObserver(function () {
        plot.setSize({
          width: Math.max(320, Math.floor(host.clientWidth || frame.clientWidth || 720)),
          height: payload.height
        });
      }).observe(host);
    }
  }

  document.querySelectorAll(".chart-frame").forEach(renderChart);
})();
"""


def render_period_table(summaries: Sequence[PeriodSummary], include_flags: bool = False) -> str:
    flags_header = "<th>Comparability flags</th>" if include_flags else ""
    rows = "\n".join(
        render_period_row(summary, include_flags=include_flags) for summary in summaries
    )
    return f"""
    <table>
      <thead>
        <tr>
          <th>Period</th>
          <th>Start</th>
          <th>End</th>
          <th>Samples</th>
          <th>Mean RH %</th>
          <th>Mean AH g/m3</th>
          <th>Outdoor AH g/m3</th>
          <th>EA rain mm</th>
          {flags_header}
        </tr>
      </thead>
      <tbody>{rows}</tbody>
    </table>
    """


def render_period_row(summary: PeriodSummary, include_flags: bool) -> str:
    flags_cell = ""
    if include_flags:
        flags = html.escape(", ".join(summary.comparability_flags) or "none")
        flags_cell = f"<td>{flags}</td>"
    return f"""
        <tr>
          <td>{html.escape(summary.label)}</td>
          <td>{format_timestamp(summary.start)}</td>
          <td>{format_timestamp(summary.end)}</td>
          <td>{summary.sensor_samples:,}</td>
          <td>{format_optional_float(summary.mean_relative_humidity_pct)}</td>
          <td>{format_optional_float(summary.mean_absolute_humidity_g_m3, 3)}</td>
          <td>{format_optional_float(summary.outdoor_mean_absolute_humidity_g_m3, 3)}</td>
          <td>{summary.rain_mm:.1f}</td>
          {flags_cell}
        </tr>
        """


def render_hypothesis_panel(summary: SiteAnalysisSummary) -> str:
    return "\n".join(
        f"""
        <article class="panel">
          <h3>{html.escape(assessment.name)}</h3>
          <p>{html.escape(assessment.summary)}</p>
        </article>
        """
        for assessment in summary.hypotheses
    )


def render_metric_card(label: str, value: str) -> str:
    return (
        '<div class="card">'
        f'<div class="label">{html.escape(label)}</div>'
        f'<div class="value">{html.escape(value)}</div>'
        "</div>"
    )


def latest_basement_readout(summary: SiteAnalysisSummary, metric_name: str) -> str:
    chart = summary.dashboard_charts[0]
    matching_series = next(
        series for series in chart.series if series.name.lower() == metric_name
    )
    if not matching_series.points:
        return "n/a"
    return format_optional_float(matching_series.points[-1][1], 1)


def render_aero_readouts(summary: SiteAnalysisSummary) -> str:
    relative_humidity = latest_basement_readout(summary, "relative humidity")
    temperature = latest_basement_readout(summary, "temperature")
    humidity_fill = "50%" if relative_humidity == "n/a" else f"{relative_humidity}%"
    return f"""
    <section class="readouts" aria-label="Current basement conditions">
      <div class="readout readout-humidity" style="--fill: {html.escape(humidity_fill)}">
        <div class="readout-value">{html.escape(relative_humidity)}<span>%</span></div>
        <div class="readout-label">Basement relative humidity</div>
      </div>
      <div class="readout readout-temperature">
        <div class="readout-value">{html.escape(temperature)}<span>°C</span></div>
        <div class="readout-label">Basement temperature</div>
      </div>
    </section>
    """


def render_aero_chart_card(chart: ChartSpec) -> str:
    return f"""
    <section class="chart-card">
      <div class="chart-head">
        <h2>{html.escape(chart.title)}</h2>
        <div class="chart-actions"></div>
      </div>
      {render_chart_spec(chart)}
    </section>
    """


def frutiger_aero_asset_path(filename: str) -> str:
    return f"{FRUTIGER_AERO_ASSET_PREFIX}/{filename}"


def render_aero_bubbles() -> str:
    bubbles = (
        ("18px", "8%", "13s", "-3s"),
        ("34px", "23%", "17s", "-9s"),
        ("12px", "44%", "11s", "-6s"),
        ("26px", "62%", "15s", "-1s"),
        ("42px", "78%", "19s", "-12s"),
        ("16px", "91%", "12s", "-8s"),
    )
    return "\n".join(
        (
            '    <div class="aero-underbubble" '
            f'style="width:{size};height:{size};left:{left};'
            f'animation-duration:{duration};animation-delay:{delay}"></div>'
        )
        for size, left, duration, delay in bubbles
    )


def render_index_html(summary: SiteAnalysisSummary) -> str:
    charts_html = "\n".join(render_aero_chart_card(chart) for chart in summary.dashboard_charts)
    latest_reading = summary.metadata.data_window_end.strftime("%d %b %Y, %H:%M")
    tank_footer_html = (
        ""
        if summary.tank_footer_text is None
        else f"\n        <p>{html.escape(summary.tank_footer_text)}</p>"
    )
    scene_960 = frutiger_aero_asset_path("tall-scene-960.webp")
    scene_1440 = frutiger_aero_asset_path("tall-scene-1440.webp")
    scene_2048 = frutiger_aero_asset_path("tall-scene-2048.webp")
    floor_image = frutiger_aero_asset_path("floor-strip.webp")
    dehumidifier_image = frutiger_aero_asset_path("dehumidifier.webp")
    goldfish_image = frutiger_aero_asset_path("goldfish.webp")
    dragonfly_image = frutiger_aero_asset_path("dragonfly.webp")
    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Watch a basement dry</title>
  <link rel="icon" href="data:,">
  <style>
    {render_chart_styles()}
    :root {{
      color-scheme: light;
      --ink: #123a55;
      --muted: #4a7391;
      --line: rgba(109, 188, 224, 0.46);
      --accent: #0f7fce;
      --scene-image: url("{scene_1440}");
      --floor-image: url("{floor_image}");
      --dehumidifier-image: url("{dehumidifier_image}");
      --goldfish-image: url("{goldfish_image}");
      --dragonfly-image: url("{dragonfly_image}");
      --waterline-y: 92vh;
      --scene-height: 150vw;
      --scene-waterline: 94.5vw;
      --scene-top: calc(var(--waterline-y) - var(--scene-waterline));
      --scene-bottom: calc(var(--waterline-y) + var(--scene-height) - var(--scene-waterline));
    }}
    * {{ box-sizing: border-box; }}
    html {{ min-height: 100%; }}
    body {{
      margin: 0;
      min-height: 100%;
      overflow-x: hidden;
      position: relative;
      font: 14px/1.45 "Segoe UI", "Helvetica Neue", -apple-system, BlinkMacSystemFont,
        sans-serif;
      color: var(--ink);
      background: #073a58;
    }}
    .aero-scene-wrap {{
      position: absolute;
      top: 0;
      left: 0;
      width: 100%;
      height: var(--scene-bottom);
      overflow: hidden;
      pointer-events: none;
    }}
    .aero-sky-extend {{
      position: absolute;
      inset: 0;
      background:
        radial-gradient(56vw 56vw at 15vw calc(var(--scene-top) + 21vw),
          rgba(190, 235, 255, 0.6), rgba(190, 235, 255, 0) 70%),
        linear-gradient(90deg, rgba(150, 215, 255, 0.35), rgba(150, 215, 255, 0) 40%,
          rgba(2, 45, 140, 0.25)),
        linear-gradient(180deg, #0143a0 0%, #0062d7 var(--scene-top), #0062d7 100%);
    }}
    .aero-scene {{
      position: absolute;
      top: var(--scene-top);
      left: 0;
      width: 100%;
      height: var(--scene-height);
      background: var(--scene-image) center / 100% 100% no-repeat;
      mask-image: linear-gradient(180deg, transparent 0, #000 56px);
    }}
    .aero-scene-fade {{
      position: absolute;
      left: 0;
      width: 100%;
      height: 22vw;
      top: calc(var(--scene-bottom) - 22vw);
      background: linear-gradient(180deg, rgba(6, 65, 110, 0), #06416e 96%);
    }}
    .aero-deep {{
      position: absolute;
      inset: 0;
      overflow: hidden;
      pointer-events: none;
      background: linear-gradient(180deg,
        rgba(6, 65, 110, 0) 0,
        rgba(6, 65, 110, 0) var(--scene-bottom),
        #06416e var(--scene-bottom),
        #052c46 72%,
        #04202f 100%);
    }}
    .page {{
      position: relative;
      z-index: 2;
      max-width: 1060px;
      margin: 0 auto;
      padding: 0 20px 300px;
    }}
    .zone-art {{
      position: absolute;
      top: 0;
      bottom: 0;
      left: 50%;
      width: 100vw;
      transform: translateX(-50%);
      z-index: -1;
      overflow: hidden;
      pointer-events: none;
    }}
    .zone-sky {{
      position: relative;
      min-height: 100vh;
      padding-top: 0;
    }}
    .zone-under {{
      position: relative;
      padding-top: 4vh;
    }}
    header {{
      text-align: center;
      padding-top: 9vh;
    }}
    h1 {{
      margin: 0;
      font-size: clamp(38px, 5.4vw, 58px);
      font-weight: 650;
      letter-spacing: 0.005em;
      background: linear-gradient(180deg, #04365f, #0a63a8 42%, #2ea3dc 72%, #8fdcf8);
      -webkit-background-clip: text;
      background-clip: text;
      color: transparent;
      filter: drop-shadow(0 1px 0 rgba(255,255,255,0.95))
        drop-shadow(0 2px 2px rgba(255,255,255,0.55))
        drop-shadow(0 8px 22px rgba(8,70,125,0.4));
    }}
    h2 {{
      margin: 0;
      font-size: 17px;
      font-weight: 600;
      letter-spacing: 0;
      color: #0b5f9e;
    }}
    a {{ color: var(--accent); }}
    .readouts {{
      display: flex;
      justify-content: center;
      flex-wrap: wrap;
      gap: 36px;
      margin: 7vh 0 30px;
    }}
    .readout {{
      position: relative;
      flex: 0 0 236px;
      width: 236px;
      height: 236px;
      overflow: hidden;
      display: flex;
      flex-direction: column;
      align-items: center;
      justify-content: center;
      padding: 0 26px;
      border: 1px solid rgba(255,255,255,0.95);
      border-radius: 50%;
      text-align: center;
      backdrop-filter: blur(10px);
      box-shadow: 0 14px 34px rgba(12,80,130,0.35),
        0 0 26px rgba(140,220,255,0.4),
        inset 0 2px 2px rgba(255,255,255,0.95),
        inset 0 -14px 26px rgba(90,180,230,0.35),
        0 40px 30px -22px rgba(25,140,205,0.45);
    }}
    .readout-humidity {{
      background: radial-gradient(circle at 32% 26%, rgba(255,255,255,0.9),
        rgba(225,246,255,0.55) 32%, rgba(170,220,248,0.4) 62%,
        rgba(125,195,238,0.55));
    }}
    .readout-humidity::before {{
      content: "";
      position: absolute;
      left: 0;
      right: 0;
      bottom: 0;
      height: var(--fill, 50%);
      background: linear-gradient(180deg, rgba(110,210,252,0.6), rgba(25,132,202,0.72));
      border-radius: 46% 54% 0 0 / 16px 20px 0 0;
      box-shadow: inset 0 3px 3px -1px rgba(255,255,255,0.95);
      animation: water-slosh 7s ease-in-out infinite alternate;
    }}
    .readout-temperature {{
      background: radial-gradient(circle at 32% 26%, rgba(255,255,255,0.92),
        rgba(255,238,205,0.6) 34%, rgba(252,195,115,0.5) 66%,
        rgba(240,150,55,0.6));
      box-shadow: 0 14px 34px rgba(140,85,15,0.3),
        0 0 26px rgba(255,205,130,0.45),
        inset 0 2px 2px rgba(255,255,255,0.95),
        inset 0 -14px 26px rgba(235,155,60,0.4),
        0 40px 30px -22px rgba(220,140,45,0.4);
    }}
    .readout::after {{
      content: "";
      position: absolute;
      left: 19%;
      right: 19%;
      top: 7%;
      height: 30%;
      border-radius: 50%;
      background: linear-gradient(180deg, rgba(255,255,255,0.95), rgba(255,255,255,0.05));
    }}
    .readout-value {{
      position: relative;
      z-index: 1;
      font-size: 54px;
      font-weight: 300;
      line-height: 1;
      color: #084a80;
      text-shadow: 0 1px 0 rgba(255,255,255,0.85);
      font-variant-numeric: tabular-nums;
    }}
    .readout-temperature .readout-value {{ color: #a34a02; }}
    .readout-value span {{
      margin-left: 4px;
      font-size: 24px;
      opacity: 0.75;
    }}
    .readout-label {{
      position: relative;
      z-index: 1;
      margin-top: 8px;
      font-size: 13px;
      color: #275b7e;
    }}
    .readout-temperature .readout-label {{ color: #7c4a14; }}
    @keyframes water-slosh {{
      from {{ border-radius: 46% 54% 0 0 / 18px 12px 0 0; }}
      to {{ border-radius: 54% 46% 0 0 / 12px 18px 0 0; }}
    }}
    .aero-scroll-hint {{
      position: absolute;
      left: 50%;
      top: 74vh;
      transform: translateX(-50%);
    }}
    .aero-scroll-hint span {{
      display: block;
      width: 26px;
      height: 26px;
      border-right: 6px solid rgba(255,255,255,0.95);
      border-bottom: 6px solid rgba(255,255,255,0.95);
      border-radius: 3px;
      filter: drop-shadow(0 3px 10px rgba(8,70,125,0.6));
      animation: hint-bob 1.8s ease-in-out infinite;
    }}
    @keyframes hint-bob {{
      0%, 100% {{ transform: rotate(45deg) translate(0, 0); opacity: 0.8; }}
      50% {{ transform: rotate(45deg) translate(7px, 7px); opacity: 1; }}
    }}
    .aero-aurora {{
      position: absolute;
      height: 240px;
      width: 150%;
      left: -25%;
      background: linear-gradient(100deg, transparent 8%, rgba(130,255,225,0.28) 30%,
        rgba(150,195,255,0.32) 52%, rgba(255,190,245,0.24) 72%, transparent 92%);
      filter: blur(28px);
      mix-blend-mode: screen;
      animation: aurora-drift 16s ease-in-out infinite alternate;
    }}
    .aero-aurora.aurora-2 {{
      animation-duration: 23s;
      animation-delay: -8s;
      opacity: 0.7;
    }}
    @keyframes aurora-drift {{
      from {{ transform: rotate(-7deg) translateX(-50px); }}
      to {{ transform: rotate(-4deg) translateX(50px); }}
    }}
    .aero-bokeh {{
      position: absolute;
      border-radius: 50%;
      background: radial-gradient(circle at 35% 30%, rgba(255,255,255,0.95),
        rgba(255,255,255,0.25) 55%, transparent 72%);
      filter: blur(1.5px);
      opacity: 0.55;
      animation: bokeh-drift ease-in-out infinite alternate;
    }}
    @keyframes bokeh-drift {{
      from {{ transform: translate(0, 0); }}
      to {{ transform: translate(26px, -34px); }}
    }}
    .aero-dragonfly {{
      position: absolute;
      top: 56vh;
      right: 6%;
      width: 148px;
      aspect-ratio: 512 / 342;
      background: var(--dragonfly-image) center / contain no-repeat;
      transform: rotate(-8deg);
      z-index: 2;
      pointer-events: none;
      filter: drop-shadow(0 8px 12px rgba(20,70,110,0.35));
      animation: dragonfly-hover 3.2s ease-in-out infinite alternate;
    }}
    @keyframes dragonfly-hover {{
      from {{ transform: rotate(-8deg) translateY(0); }}
      to {{ transform: rotate(-6deg) translateY(6px); }}
    }}
    .aero-fish-sky,
    .aero-fish-deep {{
      position: absolute;
      aspect-ratio: 640 / 480;
      background: var(--goldfish-image) center / contain no-repeat;
      pointer-events: none;
    }}
    .aero-fish-sky {{
      width: clamp(110px, 14vw, 185px);
      right: 5%;
      top: 330px;
      filter: drop-shadow(0 10px 16px rgba(10,70,120,0.35));
      animation: fish-swim 11s ease-in-out infinite alternate;
    }}
    .aero-fish-deep {{
      width: 110px;
      top: calc(100vh + 34vw);
      left: 8%;
      filter: brightness(0.35) saturate(0.4) blur(1.5px);
      opacity: 0.5;
      transform: scaleX(-1);
      animation: fish-deep-drift 70s ease-in-out infinite alternate;
    }}
    @keyframes fish-swim {{
      from {{ transform: translate(0, 0) rotate(-5deg); }}
      to {{ transform: translate(-70px, 26px) rotate(3deg); }}
    }}
    @keyframes fish-deep-drift {{
      from {{ transform: scaleX(-1) translate(0, 0); }}
      to {{ transform: scaleX(-1) translate(-58vw, 40px); }}
    }}
    .aero-underbubble {{
      position: absolute;
      bottom: -70px;
      border-radius: 50%;
      background: radial-gradient(circle at 32% 28%, rgba(255,255,255,0.9),
        rgba(255,255,255,0.28) 24%, rgba(190,235,255,0.12) 60%,
        rgba(160,220,250,0.3));
      border: 1px solid rgba(255,255,255,0.5);
      box-shadow: inset -5px -7px 14px rgba(120,200,240,0.3);
      animation: bubble-rise linear infinite;
    }}
    @keyframes bubble-rise {{
      0% {{ transform: translate(0, 0); opacity: 0; }}
      8% {{ opacity: 0.9; }}
      100% {{ transform: translate(26px, -1600px); opacity: 0; }}
    }}
    .aero-deep-floor {{
      position: absolute;
      left: 0;
      right: 0;
      bottom: 0;
      height: min(240px, 30vw);
      background: var(--floor-image) bottom center / auto 100% repeat-x;
      mask-image: linear-gradient(180deg, transparent 0%, #000 60%);
    }}
    .aero-deep-floor::after {{
      content: "";
      position: absolute;
      inset: 0;
      background: linear-gradient(180deg, rgba(4,30,48,0.72),
        rgba(6,45,70,0.5) 45%, rgba(8,55,84,0.4));
    }}
    .aero-dehumidifier {{
      position: absolute;
      right: 6%;
      bottom: min(88px, 11vw);
      width: clamp(130px, 15vw, 200px);
      aspect-ratio: 640 / 427;
      background: var(--dehumidifier-image) bottom / contain no-repeat;
      filter: brightness(0.88) saturate(0.92) drop-shadow(0 12px 16px rgba(2,18,30,0.6));
    }}
    .chart-card {{
      position: relative;
      margin-bottom: 26px;
      padding: 16px 18px 10px;
      overflow: hidden;
      border: 1px solid rgba(255,255,255,0.95);
      border-radius: 22px;
      background: linear-gradient(180deg, rgba(255,255,255,0.88), rgba(255,255,255,0.7));
      backdrop-filter: blur(20px) saturate(1.2);
      box-shadow: 0 12px 36px rgba(10,70,120,0.28),
        0 0 0 1px rgba(150,225,255,0.35),
        0 0 30px rgba(120,210,255,0.35),
        inset 0 1px 0 rgba(255,255,255,0.95),
        inset 0 -12px 20px rgba(150,215,245,0.3);
    }}
    .chart-card::before {{
      content: "";
      position: absolute;
      left: 14px;
      right: 14px;
      top: 0;
      height: 54px;
      border-radius: 16px 16px 28px 28px;
      background: linear-gradient(180deg, rgba(255,255,255,0.65), rgba(255,255,255,0.06));
      pointer-events: none;
    }}
    .chart-card::after {{
      content: "";
      position: absolute;
      top: -20px;
      bottom: -20px;
      left: 0;
      width: 46%;
      background: linear-gradient(105deg, transparent 20%, rgba(255,255,255,0.5) 50%,
        transparent 80%);
      transform: translateX(-130%) skewX(-18deg);
      pointer-events: none;
      animation: sheen-sweep 1.7s ease-out 0.5s 1 both;
    }}
    .chart-card:hover::after {{
      animation: sheen-sweep-again 1.1s ease-out 1 both;
    }}
    @keyframes sheen-sweep {{
      to {{ transform: translateX(320%) skewX(-18deg); }}
    }}
    @keyframes sheen-sweep-again {{
      from {{ transform: translateX(-130%) skewX(-18deg); }}
      to {{ transform: translateX(320%) skewX(-18deg); }}
    }}
    .chart-head,
    .chart-frame {{
      position: relative;
      z-index: 1;
    }}
    .chart-head {{
      display: flex;
      align-items: center;
      justify-content: space-between;
      gap: 12px;
      margin-bottom: 6px;
    }}
    .interactive-chart .uplot {{
      border: 0;
      border-radius: 0;
      background: transparent;
    }}
    .interactive-chart .u-legend {{
      color: var(--ink);
      font-size: 12px;
    }}
    .chart-head .chart-actions {{
      margin: 0;
      gap: 8px;
    }}
    .chart-actions button {{
      min-width: 0;
      height: auto;
      border-color: #79c3e3;
      border-radius: 999px;
      background: linear-gradient(180deg, #f4fdff, #c9effd 42%, #8edcf8 58%, #cdf3ff);
      color: #0b5f9e;
      font-size: 13px;
      font-weight: 600;
      line-height: 1.5;
      padding: 5px 18px;
      box-shadow: 0 3px 8px rgba(20,90,140,0.3), inset 0 1px 0 rgba(255,255,255,0.95),
        inset 0 -5px 8px rgba(70,170,220,0.35),
        0 10px 10px -6px rgba(120,210,255,0.5);
    }}
    .chart-actions button[aria-pressed="true"] {{
      border-color: #0a6cb4;
      background: linear-gradient(180deg, #6fd0f2, #0f7fce 52%, #0a6cb4 60%, #4db6e6);
      color: #fff;
      box-shadow: 0 3px 10px rgba(10,90,150,0.45),
        inset 0 1px 0 rgba(255,255,255,0.6),
        inset 0 -5px 10px rgba(6,60,105,0.4),
        0 10px 10px -6px rgba(60,180,240,0.55);
    }}
    footer {{
      position: relative;
      z-index: 1;
      margin-top: 34px;
      padding: 12px 18px;
      border: 1px solid rgba(170,230,255,0.4);
      border-radius: 16px;
      color: #e9f7ff;
      font-size: 13.5px;
      background: linear-gradient(180deg, rgba(10,55,84,0.55), rgba(7,40,62,0.75));
      backdrop-filter: blur(12px);
      box-shadow: 0 10px 28px rgba(3,25,40,0.5), inset 0 1px 0 rgba(200,240,255,0.35);
    }}
    footer p {{
      margin: 4px 0;
    }}
    .sources {{
      color: #b9dcef;
    }}
    @media (min-width: 1400px) {{
      :root {{ --scene-image: url("{scene_2048}"); }}
    }}
    @media (max-width: 760px) {{
      :root {{
        --scene-image: url("{scene_960}");
        --scene-height: 180vw;
        --scene-waterline: 113vw;
      }}
      .page {{ padding-left: 14px; padding-right: 14px; }}
      header {{ padding-top: 7vh; }}
      .readouts {{ gap: 18px; }}
      .readout {{
        flex-basis: 196px;
        width: 196px;
        height: 196px;
      }}
      .readout-value {{ font-size: 44px; }}
      .aero-dragonfly {{ display: none; }}
      .chart-card {{ padding: 12px 10px 8px; }}
      .chart-head {{ flex-wrap: wrap; }}
    }}
    @media (prefers-reduced-motion: reduce) {{
      *,
      *::before,
      *::after {{
        animation: none !important;
      }}
    }}
  </style>
</head>
<body class="theme-aero">
  <div class="aero-scene-wrap" aria-hidden="true">
    <div class="aero-sky-extend"></div>
    <div class="aero-scene"></div>
    <div class="aero-scene-fade"></div>
  </div>
  <div class="aero-deep" aria-hidden="true">
{render_aero_bubbles()}
    <div class="aero-fish-deep"></div>
    <div class="aero-deep-floor"></div>
    <div class="aero-dehumidifier"></div>
  </div>
  <main class="page">
    <div class="zone-sky">
      <div class="zone-art" aria-hidden="true">
        <div class="aero-aurora" style="top: 130px"></div>
        <div class="aero-aurora aurora-2" style="top: 420px"></div>
        <div class="aero-bokeh"
          style="width:84px;height:84px;left:6%;top:16%;animation-duration:9s"></div>
        <div class="aero-bokeh"
          style="width:38px;height:38px;left:16%;top:38%;animation-duration:13s"></div>
        <div class="aero-bokeh"
          style="width:56px;height:56px;right:9%;top:24%;animation-duration:11s"></div>
        <div class="aero-bokeh"
          style="width:26px;height:26px;right:20%;top:52%;animation-duration:8s"></div>
        <div class="aero-fish-sky" style="right:5%;top:330px"></div>
      </div>
      <div class="aero-dragonfly" aria-hidden="true"></div>
      <header><h1>Watch a basement dry</h1></header>
      {render_aero_readouts(summary)}
      <div class="aero-scroll-hint" aria-hidden="true"><span></span></div>
    </div>
    <div class="zone-under">
      {charts_html}
      <footer>
        <p>Data to {latest_reading}</p>
        <p class="sources">Indoor readings come from thermometer&ndash;hygrometer sensors in the
        basement, bedroom, and living room. Outdoor humidity comes from the Open-Meteo weather
        archive. Rainfall comes from a nearby Environment Agency rain gauge.</p>{tank_footer_html}
      </footer>
    </div>
  </main>
  {render_chart_runtime_scripts()}
</body>
</html>
"""


def render_caveat_list(summary: SiteAnalysisSummary, use_report_text: bool) -> str:
    return "\n".join(
        f"""
        <article class="panel">
          <h3>{html.escape(caveat.short_label)}</h3>
          <p>{html.escape(caveat.report_text if use_report_text else caveat.dashboard_text)}</p>
        </article>
        """
        for caveat in summary.caveats
    )


def render_uncertainty_table(summary: SiteAnalysisSummary) -> str:
    rows = "\n".join(
        f"""
        <tr>
          <td>{html.escape(row.component)}</td>
          <td>{html.escape(row.applies_to)}</td>
          <td>{html.escape(row.treatment)}</td>
          <td>{"yes" if row.included_in_headline_interval else "no"}</td>
        </tr>
        """
        for row in summary.uncertainty_budget
    )
    return f"""
    <table>
      <thead>
        <tr>
          <th>Component</th>
          <th>Applies to</th>
          <th>Treatment</th>
          <th>In headline interval</th>
        </tr>
      </thead>
      <tbody>{rows}</tbody>
    </table>
    """


def render_physics_report_html(summary: SiteAnalysisSummary) -> str:
    generated_at = format_timestamp(summary.metadata.generated_at)
    data_window = (
        f"{format_timestamp(summary.metadata.data_window_start)} to "
        f"{format_timestamp(summary.metadata.data_window_end)}"
    )
    source_list = "".join(
        f"<li>{html.escape(source)}</li>" for source in summary.metadata.weather_sources
    )
    chart_html = "\n".join(
        f"<h2>{html.escape(chart.title)}</h2>{render_chart_spec(chart)}"
        for chart in summary.report_charts
    )
    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Basement Physics And Metrology Report</title>
  <link rel="icon" href="data:,">
  <style>
    {render_chart_styles()}
    :root {{
      color-scheme: light;
      --ink: #18212f;
      --muted: #5d6878;
      --line: #d8dee8;
      --soft: #f4f7f9;
      --accent: #1f766f;
    }}
    * {{ box-sizing: border-box; }}
    body {{
      margin: 0;
      font: 15px/1.55 -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
      color: var(--ink);
      background: #ffffff;
    }}
    header {{
      border-bottom: 1px solid var(--line);
      padding: 18px 22px 14px;
    }}
    main {{
      max-width: 980px;
      padding: 18px 22px 42px;
    }}
    h1 {{ margin: 0 0 4px; font-size: 24px; letter-spacing: 0; }}
    h2 {{ margin: 30px 0 10px; font-size: 18px; letter-spacing: 0; }}
    h3 {{ margin: 0 0 7px; font-size: 14px; letter-spacing: 0; }}
    a {{ color: var(--accent); }}
    .subtle, .panel p {{ color: var(--muted); }}
    .note {{
      border-left: 4px solid var(--accent);
      background: var(--soft);
      padding: 10px 12px;
      max-width: 920px;
    }}
    .panel-grid {{
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(260px, 1fr));
      gap: 10px;
    }}
    .panel {{
      border: 1px solid var(--line);
      border-radius: 8px;
      padding: 11px 12px;
      background: #fff;
    }}
    .panel p {{ margin: 0; }}
    .chart {{
      display: block;
      width: 100%;
      height: auto;
      border: 1px solid var(--line);
      border-radius: 8px;
      background: #fff;
    }}
    .plot-bg {{ fill: #fbfcfd; }}
    .grid {{ stroke: #e7ebf0; stroke-width: 1; }}
    .axis {{ stroke: #9aa4b2; stroke-width: 1; }}
    .event-line {{ stroke: #374151; stroke-width: 1; stroke-dasharray: 4 4; opacity: .5; }}
    .series-line {{ fill: none; stroke-width: 2; vector-effect: non-scaling-stroke; }}
    .axis-label, .axis-title {{ fill: var(--muted); font-size: 12px; }}
    .legend {{
      display: flex;
      flex-wrap: wrap;
      gap: 10px 16px;
      margin: 5px 0 7px;
      color: var(--muted);
    }}
    .legend-item {{ display: inline-flex; align-items: center; gap: 6px; }}
    .legend-swatch {{ display: inline-block; width: 22px; height: 3px; }}
    table {{
      width: 100%;
      border-collapse: collapse;
      font-size: 13px;
    }}
    th, td {{
      border-bottom: 1px solid var(--line);
      padding: 7px 8px;
      text-align: left;
      vertical-align: top;
    }}
    .table-wrap {{ overflow-x: auto; border: 1px solid var(--line); border-radius: 8px; }}
    code {{ background: var(--soft); padding: 1px 4px; border-radius: 4px; }}
    @media (max-width: 760px) {{
      header, main {{ padding-left: 14px; padding-right: 14px; }}
      h1 {{ font-size: 21px; }}
    }}
  </style>
</head>
<body>
  <header>
    <h1>Basement physics and metrology report</h1>
    <div class="subtle">Generated {generated_at}; data window {html.escape(data_window)}.</div>
  </header>
  <main>
    <p><a href="index.html">Back to dashboard</a></p>
    <p class="note">
      Explains the calculation model, evidence limits, and caveats behind the dashboard.
      Current intervals are not yet numeric GUM-style intervals; qualitative caveats remain
      separate from measurement uncertainty.
    </p>

    <h2>Psychrometric Model</h2>
    <p>
      Absolute humidity is calculated from temperature and relative humidity using a
      Magnus saturation vapour pressure approximation. The dashboard and this report consume
      the same derived absolute-humidity values and event-bounded summaries.
    </p>

    <h2>Sources</h2>
    <ul>{source_list}</ul>

    <h2>Hypothesis Evidence</h2>
    <section class="panel-grid">{render_hypothesis_panel(summary)}</section>

    {chart_html}

    <h2>Event-Bounded Period Metrics</h2>
    <div class="table-wrap">
      {render_period_table(summary.period_summaries, include_flags=True)}
    </div>

    <h2>Uncertainty Budget</h2>
    <div class="table-wrap">{render_uncertainty_table(summary)}</div>

    <h2>Caveats</h2>
    <section class="panel-grid">{render_caveat_list(summary, use_report_text=True)}</section>
  </main>
  {render_chart_runtime_scripts()}
</body>
</html>
"""


def render_site_pages(summary: SiteAnalysisSummary) -> dict[str, str]:
    """Render every published site page to a relative object path -> HTML string mapping.

    This is the render/write seam: callers that need the bytes without a filesystem
    destination (for example a hosted job uploading straight to R2) can call this function
    directly and skip `write_site_pages` entirely.
    """
    return {
        "index.html": render_index_html(summary),
    }


def render_private_report_pages(summary: SiteAnalysisSummary) -> dict[str, str]:
    """Render local-only analysis pages that are not part of the public site."""
    return {"physics-report.html": render_physics_report_html(summary)}


def write_site_pages(pages: Mapping[str, str], output_dir: Path) -> dict[str, Path]:
    """Persist a rendered-page mapping under `output_dir`, keyed by relative object path."""
    output_dir.mkdir(parents=True, exist_ok=True)
    written_paths: dict[str, Path] = {}
    for relative_path, page_content in pages.items():
        destination_path = output_dir / relative_path
        destination_path.parent.mkdir(parents=True, exist_ok=True)
        destination_path.write_text(page_content, encoding="utf-8")
        written_paths[relative_path] = destination_path
    return written_paths


def copy_site_assets(output_dir: Path) -> None:
    """Copy the committed static asset tree into a built site."""
    shutil.copytree(SITE_ASSETS_DIR, output_dir, dirs_exist_ok=True)


def build_static_site(
    data_dir: Path,
    output_dir: Path,
    refresh_weather: bool = False,
    curated_dataset_dir: CuratedDataRoot | None = None,
    rebuild_curated_dataset: bool = True,
    phase_recorder: PhaseRecorder | None = None,
    include_private_report: bool = False,
) -> BuildResult:
    recorder = phase_recorder if phase_recorder is not None else PhaseRecorder()
    resolved_curated_dataset_dir = (
        curated_dataset_dir if curated_dataset_dir is not None else output_dir / "curated-data"
    )

    if rebuild_curated_dataset:
        if isinstance(resolved_curated_dataset_dir, str):
            raise ValueError(
                "Rebuilding the curated dataset needs a local --curated-data-dir; "
                "an s3:// location can only be read with --reuse-curated."
            )
        with recorder.phase("load-sensor-csvs"):
            sensor_readings_from_csv = load_sensor_readings(data_dir)
        if not sensor_readings_from_csv:
            raise ValueError(f"No sensor readings found in {data_dir}")

        events_from_csv = load_events(data_dir)
        dataset_start = min(reading.timestamp for reading in sensor_readings_from_csv)
        dataset_end = max(reading.timestamp for reading in sensor_readings_from_csv)
        cache_dir = output_dir / "cache"
        with recorder.phase("fetch-open-meteo-weather"):
            weather_hours_from_api = fetch_open_meteo_weather(
                start_date=dataset_start.date(),
                end_date=dataset_end.date(),
                cache_dir=cache_dir,
                refresh=refresh_weather,
            )
        with recorder.phase("fetch-environment-agency-rainfall"):
            rain_readings_from_api = fetch_environment_agency_rainfall(
                start_date=dataset_start.date(),
                end_date=dataset_end.date(),
                cache_dir=cache_dir,
                refresh=refresh_weather,
            )
        with recorder.phase("write-curated-parquet"):
            write_curated_dataset(
                dataset_dir=resolved_curated_dataset_dir,
                sensor_readings=sensor_readings_from_csv,
                events=events_from_csv,
                weather_hours=weather_hours_from_api,
                rain_readings=rain_readings_from_api,
            )

    with recorder.phase("load-curated-parquet"):
        curated_dataset = load_curated_dataset(resolved_curated_dataset_dir)
    sensor_readings = list(curated_dataset.sensor_readings)
    if not sensor_readings:
        raise ValueError(f"No curated sensor readings found in {resolved_curated_dataset_dir}")

    with recorder.phase("build-summary"):
        summary = build_site_analysis_summary(
            sensor_readings=sensor_readings,
            events=curated_dataset.events,
            weather_hours=curated_dataset.weather_hours,
            rain_readings=curated_dataset.rain_readings,
            input_files=curated_dataset.parquet_files,
            event_timeline_source=join_curated_data_path(resolved_curated_dataset_dir, "events"),
        )

    with recorder.phase("render-site"):
        rendered_pages = render_site_pages(summary)
        if include_private_report:
            rendered_pages = rendered_pages | render_private_report_pages(summary)
    with recorder.phase("write-site"):
        written_paths = write_site_pages(rendered_pages, output_dir)
        copy_site_assets(output_dir)
    return BuildResult(
        index_path=written_paths["index.html"],
        private_report_path=written_paths.get("physics-report.html"),
        curated_dataset_dir=resolved_curated_dataset_dir,
        sensor_row_count=len(sensor_readings),
        weather_hour_count=len(curated_dataset.weather_hours),
        rain_reading_count=len(curated_dataset.rain_readings),
        newest_sensor_reading=max(reading.timestamp for reading in sensor_readings),
    )
