from __future__ import annotations

import csv
import html
import json
import math
from collections import defaultdict
from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path
from typing import cast
from urllib.parse import urlencode
from urllib.request import urlopen
from zoneinfo import ZoneInfo

CAVERSHAM_LATITUDE = 51.47
CAVERSHAM_LONGITUDE = -0.97
LOCAL_TIMEZONE = "Europe/London"
ENVIRONMENT_AGENCY_RAIN_STATION = "270397"

SENSOR_FILE_LABELS = {
    "Thermo-hygrometer_Export Data_202601031200_202607031200.csv": "Basement",
    "Thermo-hygrometer 2_Export Data_202601031200_202607031200.csv": "Bedroom",
    "Thermo-hygrometer 3_Export Data_202601031200_202607031200.csv": "Living room",
}

PERIOD_LABEL_BY_EVENT_TIME = {
    "2026-06-28 12:40": "clearing_in_progress",
    "2026-06-28 16:20": "bare_no_dehumidifier",
    "2026-07-01 21:00": "dehumidifier_centre_no_fan_sensor_original",
    "2026-07-02 14:35": "fan_added_sensor_move_transition",
    "2026-07-02 14:40": "fan_on_sensor_near_extractor_original_orientation",
    "2026-07-02 18:30": "fan_on_sensor_near_extractor_intake_away_uncertain",
    "2026-07-02 21:00": "fan_on_sensor_near_extractor_intake_toward_uncertain",
}


@dataclass(frozen=True)
class SensorReading:
    timestamp: datetime
    location: str
    temperature_c: float
    relative_humidity_pct: float
    absolute_humidity_g_m3: float


@dataclass(frozen=True)
class Event:
    timestamp: datetime
    description: str


@dataclass(frozen=True)
class WeatherHour:
    timestamp: datetime
    temperature_c: float
    relative_humidity_pct: float
    dew_point_c: float
    precipitation_mm: float
    rain_mm: float
    absolute_humidity_g_m3: float


@dataclass(frozen=True)
class RainReading:
    timestamp: datetime
    rainfall_mm: float


@dataclass(frozen=True)
class AggregatedReading:
    timestamp: datetime
    location: str
    temperature_c: float
    relative_humidity_pct: float
    absolute_humidity_g_m3: float


@dataclass(frozen=True)
class Period:
    label: str
    start: datetime
    end: datetime
    event: Event | None


@dataclass(frozen=True)
class PeriodSummary:
    label: str
    start: datetime
    end: datetime
    event_description: str
    sensor_samples: int
    mean_temperature_c: float | None
    mean_relative_humidity_pct: float | None
    mean_absolute_humidity_g_m3: float | None
    outdoor_mean_absolute_humidity_g_m3: float | None
    rain_mm: float


@dataclass(frozen=True)
class BuildResult:
    index_path: Path
    sensor_row_count: int
    weather_hour_count: int
    rain_reading_count: int


@dataclass(frozen=True)
class ChartSeries:
    name: str
    color: str
    points: Sequence[tuple[datetime, float]]


def absolute_humidity_g_m3(temperature_c: float, relative_humidity_pct: float) -> float:
    """Return water vapour density using the Magnus saturation vapour pressure formula."""
    saturation_hpa = 6.112 * math.exp((17.67 * temperature_c) / (temperature_c + 243.5))
    actual_hpa = (relative_humidity_pct / 100.0) * saturation_hpa
    return 216.7 * actual_hpa / (temperature_c + 273.15)


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
    for csv_path in sorted(data_dir.glob("Thermo-hygrometer*.csv")):
        location = SENSOR_FILE_LABELS.get(csv_path.name, csv_path.stem.split("_Export", 1)[0])
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


def floor_time(timestamp: datetime, bucket_minutes: int) -> datetime:
    minute = (timestamp.minute // bucket_minutes) * bucket_minutes
    return timestamp.replace(minute=minute, second=0, microsecond=0)


def aggregate_sensor_readings(
    readings: Iterable[SensorReading],
    bucket_minutes: int,
) -> list[AggregatedReading]:
    grouped: dict[tuple[str, datetime], list[SensorReading]] = defaultdict(list)
    for reading in readings:
        grouped[(reading.location, floor_time(reading.timestamp, bucket_minutes))].append(reading)

    aggregated: list[AggregatedReading] = []
    for (location, timestamp), bucket_readings in grouped.items():
        count = len(bucket_readings)
        aggregated.append(
            AggregatedReading(
                timestamp=timestamp,
                location=location,
                temperature_c=sum(reading.temperature_c for reading in bucket_readings) / count,
                relative_humidity_pct=sum(
                    reading.relative_humidity_pct for reading in bucket_readings
                )
                / count,
                absolute_humidity_g_m3=sum(
                    reading.absolute_humidity_g_m3 for reading in bucket_readings
                )
                / count,
            )
        )
    return sorted(aggregated, key=lambda reading: (reading.location, reading.timestamp))


def build_periods(
    events: Sequence[Event], dataset_start: datetime, dataset_end: datetime
) -> list[Period]:
    periods: list[Period] = []
    current_start = dataset_start
    current_label = "carpeted_baseline"
    current_event: Event | None = None

    for event in events:
        if dataset_start <= event.timestamp <= dataset_end:
            periods.append(
                Period(
                    label=current_label,
                    start=current_start,
                    end=event.timestamp,
                    event=current_event,
                )
            )
            current_start = event.timestamp
            current_label = PERIOD_LABEL_BY_EVENT_TIME.get(
                format_timestamp(event.timestamp), event.description
            )
            current_event = event

    periods.append(
        Period(label=current_label, start=current_start, end=dataset_end, event=current_event)
    )
    return [period for period in periods if period.end > period.start]


def summarize_periods(
    periods: Sequence[Period],
    basement_readings: Sequence[SensorReading],
    weather_hours: Sequence[WeatherHour],
    rain_readings: Sequence[RainReading],
) -> list[PeriodSummary]:
    summaries: list[PeriodSummary] = []
    for period in periods:
        indoor = [
            reading
            for reading in basement_readings
            if period.start <= reading.timestamp < period.end
        ]
        outdoor = [
            weather_hour
            for weather_hour in weather_hours
            if period.start <= weather_hour.timestamp < period.end
        ]
        rain = [
            reading for reading in rain_readings if period.start <= reading.timestamp < period.end
        ]
        summaries.append(
            PeriodSummary(
                label=period.label,
                start=period.start,
                end=period.end,
                event_description=period.event.description if period.event else "dataset start",
                sensor_samples=len(indoor),
                mean_temperature_c=mean_or_none(reading.temperature_c for reading in indoor),
                mean_relative_humidity_pct=mean_or_none(
                    reading.relative_humidity_pct for reading in indoor
                ),
                mean_absolute_humidity_g_m3=mean_or_none(
                    reading.absolute_humidity_g_m3 for reading in indoor
                ),
                outdoor_mean_absolute_humidity_g_m3=mean_or_none(
                    weather_hour.absolute_humidity_g_m3 for weather_hour in outdoor
                ),
                rain_mm=sum(reading.rainfall_mm for reading in rain),
            )
        )
    return summaries


def mean_or_none(values: Iterable[float]) -> float | None:
    collected = list(values)
    if not collected:
        return None
    return sum(collected) / len(collected)


def series_points(
    readings: Sequence[AggregatedReading],
    location: str,
    value_name: str,
) -> list[tuple[datetime, float]]:
    points: list[tuple[datetime, float]] = []
    for reading in readings:
        if reading.location != location:
            continue
        if value_name == "relative_humidity_pct":
            value = reading.relative_humidity_pct
        elif value_name == "absolute_humidity_g_m3":
            value = reading.absolute_humidity_g_m3
        elif value_name == "temperature_c":
            value = reading.temperature_c
        else:
            raise ValueError(f"Unknown reading value {value_name!r}")
        points.append((reading.timestamp, value))
    return points


def daily_basement_points(readings: Sequence[SensorReading]) -> list[AggregatedReading]:
    grouped: dict[date, list[SensorReading]] = defaultdict(list)
    for reading in readings:
        grouped[reading.timestamp.date()].append(reading)

    aggregated: list[AggregatedReading] = []
    for day, day_readings in grouped.items():
        timestamp = datetime.combine(day, datetime.min.time())
        count = len(day_readings)
        aggregated.append(
            AggregatedReading(
                timestamp=timestamp,
                location="Basement",
                temperature_c=sum(reading.temperature_c for reading in day_readings) / count,
                relative_humidity_pct=sum(reading.relative_humidity_pct for reading in day_readings)
                / count,
                absolute_humidity_g_m3=sum(
                    reading.absolute_humidity_g_m3 for reading in day_readings
                )
                / count,
            )
        )
    return sorted(aggregated, key=lambda reading: reading.timestamp)


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


def render_rain_svg(rain_readings: Sequence[RainReading], height: int = 180) -> str:
    hourly: dict[datetime, float] = defaultdict(float)
    for reading in rain_readings:
        hourly[floor_time(reading.timestamp, 60)] += reading.rainfall_mm
    points = sorted(hourly.items())
    if not points:
        return '<div class="empty">No Environment Agency rainfall readings available.</div>'

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
      <text class="axis-title" transform="translate(16 {height / 2:.1f}) rotate(-90)"
        text-anchor="middle">EA rain mm/hr</text>
    </svg>
    """


def render_period_table(summaries: Sequence[PeriodSummary]) -> str:
    rows = "\n".join(
        f"""
        <tr>
          <td>{html.escape(summary.label)}</td>
          <td>{format_timestamp(summary.start)}</td>
          <td>{format_timestamp(summary.end)}</td>
          <td>{summary.sensor_samples:,}</td>
          <td>{format_optional_float(summary.mean_relative_humidity_pct)}</td>
          <td>{format_optional_float(summary.mean_absolute_humidity_g_m3, 3)}</td>
          <td>{format_optional_float(summary.outdoor_mean_absolute_humidity_g_m3, 3)}</td>
          <td>{summary.rain_mm:.1f}</td>
        </tr>
        """
        for summary in summaries
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
        </tr>
      </thead>
      <tbody>{rows}</tbody>
    </table>
    """


def latest_reading(readings: Sequence[SensorReading], location: str) -> SensorReading:
    matching = [reading for reading in readings if reading.location == location]
    if not matching:
        raise ValueError(f"No readings for location {location!r}")
    return max(matching, key=lambda reading: reading.timestamp)


def period_by_label(summaries: Sequence[PeriodSummary], label: str) -> PeriodSummary | None:
    for summary in summaries:
        if summary.label == label:
            return summary
    return None


def render_hypothesis_panel(summaries: Sequence[PeriodSummary]) -> str:
    bare = period_by_label(summaries, "bare_no_dehumidifier")
    latest = period_by_label(summaries, "fan_on_sensor_near_extractor_intake_toward_uncertain")
    drying_delta = None
    outdoor_delta = None
    if bare and latest:
        if (
            bare.mean_absolute_humidity_g_m3 is not None
            and latest.mean_absolute_humidity_g_m3 is not None
        ):
            drying_delta = latest.mean_absolute_humidity_g_m3 - bare.mean_absolute_humidity_g_m3
        if (
            bare.outdoor_mean_absolute_humidity_g_m3 is not None
            and latest.outdoor_mean_absolute_humidity_g_m3 is not None
        ):
            outdoor_delta = (
                latest.outdoor_mean_absolute_humidity_g_m3
                - bare.outdoor_mean_absolute_humidity_g_m3
            )

    drying_text = (
        "Not enough event-bounded data yet."
        if drying_delta is None
        else (
            "Compatible with active basement drying: latest known operating period is "
            f"{abs(drying_delta):.2f} g/m3 lower than the bare/no-dehumidifier period."
            if drying_delta < 0
            else (
                "No drying improvement is visible in event-bounded absolute humidity yet: "
                f"latest period is {drying_delta:.2f} g/m3 higher."
            )
        )
    )
    weather_text = (
        "Outdoor absolute humidity is included for comparison; rain response remains exploratory."
        if outdoor_delta is None
        else (
            "Weather is a material confounder: outdoor absolute humidity changed by "
            f"{outdoor_delta:.2f} g/m3 between the same comparison periods."
        )
    )
    steady_text = (
        "Steady-state leak evidence is not separable yet; the periods are short and "
        "cross ventilation, "
        "sensor-placement, fan, and dehumidifier-orientation changes."
    )
    cards = [
        ("Basement drying", drying_text),
        ("Weather-related leaking", weather_text),
        ("Steady-state leaking", steady_text),
    ]
    return "\n".join(
        f"""
        <article class="panel">
          <h3>{html.escape(title)}</h3>
          <p>{html.escape(body)}</p>
        </article>
        """
        for title, body in cards
    )


def render_metric_card(label: str, value: str) -> str:
    return (
        '<div class="card">'
        f'<div class="label">{html.escape(label)}</div>'
        f'<div class="value">{html.escape(value)}</div>'
        "</div>"
    )


def render_index_html(
    sensor_readings: Sequence[SensorReading],
    events: Sequence[Event],
    weather_hours: Sequence[WeatherHour],
    rain_readings: Sequence[RainReading],
    period_summaries: Sequence[PeriodSummary],
) -> str:
    hourly_sensors = aggregate_sensor_readings(sensor_readings, bucket_minutes=60)
    daily_basement = daily_basement_points(
        [reading for reading in sensor_readings if reading.location == "Basement"]
    )
    latest_basement = latest_reading(sensor_readings, "Basement")
    latest_weather = weather_hours[-1] if weather_hours else None
    total_rain = sum(reading.rainfall_mm for reading in rain_readings)
    weather_points = [
        (weather_hour.timestamp, weather_hour.absolute_humidity_g_m3)
        for weather_hour in weather_hours
    ]

    raw_sensor_chart = render_time_series_svg(
        [
            ChartSeries(
                name="Basement RH",
                color="#1f766f",
                points=series_points(hourly_sensors, "Basement", "relative_humidity_pct"),
            ),
            ChartSeries(
                name="Bedroom RH",
                color="#8b5cf6",
                points=series_points(hourly_sensors, "Bedroom", "relative_humidity_pct"),
            ),
            ChartSeries(
                name="Living room RH",
                color="#c2410c",
                points=series_points(hourly_sensors, "Living room", "relative_humidity_pct"),
            ),
        ],
        events=events,
        y_label="Relative humidity %",
    )
    humidity_chart = render_time_series_svg(
        [
            ChartSeries(
                name="Basement absolute humidity",
                color="#1f766f",
                points=series_points(hourly_sensors, "Basement", "absolute_humidity_g_m3"),
            ),
            ChartSeries(
                name="Outdoor absolute humidity",
                color="#2563eb",
                points=weather_points,
            ),
        ],
        events=events,
        y_label="Absolute humidity g/m3",
    )
    daily_chart = render_time_series_svg(
        [
            ChartSeries(
                name="Daily basement RH",
                color="#1f766f",
                points=[
                    (reading.timestamp, reading.relative_humidity_pct) for reading in daily_basement
                ],
            ),
            ChartSeries(
                name="Daily basement absolute humidity",
                color="#8b5cf6",
                points=[
                    (reading.timestamp, reading.absolute_humidity_g_m3)
                    for reading in daily_basement
                ],
            ),
        ],
        events=events,
        y_label="Daily values",
        height=280,
    )

    generated_at = datetime.now().strftime("%Y-%m-%d %H:%M")
    latest_weather_text = (
        "n/a" if latest_weather is None else format_timestamp(latest_weather.timestamp)
    )
    latest_outdoor_ah = None if latest_weather is None else latest_weather.absolute_humidity_g_m3
    indoor_outdoor_delta = (
        None
        if latest_outdoor_ah is None
        else latest_basement.absolute_humidity_g_m3 - latest_outdoor_ah
    )
    cards_html = "\n".join(
        [
            render_metric_card(
                "Latest basement sample", format_timestamp(latest_basement.timestamp)
            ),
            render_metric_card("Basement RH", f"{latest_basement.relative_humidity_pct:.1f}%"),
            render_metric_card(
                "Basement AH",
                f"{latest_basement.absolute_humidity_g_m3:.2f} g/m3",
            ),
            render_metric_card("Latest weather hour", latest_weather_text),
            render_metric_card(
                "Outdoor AH",
                f"{format_optional_float(latest_outdoor_ah, 2)} g/m3",
            ),
            render_metric_card(
                "Indoor - outdoor AH",
                f"{format_optional_float(indoor_outdoor_delta, 2)} g/m3",
            ),
            render_metric_card("EA rain in dataset", f"{total_rain:.1f} mm"),
        ]
    )

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
      Generated {generated_at}; local CSV sensors plus Open-Meteo outdoor humidity
      and Environment Agency rainfall.
    </div>
  </header>
  <main>
    <section class="cards">
      {cards_html}
    </section>

    <p class="note">
      Prototype scope: fast local feedback from visible calculations. Event boundaries come from
      <code>data/basement_events.csv</code>; weather is public contextual data,
      not a house-local calibrated station.
    </p>

    <h2>Hypothesis Evidence</h2>
    <section class="panel-grid">{render_hypothesis_panel(period_summaries)}</section>

    <h2>Daily Basement Trends</h2>
    {daily_chart}

    <h2>Basement Versus Outdoor Moisture</h2>
    {humidity_chart}
    {render_rain_svg(rain_readings)}

    <h2>Raw Sensor Context</h2>
    {raw_sensor_chart}

    <h2>Event-Bounded Period Metrics</h2>
    <div class="table-wrap">{render_period_table(period_summaries)}</div>
  </main>
</body>
</html>
"""


def build_static_site(
    data_dir: Path, output_dir: Path, refresh_weather: bool = False
) -> BuildResult:
    sensor_readings = load_sensor_readings(data_dir)
    if not sensor_readings:
        raise ValueError(f"No sensor readings found in {data_dir}")

    events = load_events(data_dir)
    dataset_start = min(reading.timestamp for reading in sensor_readings)
    dataset_end = max(reading.timestamp for reading in sensor_readings)
    cache_dir = output_dir / "cache"
    weather_hours = fetch_open_meteo_weather(
        start_date=dataset_start.date(),
        end_date=dataset_end.date(),
        cache_dir=cache_dir,
        refresh=refresh_weather,
    )
    rain_readings = fetch_environment_agency_rainfall(
        start_date=dataset_start.date(),
        end_date=dataset_end.date(),
        cache_dir=cache_dir,
        refresh=refresh_weather,
    )

    basement_readings = [reading for reading in sensor_readings if reading.location == "Basement"]
    periods = build_periods(events, dataset_start, dataset_end)
    period_summaries = summarize_periods(
        periods=periods,
        basement_readings=basement_readings,
        weather_hours=weather_hours,
        rain_readings=rain_readings,
    )

    output_dir.mkdir(parents=True, exist_ok=True)
    index_path = output_dir / "index.html"
    index_path.write_text(
        render_index_html(
            sensor_readings=sensor_readings,
            events=events,
            weather_hours=weather_hours,
            rain_readings=rain_readings,
            period_summaries=period_summaries,
        ),
        encoding="utf-8",
    )
    return BuildResult(
        index_path=index_path,
        sensor_row_count=len(sensor_readings),
        weather_hour_count=len(weather_hours),
        rain_reading_count=len(rain_readings),
    )
