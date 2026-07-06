from __future__ import annotations

from datetime import datetime
from pathlib import Path

from basement_analysis.static_site import (
    render_index_html,
    render_physics_report_html,
    render_site_pages,
    write_site_pages,
)
from basement_analysis.summaries import (
    Event,
    RainReading,
    SensorReading,
    WeatherHour,
    absolute_humidity_g_m3,
    build_site_analysis_summary,
)


def sensor_reading(
    raw_timestamp: str,
    location: str,
    temperature_c: float,
    relative_humidity_pct: float,
) -> SensorReading:
    absolute_humidity = absolute_humidity_g_m3(temperature_c, relative_humidity_pct)
    return SensorReading(
        timestamp=datetime.fromisoformat(raw_timestamp),
        location=location,
        temperature_c=temperature_c,
        relative_humidity_pct=relative_humidity_pct,
        absolute_humidity_g_m3=absolute_humidity,
    )


def weather_hour(
    raw_timestamp: str,
    temperature_c: float,
    relative_humidity_pct: float,
) -> WeatherHour:
    absolute_humidity = absolute_humidity_g_m3(temperature_c, relative_humidity_pct)
    return WeatherHour(
        timestamp=datetime.fromisoformat(raw_timestamp),
        temperature_c=temperature_c,
        relative_humidity_pct=relative_humidity_pct,
        dew_point_c=10.0,
        precipitation_mm=0.0,
        rain_mm=0.0,
        absolute_humidity_g_m3=absolute_humidity,
    )


def test_site_analysis_summary_builds_shared_dashboard_and_report_values() -> None:
    sensor_readings = [
        sensor_reading("2026-06-28T15:00:00", "Basement", 18.0, 88.0),
        sensor_reading("2026-06-28T17:00:00", "Basement", 18.5, 86.0),
        sensor_reading("2026-07-02T22:00:00", "Basement", 19.0, 72.0),
        sensor_reading("2026-07-02T23:00:00", "Basement", 19.0, 71.0),
        sensor_reading("2026-07-02T22:00:00", "Bedroom", 20.0, 60.0),
        sensor_reading("2026-07-02T22:00:00", "Living room", 21.0, 58.0),
    ]
    events = [
        Event(datetime.fromisoformat("2026-06-28T16:20:00"), "Bare floor exposed"),
        Event(datetime.fromisoformat("2026-07-02T21:00:00"), "Fan orientation uncertain"),
    ]
    weather_hours = [
        weather_hour("2026-06-28T15:00:00", 16.0, 70.0),
        weather_hour("2026-06-28T17:00:00", 16.0, 71.0),
        weather_hour("2026-07-02T22:00:00", 17.0, 68.0),
    ]
    rain_readings = [
        RainReading(datetime.fromisoformat("2026-07-02T22:10:00"), 0.4),
        RainReading(datetime.fromisoformat("2026-07-02T22:40:00"), 0.6),
    ]

    summary = build_site_analysis_summary(
        sensor_readings=sensor_readings,
        events=events,
        weather_hours=weather_hours,
        rain_readings=rain_readings,
        generated_at=datetime.fromisoformat("2026-07-05T12:00:00"),
    )

    assert [card.label for card in summary.metric_cards] == [
        "Latest basement sample",
        "Basement RH",
        "Basement AH",
        "Latest weather hour",
        "Outdoor AH",
        "Indoor - outdoor AH",
        "EA rain in dataset",
    ]
    assert [period.label for period in summary.period_summaries] == [
        "carpeted_baseline",
        "bare_no_dehumidifier",
        "fan_on_sensor_near_extractor_intake_toward_uncertain",
    ]
    assert summary.rain_chart.hourly_points == (
        (datetime.fromisoformat("2026-07-02T22:00:00"), 1.0),
    )
    assert summary.dashboard_charts[0].title == "Daily Basement Trends"
    assert "event timestamp uncertainty" in summary.period_summaries[-1].comparability_flags


def test_dashboard_and_report_render_from_shared_summary() -> None:
    sensor_readings = [
        sensor_reading("2026-06-28T15:00:00", "Basement", 18.0, 88.0),
        sensor_reading("2026-06-28T17:00:00", "Basement", 18.5, 86.0),
        sensor_reading("2026-07-02T22:00:00", "Basement", 19.0, 72.0),
        sensor_reading("2026-07-02T23:00:00", "Basement", 19.0, 71.0),
    ]
    summary = build_site_analysis_summary(
        sensor_readings=sensor_readings,
        events=[
            Event(datetime.fromisoformat("2026-06-28T16:20:00"), "Bare floor exposed"),
            Event(datetime.fromisoformat("2026-07-02T21:00:00"), "Fan orientation uncertain"),
        ],
        weather_hours=[weather_hour("2026-07-02T22:00:00", 17.0, 68.0)],
        rain_readings=[RainReading(datetime.fromisoformat("2026-07-02T22:10:00"), 0.4)],
        generated_at=datetime.fromisoformat("2026-07-05T12:00:00"),
    )

    dashboard_html = render_index_html(summary)
    report_html = render_physics_report_html(summary)

    assert 'href="physics-report.html"' in dashboard_html
    assert "Basement Versus Outdoor Moisture" in dashboard_html
    assert "Compatible with active basement drying" in dashboard_html
    assert 'href="index.html"' in report_html
    assert "Uncertainty Budget" in report_html
    assert "Comparability flags" in report_html
    assert "Compatible with active basement drying" in report_html


def test_render_site_pages_returns_relative_path_to_html_mapping() -> None:
    summary = build_site_analysis_summary(
        sensor_readings=[
            sensor_reading("2026-06-28T15:00:00", "Basement", 18.0, 88.0),
            sensor_reading("2026-07-02T22:00:00", "Basement", 19.0, 72.0),
        ],
        events=[Event(datetime.fromisoformat("2026-06-28T16:20:00"), "Bare floor exposed")],
        weather_hours=[weather_hour("2026-07-02T22:00:00", 17.0, 68.0)],
        rain_readings=[RainReading(datetime.fromisoformat("2026-07-02T22:10:00"), 0.4)],
        generated_at=datetime.fromisoformat("2026-07-05T12:00:00"),
    )

    pages = render_site_pages(summary)

    assert set(pages) == {"index.html", "physics-report.html"}
    assert pages["index.html"] == render_index_html(summary)
    assert pages["physics-report.html"] == render_physics_report_html(summary)


def test_write_site_pages_persists_mapping_under_output_dir(tmp_path: Path) -> None:
    pages = {"index.html": "<p>dashboard</p>", "nested/report.html": "<p>report</p>"}

    written_paths = write_site_pages(pages, tmp_path / "site")

    assert written_paths["index.html"] == tmp_path / "site" / "index.html"
    assert written_paths["nested/report.html"] == tmp_path / "site" / "nested" / "report.html"
    for relative_path, content in pages.items():
        assert written_paths[relative_path].read_text(encoding="utf-8") == content
