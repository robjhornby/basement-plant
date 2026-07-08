from __future__ import annotations

import csv
import html
import json
import math
import re
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
    report_path: Path
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


def chart_timestamp_seconds(timestamp: datetime) -> float:
    local_zone = ZoneInfo(LOCAL_TIMEZONE)
    aware_timestamp = (
        timestamp.replace(tzinfo=local_zone)
        if timestamp.tzinfo is None
        else timestamp.astimezone(local_zone)
    )
    return aware_timestamp.timestamp()


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
        data.append([values_by_timestamp.get(timestamp) for timestamp in all_timestamps])
        series_payload.append(
            {
                "name": chart_series.name,
                "color": chart_series.color,
                "kind": "line",
                "digits": 2,
            }
        )
        if chart_series.min_points and chart_series.max_points:
            min_values_by_timestamp = dict(chart_series.min_points)
            max_values_by_timestamp = dict(chart_series.max_points)
            bands_payload.append(
                {
                    "name": chart_series.name,
                    "color": chart_series.color,
                    "lower": [
                        min_values_by_timestamp.get(timestamp) for timestamp in all_timestamps
                    ],
                    "upper": [
                        max_values_by_timestamp.get(timestamp) for timestamp in all_timestamps
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
    payload: dict[str, JsonValue] = {
        "id": chart_id,
        "title": chart.title,
        "yLabel": chart.y_label,
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
        "yLabel": rain_chart.y_label,
        "height": rain_chart.height,
        "data": [
            [chart_timestamp_seconds(timestamp) for timestamp, _value in points],
            [value for _timestamp, value in points],
        ],
        "series": [
            {
                "name": "EA rainfall",
                "color": "#2563eb",
                "kind": "bar",
                "digits": 2,
            }
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

  var latestWindowLabel = "1w";
  var fullWindowLabel = "All";

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

  function formatSeriesValue(value, digits) {
    return value == null || !Number.isFinite(value) ? "n/a" : value.toFixed(digits);
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
            context.strokeStyle = "rgba(55, 65, 81, 0.45)";
            context.lineWidth = 1;
            context.setLineDash([4, 4]);
            events.forEach(function (event) {
              var xPosition = plot.valToPos(event.timestamp, "x", true);
              if (xPosition >= plot.bbox.left && xPosition <= plot.bbox.left + plot.bbox.width) {
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
              context.fillStyle = hexToRgba(band.color, 0.14);

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
                var upperY = plot.valToPos(upper, "y", true);
                var lowerY = plot.valToPos(lower, "y", true);
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
        stroke: series.color,
        fill: series.kind === "bar" ? series.color : undefined,
        width: series.kind === "bar" ? 0 : 2,
        points: { show: false },
        value: function (_plot, value) {
          return formatSeriesValue(value, series.digits);
        }
      };
      if (series.kind === "bar") {
        options.paths = uPlot.paths.bars({ size: [0.74, Infinity, 1] });
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

  function valueBounds(payload) {
    var values = [];
    payload.data.slice(1).forEach(function (seriesValues) {
      values = values.concat(seriesValues);
    });
    (payload.bands || []).forEach(function (band) {
      values = values.concat(band.lower, band.upper);
    });
    var finiteValues = values.filter(function (value) {
      return value != null && Number.isFinite(value);
    });
    if (finiteValues.length === 0) {
      return { minimum: 0, maximum: 1 };
    }
    var minimum = Math.min.apply(null, finiteValues);
    var maximum = Math.max.apply(null, finiteValues);
    if (minimum === maximum) {
      return { minimum: minimum - 1, maximum: maximum + 1 };
    }
    var padding = (maximum - minimum) * 0.08;
    return { minimum: minimum - padding, maximum: maximum + padding };
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
    var controls = document.createElement("div");
    controls.className = "chart-actions";
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
    frame.insertBefore(controls, frame.firstChild);
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

  function renderChart(frame) {
    var payloadScript = document.getElementById(frame.dataset.chartPayload);
    if (payloadScript == null) {
      return;
    }
    var payload = JSON.parse(payloadScript.textContent);
    normalizeLineGaps(payload);
    var host = frame.querySelector(".interactive-chart");
    var bounds = dataBounds(payload);
    var yBounds = valueBounds(payload);
    var options = {
      title: payload.title,
      width: Math.max(320, host.clientWidth || frame.clientWidth || 720),
      height: payload.height,
      scales: {
        x: { time: true, min: bounds.latestMinimum, max: bounds.maximum }
      },
      axes: [
        {},
        { label: payload.yLabel, size: 58 }
      ],
      cursor: {
        drag: { x: true, y: false, setScale: true },
        focus: { prox: 24 }
      },
      legend: { show: true, live: true },
      series: makeSeriesOptions(payload),
      plugins: [
        rangeBandPlugin(payload.bands || [], payload.data[0]),
        eventMarkerPlugin(payload.events)
      ]
    };
    if (payload.series.some(function (series) { return series.kind === "bar"; })) {
      options.scales.y = { range: function (_plot, minimum, maximum) {
        return [0, Math.max(1, maximum * 1.12)];
      } };
    } else {
      options.scales.y = { range: function () {
        return [yBounds.minimum, yBounds.maximum];
      } };
    }
    var plot = new uPlot(options, payload.data, host);
    addRangeControls(frame, plot, bounds);
    addWheelNavigation(frame, plot, bounds);
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


def render_index_html(summary: SiteAnalysisSummary) -> str:
    cards_html = "\n".join(
        render_metric_card(card.label, card.value) for card in summary.metric_cards
    )
    charts_by_title = {chart.title: chart for chart in summary.dashboard_charts}
    daily_chart = render_chart_spec(charts_by_title["Daily Basement Trends"])
    humidity_chart = render_chart_spec(charts_by_title["Basement Versus Outdoor Moisture"])
    raw_sensor_chart = render_chart_spec(charts_by_title["Raw Sensor Context"])
    generated_at = format_timestamp(summary.metadata.generated_at)
    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Basement Dampness</title>
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
      font: 14px/1.45 -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
      color: var(--ink);
      background: #ffffff;
    }}
    header {{
      border-bottom: 1px solid var(--line);
      padding: 18px 22px 14px;
    }}
    main {{
      max-width: 1180px;
      padding: 18px 22px 36px;
    }}
    h1 {{
      margin: 0 0 4px;
      font-size: 24px;
      letter-spacing: 0;
    }}
    h2 {{
      margin: 28px 0 10px;
      font-size: 18px;
      letter-spacing: 0;
    }}
    h3 {{
      margin: 0 0 7px;
      font-size: 14px;
      letter-spacing: 0;
    }}
    .subtle {{ color: var(--muted); }}
    a {{ color: var(--accent); }}
    .cards {{
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(172px, 1fr));
      gap: 10px;
      margin: 0 0 18px;
    }}
    .card, .panel {{
      border: 1px solid var(--line);
      border-radius: 8px;
      padding: 11px 12px;
      background: #fff;
    }}
    .label {{
      color: var(--muted);
      font-size: 12px;
    }}
    .value {{
      margin-top: 5px;
      font-size: 20px;
      font-weight: 650;
      letter-spacing: 0;
      overflow-wrap: anywhere;
    }}
    .report-link {{
      margin: 0 0 18px;
      font-size: 13px;
    }}
    .panel-grid {{
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(260px, 1fr));
      gap: 10px;
    }}
    .panel p {{ margin: 0; color: var(--muted); }}
    .chart {{
      display: block;
      width: 100%;
      height: auto;
      border: 1px solid var(--line);
      border-radius: 8px;
      background: #fff;
    }}
    .short-chart {{ margin-top: 8px; }}
    .plot-bg {{ fill: #fbfcfd; }}
    .grid {{ stroke: #e7ebf0; stroke-width: 1; }}
    .axis {{ stroke: #9aa4b2; stroke-width: 1; }}
    .event-line {{ stroke: #374151; stroke-width: 1; stroke-dasharray: 4 4; opacity: .5; }}
    .series-line {{ fill: none; stroke-width: 2; vector-effect: non-scaling-stroke; }}
    .axis-label, .axis-title {{ fill: var(--muted); font-size: 12px; }}
    .rain-bar {{ fill: #2563eb; opacity: .72; }}
    .legend {{
      display: flex;
      flex-wrap: wrap;
      gap: 10px 16px;
      margin: 5px 0 7px;
      color: var(--muted);
    }}
    .legend-item {{
      display: inline-flex;
      align-items: center;
      gap: 6px;
    }}
    .legend-swatch {{
      display: inline-block;
      width: 22px;
      height: 3px;
    }}
    table {{
      width: 100%;
      border-collapse: collapse;
      font-size: 13px;
    }}
    th, td {{
      border-bottom: 1px solid var(--line);
      padding: 7px 8px;
      text-align: right;
      white-space: nowrap;
    }}
    th:first-child, td:first-child {{ text-align: left; }}
    .table-wrap {{ overflow-x: auto; border: 1px solid var(--line); border-radius: 8px; }}
    @media (max-width: 760px) {{
      header, main {{ padding-left: 14px; padding-right: 14px; }}
      h1 {{ font-size: 21px; }}
      .value {{ font-size: 18px; }}
    }}
  </style>
</head>
<body>
  <header>
    <h1>Basement dampness</h1>
    <div class="subtle">
      Updated {generated_at}; STH51 sensors, Open-Meteo humidity, and Environment Agency rainfall.
    </div>
  </header>
  <main>
    <section class="cards">
      {cards_html}
    </section>

    <p class="report-link subtle"><a href="physics-report.html">Physics and metrology report</a></p>

    <h2>Hypothesis Evidence</h2>
    <section class="panel-grid">{render_hypothesis_panel(summary)}</section>

    <h2>Daily Basement Trends</h2>
    {daily_chart}

    <h2>Basement Versus Outdoor Moisture</h2>
    {humidity_chart}
    {render_rain_chart_spec(summary.rain_chart)}

    <h2>Raw Sensor Context</h2>
    {raw_sensor_chart}

    <h2>Event-Bounded Period Metrics</h2>
    <div class="table-wrap">{render_period_table(summary.period_summaries)}</div>
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
        "physics-report.html": render_physics_report_html(summary),
    }


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


def build_static_site(
    data_dir: Path,
    output_dir: Path,
    refresh_weather: bool = False,
    curated_dataset_dir: CuratedDataRoot | None = None,
    rebuild_curated_dataset: bool = True,
    phase_recorder: PhaseRecorder | None = None,
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
    with recorder.phase("write-site"):
        written_paths = write_site_pages(rendered_pages, output_dir)
    return BuildResult(
        index_path=written_paths["index.html"],
        report_path=written_paths["physics-report.html"],
        curated_dataset_dir=resolved_curated_dataset_dir,
        sensor_row_count=len(sensor_readings),
        weather_hour_count=len(curated_dataset.weather_hours),
        rain_reading_count=len(curated_dataset.rain_readings),
        newest_sensor_reading=max(reading.timestamp for reading in sensor_readings),
    )
