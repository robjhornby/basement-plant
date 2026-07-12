from __future__ import annotations

import math
from collections import defaultdict
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Literal

ENVIRONMENT_AGENCY_RAIN_STATION = "270397"

PERIOD_LABEL_BY_EVENT_TIME = {
    "2026-06-28 12:40": "clearing_in_progress",
    "2026-06-28 16:20": "bare_no_dehumidifier",
    "2026-07-01 21:00": "dehumidifier_centre_no_fan_sensor_original",
    "2026-07-02 14:35": "fan_added_sensor_move_transition",
    "2026-07-02 14:40": "fan_on_sensor_near_extractor_original_orientation",
    "2026-07-02 18:30": "fan_on_sensor_near_extractor_intake_away_uncertain",
    "2026-07-02 21:00": "fan_on_sensor_near_extractor_intake_toward_uncertain",
}

HypothesisName = Literal[
    "Basement drying",
    "Weather-related leaking",
    "Steady-state leaking",
]
AggregatedMetricName = Literal[
    "temperature_c",
    "relative_humidity_pct",
    "absolute_humidity_g_m3",
]
ChartSeriesKind = Literal["line", "bar"]
SENSOR_CHART_RECENT_DAYS = 31
SENSOR_CHART_RECENT_BUCKET_MINUTES = 10
SENSOR_CHART_HISTORICAL_BUCKET_MINUTES = 60


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
    min_temperature_c: float
    max_temperature_c: float
    relative_humidity_pct: float
    min_relative_humidity_pct: float
    max_relative_humidity_pct: float
    absolute_humidity_g_m3: float
    min_absolute_humidity_g_m3: float
    max_absolute_humidity_g_m3: float


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
    comparability_flags: tuple[str, ...]
    sensor_samples: int
    mean_temperature_c: float | None
    mean_relative_humidity_pct: float | None
    mean_absolute_humidity_g_m3: float | None
    outdoor_mean_absolute_humidity_g_m3: float | None
    rain_mm: float


@dataclass(frozen=True)
class SiteMetadata:
    generated_at: datetime
    data_window_start: datetime
    data_window_end: datetime
    analysis_version: str
    input_files: tuple[Path | str, ...]
    sensor_models: tuple[str, ...]
    weather_sources: tuple[str, ...]
    event_timeline_source: Path | str | None


@dataclass(frozen=True)
class MetricCard:
    label: str
    value: str
    caveat_ids: tuple[str, ...] = ()


@dataclass(frozen=True)
class ChartSeries:
    name: str
    color: str
    points: tuple[tuple[datetime, float], ...]
    min_points: tuple[tuple[datetime, float], ...] = ()
    max_points: tuple[tuple[datetime, float], ...] = ()
    caveat_ids: tuple[str, ...] = ()
    unit: str = ""
    kind: ChartSeriesKind = "line"
    scale: str = "y"


@dataclass(frozen=True)
class ChartAxis:
    scale: str
    label: str
    side: str = "left"
    show: bool = True


@dataclass(frozen=True)
class ChartSpec:
    title: str
    axes: tuple[ChartAxis, ...]
    series: tuple[ChartSeries, ...]
    height: int = 320
    event_markers: tuple[Event, ...] = ()
    caveat_ids: tuple[str, ...] = ()


@dataclass(frozen=True)
class RainChartSpec:
    title: str
    y_label: str
    hourly_points: tuple[tuple[datetime, float], ...]
    height: int = 180
    caveat_ids: tuple[str, ...] = ()


@dataclass(frozen=True)
class HypothesisAssessment:
    name: HypothesisName
    evidence_state: str
    summary: str
    caveat_ids: tuple[str, ...] = ()


@dataclass(frozen=True)
class Caveat:
    id: str
    short_label: str
    dashboard_text: str
    report_text: str
    applies_to: tuple[str, ...]


@dataclass(frozen=True)
class UncertaintyBudgetRow:
    component: str
    applies_to: str
    treatment: str
    included_in_headline_interval: bool
    caveat_ids: tuple[str, ...] = ()


@dataclass(frozen=True)
class SiteAnalysisSummary:
    metadata: SiteMetadata
    metric_cards: tuple[MetricCard, ...]
    period_summaries: tuple[PeriodSummary, ...]
    dashboard_charts: tuple[ChartSpec, ...]
    report_charts: tuple[ChartSpec, ...]
    rain_chart: RainChartSpec
    hypotheses: tuple[HypothesisAssessment, ...]
    caveats: tuple[Caveat, ...]
    uncertainty_budget: tuple[UncertaintyBudgetRow, ...]
    appendix_tables: Mapping[str, object]


def absolute_humidity_g_m3(temperature_c: float, relative_humidity_pct: float) -> float:
    """Return water vapour density using the Magnus saturation vapour pressure formula."""
    saturation_hpa = 6.112 * math.exp((17.67 * temperature_c) / (temperature_c + 243.5))
    actual_hpa = (relative_humidity_pct / 100.0) * saturation_hpa
    return 216.7 * actual_hpa / (temperature_c + 273.15)


def build_site_analysis_summary(
    sensor_readings: Sequence[SensorReading],
    events: Sequence[Event],
    weather_hours: Sequence[WeatherHour],
    rain_readings: Sequence[RainReading],
    input_files: Sequence[Path | str] = (),
    event_timeline_source: Path | str | None = None,
    generated_at: datetime | None = None,
) -> SiteAnalysisSummary:
    if not sensor_readings:
        raise ValueError("Cannot build a site analysis summary without sensor readings.")

    dataset_start = min(reading.timestamp for reading in sensor_readings)
    dataset_end = max(reading.timestamp for reading in sensor_readings)
    basement_readings = [reading for reading in sensor_readings if reading.location == "Basement"]
    periods = build_periods(events, dataset_start, dataset_end)
    period_summaries = tuple(
        summarize_periods(
            periods=periods,
            basement_readings=basement_readings,
            weather_hours=weather_hours,
            rain_readings=rain_readings,
        )
    )
    chart_sensors = aggregate_sensor_readings_for_chart(
        sensor_readings,
        recent_start=dataset_end - timedelta(days=SENSOR_CHART_RECENT_DAYS),
    )
    rain_chart = build_rain_chart(rain_readings)
    outdoor_absolute_humidity_points = tuple(
        (weather_hour.timestamp, weather_hour.absolute_humidity_g_m3)
        for weather_hour in weather_hours
    )
    outdoor_temperature_points = tuple(
        (weather_hour.timestamp, weather_hour.temperature_c) for weather_hour in weather_hours
    )
    outdoor_relative_humidity_points = tuple(
        (weather_hour.timestamp, weather_hour.relative_humidity_pct)
        for weather_hour in weather_hours
    )
    rain_points = rain_chart.hourly_points

    basement_conditions_chart = ChartSpec(
        title="Basement conditions",
        axes=(
            ChartAxis(scale="rh", label="Relative humidity / %", side="left"),
            ChartAxis(scale="temp", label="Temperature / °C", side="right"),
        ),
        height=340,
        event_markers=tuple(events),
        series=(
            ChartSeries(
                name="Relative humidity",
                color="#1f766f",
                points=tuple(series_points(chart_sensors, "Basement", "relative_humidity_pct")),
                min_points=tuple(
                    series_points(
                        chart_sensors,
                        "Basement",
                        "relative_humidity_pct",
                        statistic="min",
                    )
                ),
                max_points=tuple(
                    series_points(
                        chart_sensors,
                        "Basement",
                        "relative_humidity_pct",
                        statistic="max",
                    )
                ),
                unit="%",
                scale="rh",
            ),
            ChartSeries(
                name="Temperature",
                color="#c2410c",
                points=tuple(series_points(chart_sensors, "Basement", "temperature_c")),
                min_points=tuple(
                    series_points(chart_sensors, "Basement", "temperature_c", statistic="min")
                ),
                max_points=tuple(
                    series_points(chart_sensors, "Basement", "temperature_c", statistic="max")
                ),
                unit="°C",
                scale="temp",
            ),
        ),
    )
    absolute_humidity_chart = ChartSpec(
        title="Absolute humidity",
        axes=(
            ChartAxis(scale="ah", label="Absolute humidity / g/m³", side="left"),
            ChartAxis(scale="rain", label="", side="right", show=False),
        ),
        event_markers=tuple(events),
        series=(
            ChartSeries(
                name="Basement",
                color="#1f766f",
                points=tuple(series_points(chart_sensors, "Basement", "absolute_humidity_g_m3")),
                min_points=tuple(
                    series_points(
                        chart_sensors,
                        "Basement",
                        "absolute_humidity_g_m3",
                        statistic="min",
                    )
                ),
                max_points=tuple(
                    series_points(
                        chart_sensors,
                        "Basement",
                        "absolute_humidity_g_m3",
                        statistic="max",
                    )
                ),
                unit="g/m³",
                scale="ah",
            ),
            ChartSeries(
                name="Bedroom",
                color="#8b5cf6",
                points=tuple(series_points(chart_sensors, "Bedroom", "absolute_humidity_g_m3")),
                min_points=tuple(
                    series_points(
                        chart_sensors,
                        "Bedroom",
                        "absolute_humidity_g_m3",
                        statistic="min",
                    )
                ),
                max_points=tuple(
                    series_points(
                        chart_sensors,
                        "Bedroom",
                        "absolute_humidity_g_m3",
                        statistic="max",
                    )
                ),
                unit="g/m³",
                scale="ah",
            ),
            ChartSeries(
                name="Living room",
                color="#c2410c",
                points=tuple(series_points(chart_sensors, "Living room", "absolute_humidity_g_m3")),
                min_points=tuple(
                    series_points(
                        chart_sensors,
                        "Living room",
                        "absolute_humidity_g_m3",
                        statistic="min",
                    )
                ),
                max_points=tuple(
                    series_points(
                        chart_sensors,
                        "Living room",
                        "absolute_humidity_g_m3",
                        statistic="max",
                    )
                ),
                unit="g/m³",
                scale="ah",
            ),
            ChartSeries(
                name="Outdoor",
                color="#2563eb",
                points=outdoor_absolute_humidity_points,
                caveat_ids=("weather_source_mismatch",),
                unit="g/m³",
                scale="ah",
            ),
            ChartSeries(
                name="Rainfall",
                color="#2563eb",
                points=rain_points,
                caveat_ids=("weather_source_mismatch",),
                unit="mm per hour",
                kind="bar",
                scale="rain",
            ),
        ),
        caveat_ids=("weather_source_mismatch",),
    )
    temperature_chart = ChartSpec(
        title="Temperature",
        axes=(ChartAxis(scale="temp", label="Temperature / °C", side="left"),),
        height=280,
        event_markers=tuple(events),
        series=(
            ChartSeries(
                name="Basement",
                color="#1f766f",
                points=tuple(series_points(chart_sensors, "Basement", "temperature_c")),
                min_points=tuple(
                    series_points(chart_sensors, "Basement", "temperature_c", statistic="min")
                ),
                max_points=tuple(
                    series_points(chart_sensors, "Basement", "temperature_c", statistic="max")
                ),
                unit="°C",
                scale="temp",
            ),
            ChartSeries(
                name="Bedroom",
                color="#8b5cf6",
                points=tuple(series_points(chart_sensors, "Bedroom", "temperature_c")),
                min_points=tuple(
                    series_points(chart_sensors, "Bedroom", "temperature_c", statistic="min")
                ),
                max_points=tuple(
                    series_points(chart_sensors, "Bedroom", "temperature_c", statistic="max")
                ),
                unit="°C",
                scale="temp",
            ),
            ChartSeries(
                name="Living room",
                color="#c2410c",
                points=tuple(series_points(chart_sensors, "Living room", "temperature_c")),
                min_points=tuple(
                    series_points(
                        chart_sensors,
                        "Living room",
                        "temperature_c",
                        statistic="min",
                    )
                ),
                max_points=tuple(
                    series_points(
                        chart_sensors,
                        "Living room",
                        "temperature_c",
                        statistic="max",
                    )
                ),
                unit="°C",
                scale="temp",
            ),
            ChartSeries(
                name="Outdoor",
                color="#2563eb",
                points=outdoor_temperature_points,
                caveat_ids=("weather_source_mismatch",),
                unit="°C",
                scale="temp",
            ),
        ),
        caveat_ids=("weather_source_mismatch",),
    )
    relative_humidity_chart = ChartSpec(
        title="Relative humidity",
        axes=(ChartAxis(scale="rh", label="Relative humidity / %", side="left"),),
        height=280,
        event_markers=tuple(events),
        series=(
            ChartSeries(
                name="Basement",
                color="#1f766f",
                points=tuple(series_points(chart_sensors, "Basement", "relative_humidity_pct")),
                min_points=tuple(
                    series_points(
                        chart_sensors,
                        "Basement",
                        "relative_humidity_pct",
                        statistic="min",
                    )
                ),
                max_points=tuple(
                    series_points(
                        chart_sensors,
                        "Basement",
                        "relative_humidity_pct",
                        statistic="max",
                    )
                ),
                unit="%",
                scale="rh",
            ),
            ChartSeries(
                name="Bedroom",
                color="#8b5cf6",
                points=tuple(series_points(chart_sensors, "Bedroom", "relative_humidity_pct")),
                min_points=tuple(
                    series_points(
                        chart_sensors,
                        "Bedroom",
                        "relative_humidity_pct",
                        statistic="min",
                    )
                ),
                max_points=tuple(
                    series_points(
                        chart_sensors,
                        "Bedroom",
                        "relative_humidity_pct",
                        statistic="max",
                    )
                ),
                unit="%",
                scale="rh",
            ),
            ChartSeries(
                name="Living room",
                color="#c2410c",
                points=tuple(series_points(chart_sensors, "Living room", "relative_humidity_pct")),
                min_points=tuple(
                    series_points(
                        chart_sensors,
                        "Living room",
                        "relative_humidity_pct",
                        statistic="min",
                    )
                ),
                max_points=tuple(
                    series_points(
                        chart_sensors,
                        "Living room",
                        "relative_humidity_pct",
                        statistic="max",
                    )
                ),
                unit="%",
                scale="rh",
            ),
            ChartSeries(
                name="Outdoor",
                color="#2563eb",
                points=outdoor_relative_humidity_points,
                caveat_ids=("weather_source_mismatch",),
                unit="%",
                scale="rh",
            ),
        ),
        caveat_ids=("weather_source_mismatch", "sensor_placement_artifact"),
    )

    dashboard_charts = (
        basement_conditions_chart,
        absolute_humidity_chart,
        temperature_chart,
        relative_humidity_chart,
    )
    return SiteAnalysisSummary(
        metadata=SiteMetadata(
            generated_at=generated_at or datetime.now(),
            data_window_start=dataset_start,
            data_window_end=dataset_end,
            analysis_version="0.1.0",
            input_files=tuple(input_files),
            sensor_models=("STH51 thermohygrometer",),
            weather_sources=(
                "Open-Meteo archive hourly weather",
                f"Environment Agency station {ENVIRONMENT_AGENCY_RAIN_STATION} rainfall",
            ),
            event_timeline_source=event_timeline_source,
        ),
        metric_cards=build_metric_cards(sensor_readings, weather_hours, rain_readings),
        period_summaries=period_summaries,
        dashboard_charts=dashboard_charts,
        report_charts=dashboard_charts,
        rain_chart=rain_chart,
        hypotheses=build_hypothesis_assessments(period_summaries),
        caveats=build_caveats(),
        uncertainty_budget=build_uncertainty_budget(),
        appendix_tables={
            "event_timeline": tuple(events),
            "input_files": tuple(input_files),
        },
    )


def format_timestamp(timestamp: datetime) -> str:
    return timestamp.strftime("%Y-%m-%d %H:%M")


def format_optional_float(value: float | None, digits: int = 2) -> str:
    if value is None or not math.isfinite(value):
        return "n/a"
    return f"{value:.{digits}f}"


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
        aggregated.append(build_aggregated_reading(location, timestamp, bucket_readings))
    return sorted(aggregated, key=lambda reading: (reading.location, reading.timestamp))


def aggregate_sensor_readings_for_chart(
    readings: Iterable[SensorReading],
    recent_start: datetime,
    recent_bucket_minutes: int = SENSOR_CHART_RECENT_BUCKET_MINUTES,
    historical_bucket_minutes: int = SENSOR_CHART_HISTORICAL_BUCKET_MINUTES,
) -> list[AggregatedReading]:
    grouped: dict[tuple[str, datetime], list[SensorReading]] = defaultdict(list)
    for reading in readings:
        bucket_minutes = (
            recent_bucket_minutes
            if reading.timestamp >= recent_start
            else historical_bucket_minutes
        )
        grouped[(reading.location, floor_time(reading.timestamp, bucket_minutes))].append(reading)

    aggregated = [
        build_aggregated_reading(location, timestamp, bucket_readings)
        for (location, timestamp), bucket_readings in grouped.items()
    ]
    return sorted(aggregated, key=lambda reading: (reading.location, reading.timestamp))


def build_aggregated_reading(
    location: str,
    timestamp: datetime,
    readings: Sequence[SensorReading],
) -> AggregatedReading:
    count = len(readings)
    temperatures = [reading.temperature_c for reading in readings]
    relative_humidities = [reading.relative_humidity_pct for reading in readings]
    absolute_humidities = [reading.absolute_humidity_g_m3 for reading in readings]
    return AggregatedReading(
        timestamp=timestamp,
        location=location,
        temperature_c=sum(temperatures) / count,
        min_temperature_c=min(temperatures),
        max_temperature_c=max(temperatures),
        relative_humidity_pct=sum(relative_humidities) / count,
        min_relative_humidity_pct=min(relative_humidities),
        max_relative_humidity_pct=max(relative_humidities),
        absolute_humidity_g_m3=sum(absolute_humidities) / count,
        min_absolute_humidity_g_m3=min(absolute_humidities),
        max_absolute_humidity_g_m3=max(absolute_humidities),
    )


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
                comparability_flags=comparability_flags(period),
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


def comparability_flags(period: Period) -> tuple[str, ...]:
    flags: list[str] = []
    label_and_event = f"{period.label} {period.event.description if period.event else ''}".lower()
    if "sensor" in label_and_event:
        flags.append("sensor-placement artifact risk")
    if "fan" in label_and_event or "dehumidifier" in label_and_event:
        flags.append("dehumidifier control-cycle artifact risk")
    if "uncertain" in label_and_event:
        flags.append("event timestamp uncertainty")
    return tuple(flags)


def mean_or_none(values: Iterable[float]) -> float | None:
    collected = list(values)
    if not collected:
        return None
    return sum(collected) / len(collected)


def series_points(
    readings: Sequence[AggregatedReading],
    location: str,
    value_name: AggregatedMetricName,
    statistic: Literal["mean", "min", "max"] = "mean",
) -> list[tuple[datetime, float]]:
    points: list[tuple[datetime, float]] = []
    for reading in readings:
        if reading.location != location:
            continue
        points.append((reading.timestamp, aggregated_reading_value(reading, value_name, statistic)))
    return points


def aggregated_reading_value(
    reading: AggregatedReading,
    value_name: AggregatedMetricName,
    statistic: Literal["mean", "min", "max"],
) -> float:
    value_by_name: dict[tuple[AggregatedMetricName, Literal["mean", "min", "max"]], float] = {
        ("temperature_c", "mean"): reading.temperature_c,
        ("temperature_c", "min"): reading.min_temperature_c,
        ("temperature_c", "max"): reading.max_temperature_c,
        ("relative_humidity_pct", "mean"): reading.relative_humidity_pct,
        ("relative_humidity_pct", "min"): reading.min_relative_humidity_pct,
        ("relative_humidity_pct", "max"): reading.max_relative_humidity_pct,
        ("absolute_humidity_g_m3", "mean"): reading.absolute_humidity_g_m3,
        ("absolute_humidity_g_m3", "min"): reading.min_absolute_humidity_g_m3,
        ("absolute_humidity_g_m3", "max"): reading.max_absolute_humidity_g_m3,
    }
    return value_by_name[(value_name, statistic)]


def daily_basement_points(readings: Sequence[SensorReading]) -> list[AggregatedReading]:
    grouped: dict[date, list[SensorReading]] = defaultdict(list)
    for reading in readings:
        grouped[reading.timestamp.date()].append(reading)

    aggregated: list[AggregatedReading] = []
    for day, day_readings in grouped.items():
        timestamp = datetime.combine(day, datetime.min.time())
        aggregated.append(
            build_aggregated_reading(
                location="Basement",
                timestamp=timestamp,
                readings=day_readings,
            )
        )
    return sorted(aggregated, key=lambda reading: reading.timestamp)


def latest_reading(readings: Sequence[SensorReading], location: str) -> SensorReading:
    matching = [reading for reading in readings if reading.location == location]
    if not matching:
        raise ValueError(f"No readings for location {location!r}")
    return max(matching, key=lambda reading: reading.timestamp)


def build_metric_cards(
    sensor_readings: Sequence[SensorReading],
    weather_hours: Sequence[WeatherHour],
    rain_readings: Sequence[RainReading],
) -> tuple[MetricCard, ...]:
    latest_basement = latest_reading(sensor_readings, "Basement")
    latest_weather = weather_hours[-1] if weather_hours else None
    total_rain = sum(reading.rainfall_mm for reading in rain_readings)
    latest_weather_text = (
        "n/a" if latest_weather is None else format_timestamp(latest_weather.timestamp)
    )
    latest_outdoor_ah = None if latest_weather is None else latest_weather.absolute_humidity_g_m3
    indoor_outdoor_delta = (
        None
        if latest_outdoor_ah is None
        else latest_basement.absolute_humidity_g_m3 - latest_outdoor_ah
    )
    return (
        MetricCard("Latest basement sample", format_timestamp(latest_basement.timestamp)),
        MetricCard("Basement RH", f"{latest_basement.relative_humidity_pct:.1f}%"),
        MetricCard("Basement AH", f"{latest_basement.absolute_humidity_g_m3:.2f} g/m3"),
        MetricCard("Latest weather hour", latest_weather_text, ("weather_source_mismatch",)),
        MetricCard(
            "Outdoor AH",
            f"{format_optional_float(latest_outdoor_ah, 2)} g/m3",
            ("weather_source_mismatch",),
        ),
        MetricCard(
            "Indoor - outdoor AH",
            f"{format_optional_float(indoor_outdoor_delta, 2)} g/m3",
            ("weather_source_mismatch",),
        ),
        MetricCard("EA rain in dataset", f"{total_rain:.1f} mm", ("weather_source_mismatch",)),
    )


def build_rain_chart(rain_readings: Sequence[RainReading]) -> RainChartSpec:
    hourly: dict[datetime, float] = defaultdict(float)
    for reading in rain_readings:
        hourly[floor_time(reading.timestamp, 60)] += reading.rainfall_mm
    return RainChartSpec(
        title="Environment Agency Rainfall",
        y_label="Rainfall / mm per hour",
        hourly_points=tuple(sorted(hourly.items())),
        caveat_ids=("weather_source_mismatch",),
    )


def period_by_label(summaries: Sequence[PeriodSummary], label: str) -> PeriodSummary | None:
    for summary in summaries:
        if summary.label == label:
            return summary
    return None


def build_hypothesis_assessments(
    summaries: Sequence[PeriodSummary],
) -> tuple[HypothesisAssessment, ...]:
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
    return (
        HypothesisAssessment(
            name="Basement drying",
            evidence_state="exploratory",
            summary=drying_text,
            caveat_ids=("sensor_placement_artifact", "dehumidifier_control_cycle_artifact"),
        ),
        HypothesisAssessment(
            name="Weather-related leaking",
            evidence_state="exploratory",
            summary=weather_text,
            caveat_ids=("weather_source_mismatch",),
        ),
        HypothesisAssessment(
            name="Steady-state leaking",
            evidence_state="not separable yet",
            summary=steady_text,
            caveat_ids=("sensor_placement_artifact", "dehumidifier_control_cycle_artifact"),
        ),
    )


def build_caveats() -> tuple[Caveat, ...]:
    return (
        Caveat(
            id="consumer_sensor_specification",
            short_label="Consumer sensor specification",
            dashboard_text=(
                "STH51 readings use manufacturer-level accuracy, not a calibrated lab trace."
            ),
            report_text=(
                "The current uncertainty basis is the STH51 manufacturer specification and "
                "explicit assumptions. No sensor-specific calibration certificate is available."
            ),
            applies_to=("metrics", "periods", "charts"),
        ),
        Caveat(
            id="sensor_placement_artifact",
            short_label="Sensor-placement artifact risk",
            dashboard_text="Sensor moves and nearby airflow can create apparent humidity changes.",
            report_text=(
                "Some event-bounded comparisons cross sensor moves or altered nearby airflow. "
                "Those comparisons should be treated as placement-sensitive until a later "
                "analysis proves a measure robust across moves."
            ),
            applies_to=("periods", "hypotheses", "charts"),
        ),
        Caveat(
            id="dehumidifier_control_cycle_artifact",
            short_label="Dehumidifier control-cycle artifact risk",
            dashboard_text=(
                "Fan and dehumidifier cycling can dominate short-term humidity patterns."
            ),
            report_text=(
                "Short-term humidity and temperature movement can reflect dehumidifier control, "
                "tank state, fan airflow, and orientation rather than changed moisture ingress."
            ),
            applies_to=("periods", "hypotheses"),
        ),
        Caveat(
            id="weather_source_mismatch",
            short_label="Weather source mismatch",
            dashboard_text="Outdoor weather is public contextual data, not a calibrated station.",
            report_text=(
                "Open-Meteo and Environment Agency rainfall are used for area weather context. "
                "They may not match the exact outdoor air or rainfall experienced at the property."
            ),
            applies_to=("weather", "rain", "hypotheses"),
        ),
    )


def build_uncertainty_budget() -> tuple[UncertaintyBudgetRow, ...]:
    return (
        UncertaintyBudgetRow(
            component="STH51 temperature and RH manufacturer specification",
            applies_to="absolute humidity and event-bounded period means",
            treatment=(
                "Recognised qualitatively in this slice; numeric intervals come in a later pass."
            ),
            included_in_headline_interval=False,
            caveat_ids=("consumer_sensor_specification",),
        ),
        UncertaintyBudgetRow(
            component="Sensor placement and nearby airflow",
            applies_to="period comparisons and hypothesis assessments",
            treatment=(
                "Tracked as comparability flags and caveats, "
                "not as numeric measurement uncertainty."
            ),
            included_in_headline_interval=False,
            caveat_ids=("sensor_placement_artifact",),
        ),
    )
