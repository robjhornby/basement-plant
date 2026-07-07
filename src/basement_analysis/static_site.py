from __future__ import annotations

import csv
import html
import json
import math
import re
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import date, datetime
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
from basement_analysis.summaries import (
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
ENVIRONMENT_AGENCY_RAIN_STATION = "270397"

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


def parse_local_datetime(raw_value: str) -> datetime:
    return datetime.strptime(raw_value, "%Y/%m/%d %H:%M")


def format_timestamp(timestamp: datetime) -> str:
    return timestamp.strftime("%Y-%m-%d %H:%M")


def format_optional_float(value: float | None, digits: int = 2) -> str:
    if value is None or not math.isfinite(value):
        return "n/a"
    return f"{value:.{digits}f}"


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
    temperatures = numeric_sequence(hourly["temperature_2m"])
    relative_humidities = numeric_sequence(hourly["relative_humidity_2m"])
    dew_points = numeric_sequence(hourly["dew_point_2m"])
    precipitation = numeric_sequence(hourly["precipitation"])
    rain = numeric_sequence(hourly["rain"])

    weather_hours: list[WeatherHour] = []
    for index, raw_time in enumerate(times):
        temperature_c = temperatures[index]
        relative_humidity_pct = relative_humidities[index]
        weather_hours.append(
            WeatherHour(
                timestamp=datetime.fromisoformat(raw_time),
                temperature_c=temperature_c,
                relative_humidity_pct=relative_humidity_pct,
                dew_point_c=dew_points[index],
                precipitation_mm=precipitation[index],
                rain_mm=rain[index],
                absolute_humidity_g_m3=absolute_humidity_g_m3(temperature_c, relative_humidity_pct),
            )
        )
    return weather_hours


def numeric_sequence(values: Sequence[object]) -> list[float]:
    result: list[float] = []
    for value in values:
        if isinstance(value, int | float):
            result.append(float(value))
        elif value is None:
            result.append(0.0)
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
    return render_time_series_svg(
        series=chart.series,
        events=chart.event_markers,
        y_label=chart.y_label,
        height=chart.height,
    )


def render_rain_svg(rain_chart: RainChartSpec) -> str:
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
  <title>Basement Dampness Local Prototype</title>
  <link rel="icon" href="data:,">
  <style>
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
    <h1>Basement dampness local prototype</h1>
    <div class="subtle">
      Generated {generated_at}; curated local sensors plus Open-Meteo outdoor humidity
      and Environment Agency rainfall.
    </div>
  </header>
  <main>
    <section class="cards">
      {cards_html}
    </section>

    <p class="note">
      Prototype scope: fast local feedback from visible calculations. Event boundaries come from
      the curated event timeline; weather is public contextual data,
      not a house-local calibrated station. See the
      <a href="physics-report.html">physics and metrology report</a>.
    </p>

    <h2>Hypothesis Evidence</h2>
    <section class="panel-grid">{render_hypothesis_panel(summary)}</section>

    <h2>Daily Basement Trends</h2>
    {daily_chart}

    <h2>Basement Versus Outdoor Moisture</h2>
    {humidity_chart}
    {render_rain_svg(summary.rain_chart)}

    <h2>Raw Sensor Context</h2>
    {raw_sensor_chart}

    <h2>Event-Bounded Period Metrics</h2>
    <div class="table-wrap">{render_period_table(summary.period_summaries)}</div>
  </main>
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
      This first report page explains the shared calculations behind the local dashboard.
      It is intentionally cautious: current intervals are not yet numeric GUM-style intervals,
      and qualitative caveats remain separate from measurement uncertainty.
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
) -> BuildResult:
    resolved_curated_dataset_dir = (
        curated_dataset_dir if curated_dataset_dir is not None else output_dir / "curated-data"
    )

    if rebuild_curated_dataset:
        if isinstance(resolved_curated_dataset_dir, str):
            raise ValueError(
                "Rebuilding the curated dataset needs a local --curated-data-dir; "
                "an s3:// location can only be read with --reuse-curated."
            )
        sensor_readings_from_csv = load_sensor_readings(data_dir)
        if not sensor_readings_from_csv:
            raise ValueError(f"No sensor readings found in {data_dir}")

        events_from_csv = load_events(data_dir)
        dataset_start = min(reading.timestamp for reading in sensor_readings_from_csv)
        dataset_end = max(reading.timestamp for reading in sensor_readings_from_csv)
        cache_dir = output_dir / "cache"
        weather_hours_from_api = fetch_open_meteo_weather(
            start_date=dataset_start.date(),
            end_date=dataset_end.date(),
            cache_dir=cache_dir,
            refresh=refresh_weather,
        )
        rain_readings_from_api = fetch_environment_agency_rainfall(
            start_date=dataset_start.date(),
            end_date=dataset_end.date(),
            cache_dir=cache_dir,
            refresh=refresh_weather,
        )
        write_curated_dataset(
            dataset_dir=resolved_curated_dataset_dir,
            sensor_readings=sensor_readings_from_csv,
            events=events_from_csv,
            weather_hours=weather_hours_from_api,
            rain_readings=rain_readings_from_api,
        )

    curated_dataset = load_curated_dataset(resolved_curated_dataset_dir)
    sensor_readings = list(curated_dataset.sensor_readings)
    if not sensor_readings:
        raise ValueError(f"No curated sensor readings found in {resolved_curated_dataset_dir}")

    summary = build_site_analysis_summary(
        sensor_readings=sensor_readings,
        events=curated_dataset.events,
        weather_hours=curated_dataset.weather_hours,
        rain_readings=curated_dataset.rain_readings,
        input_files=curated_dataset.parquet_files,
        event_timeline_source=join_curated_data_path(resolved_curated_dataset_dir, "events"),
    )

    written_paths = write_site_pages(render_site_pages(summary), output_dir)
    return BuildResult(
        index_path=written_paths["index.html"],
        report_path=written_paths["physics-report.html"],
        curated_dataset_dir=resolved_curated_dataset_dir,
        sensor_row_count=len(sensor_readings),
        weather_hour_count=len(curated_dataset.weather_hours),
        rain_reading_count=len(curated_dataset.rain_readings),
    )
