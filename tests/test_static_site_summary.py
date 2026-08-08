from __future__ import annotations

import json
import re
from datetime import date, datetime
from pathlib import Path
from typing import cast

import pytest

from basement_analysis.static_site import (
    fetch_open_meteo_weather,
    load_events,
    parse_local_datetime,
    render_index_html,
    render_physics_report_html,
    render_private_report_pages,
    render_site_pages,
    write_site_pages,
)
from basement_analysis.summaries import (
    Event,
    RainReading,
    SensorReading,
    SiteAnalysisSummary,
    WeatherHour,
    absolute_humidity_g_m3,
    build_site_analysis_summary,
)
from synthetic_tank_series import minutes_after_install, synthetic_series


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


def test_parse_local_datetime_accepts_minute_and_second_precision() -> None:
    assert parse_local_datetime("2026/06/28 12:40") == datetime(2026, 6, 28, 12, 40)
    assert parse_local_datetime("2026/07/05 00:51:03") == datetime(2026, 7, 5, 0, 51, 3)


def test_load_events_reads_seconds_precision_tank_full_rows(tmp_path: Path) -> None:
    (tmp_path / "basement_events.csv").write_text(
        "Time,Event\n"
        "2026/07/01 21:00,dehumidifier installed\n"
        "2026/07/05 00:51:03,dehumidifer tank full\n",
        encoding="utf-8",
    )

    events = load_events(tmp_path)

    assert [(event.timestamp, event.description) for event in events] == [
        (datetime(2026, 7, 1, 21, 0), "dehumidifier installed"),
        (datetime(2026, 7, 5, 0, 51, 3), "dehumidifer tank full"),
    ]


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


def visible_markup(rendered_html: str) -> str:
    return re.sub(
        r"<(script|style)\b.*?</\1>",
        "",
        rendered_html,
        flags=re.DOTALL | re.IGNORECASE,
    )


def chart_payload(rendered_html: str, title: str) -> dict[str, object]:
    for raw_payload in re.findall(
        r'<script type="application/json" id="[^"]+-payload">([^<]+)</script>',
        rendered_html,
    ):
        payload = json.loads(raw_payload)
        if payload["title"] == title:
            return payload
    raise AssertionError(f"No chart payload found for {title!r}")


def test_fetch_open_meteo_weather_drops_hours_with_null_values(tmp_path: Path) -> None:
    cache_dir = tmp_path / "cache"
    cache_path = cache_dir / "open_meteo_2026-07-03_2026-07-03.json"
    cache_path.parent.mkdir(parents=True, exist_ok=True)
    cache_path.write_text(
        json.dumps(
            {
                "hourly": {
                    "time": ["2026-07-03T00:00", "2026-07-03T01:00", "2026-07-03T02:00"],
                    "temperature_2m": [16.0, None, 15.5],
                    "relative_humidity_2m": [70.0, 71.0, 72.0],
                    "dew_point_2m": [10.0, 10.5, None],
                    "precipitation": [0.0, 0.1, 0.2],
                    "rain": [0.0, 0.1, 0.2],
                }
            }
        ),
        encoding="utf-8",
    )

    weather_hours = fetch_open_meteo_weather(
        start_date=date(2026, 7, 3),
        end_date=date(2026, 7, 3),
        cache_dir=cache_dir,
        refresh=False,
    )

    assert [hour.timestamp for hour in weather_hours] == [
        datetime.fromisoformat("2026-07-03T00:00:00")
    ]
    assert weather_hours[0].temperature_c == 16.0


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
    assert [chart.title for chart in summary.dashboard_charts] == [
        "Basement conditions",
        "Absolute humidity",
        "Temperature",
        "Relative humidity",
    ]
    assert "event timestamp uncertainty" in summary.period_summaries[-1].comparability_flags


def test_dashboard_chart_payload_matches_final_redesign_lineup() -> None:
    summary = build_site_analysis_summary(
        sensor_readings=[
            sensor_reading("2026-07-02T22:03:00", "Basement", 19.0, 70.0),
            sensor_reading("2026-07-02T22:03:00", "Bedroom", 20.0, 60.0),
            sensor_reading("2026-07-02T22:03:00", "Living room", 21.0, 58.0),
        ],
        events=[],
        weather_hours=[weather_hour("2026-07-02T22:00:00", 17.0, 68.0)],
        rain_readings=[RainReading(datetime.fromisoformat("2026-07-02T22:10:00"), 0.4)],
        generated_at=datetime.fromisoformat("2026-07-05T12:00:00"),
    )

    dashboard_html = render_index_html(summary)
    payloads = [
        chart_payload(dashboard_html, title)
        for title in (
            "Basement conditions",
            "Absolute humidity",
            "Temperature",
            "Relative humidity",
        )
    ]
    series_by_title = {
        str(payload["title"]): [
            str(series["name"]) for series in cast(list[dict[str, object]], payload["series"])
        ]
        for payload in payloads
    }
    absolute_humidity_payload = chart_payload(dashboard_html, "Absolute humidity")
    absolute_humidity_series = cast(list[dict[str, object]], absolute_humidity_payload["series"])
    rain_series = absolute_humidity_series[-1]
    axes = cast(list[dict[str, object]], absolute_humidity_payload["axes"])

    assert series_by_title == {
        "Basement conditions": ["Relative humidity", "Temperature"],
        "Absolute humidity": ["Basement", "Bedroom", "Living room", "Outdoor", "Rainfall"],
        "Temperature": ["Basement", "Bedroom", "Living room", "Outdoor"],
        "Relative humidity": ["Basement", "Bedroom", "Living room", "Outdoor"],
    }
    assert all(series["unit"] for series in absolute_humidity_series)
    assert rain_series["kind"] == "bar"
    assert rain_series["scale"] == "rain"
    assert rain_series["unit"] == "mm per hour"
    assert axes == [
        {
            "scale": "ah",
            "label": "Absolute humidity / g/m³",
            "side": "left",
            "show": True,
            "size": 56,
        },
        {"scale": "rain", "label": "", "side": "right", "show": False, "size": 0},
    ]
    assert "Daily Basement Trends" not in dashboard_html
    assert "Basement Versus Outdoor Moisture" not in dashboard_html
    assert "Raw Sensor Context" not in dashboard_html
    assert "formatSeriesValueWithUnit(value, series)" in dashboard_html


def test_dashboard_axes_use_verbatim_measure_slash_unit_labels() -> None:
    """Ticket-10 rule: each measure gets a dedicated axis titled '<measure> / <unit>'."""
    summary = build_site_analysis_summary(
        sensor_readings=[
            sensor_reading("2026-07-02T22:03:00", "Basement", 19.0, 70.0),
            sensor_reading("2026-07-02T22:03:00", "Bedroom", 20.0, 60.0),
            sensor_reading("2026-07-02T22:03:00", "Living room", 21.0, 58.0),
        ],
        events=[],
        weather_hours=[weather_hour("2026-07-02T22:00:00", 17.0, 68.0)],
        rain_readings=[RainReading(datetime.fromisoformat("2026-07-02T22:10:00"), 0.4)],
        generated_at=datetime.fromisoformat("2026-07-05T12:00:00"),
    )

    dashboard_html = render_index_html(summary)

    def axis_labels(title: str) -> list[tuple[str, str, bool]]:
        payload = chart_payload(dashboard_html, title)
        return [
            (str(axis["label"]), str(axis["side"]), bool(axis["show"]))
            for axis in cast(list[dict[str, object]], payload["axes"])
        ]

    assert axis_labels("Basement conditions") == [
        ("Relative humidity / %", "left", True),
        ("Temperature / °C", "right", True),
    ]
    assert axis_labels("Absolute humidity") == [
        ("Absolute humidity / g/m³", "left", True),
        ("", "right", False),
    ]
    assert axis_labels("Temperature") == [("Temperature / °C", "left", True)]
    assert axis_labels("Relative humidity") == [("Relative humidity / %", "left", True)]

    basement_conditions_series = cast(
        list[dict[str, object]],
        chart_payload(dashboard_html, "Basement conditions")["series"],
    )
    units_by_name = {
        str(series["name"]): str(series["unit"]) for series in basement_conditions_series
    }
    assert units_by_name == {
        "Relative humidity": "%",
        "Temperature": "°C",
    }
    assert "EA rain mm/hr" not in dashboard_html
    # Hover values keep the accepted unit glyphs and spacing rules.
    assert 'series.unit === "%" ? formattedValue + "%"' in dashboard_html


def test_sensor_chart_payload_uses_tiered_resolution_and_min_max_bands() -> None:
    summary = build_site_analysis_summary(
        sensor_readings=[
            sensor_reading("2026-05-01T05:34:00", "Basement", 17.0, 80.0),
            sensor_reading("2026-05-01T05:56:00", "Basement", 17.0, 82.0),
            sensor_reading("2026-07-02T22:03:00", "Basement", 19.0, 70.0),
            sensor_reading("2026-07-02T22:08:00", "Basement", 19.0, 74.0),
            sensor_reading("2026-07-02T22:11:00", "Basement", 19.0, 76.0),
            sensor_reading("2026-07-02T22:03:00", "Bedroom", 20.0, 60.0),
            sensor_reading("2026-07-02T22:03:00", "Living room", 21.0, 58.0),
        ],
        events=[],
        weather_hours=[weather_hour("2026-07-02T22:00:00", 17.0, 68.0)],
        rain_readings=[],
        generated_at=datetime.fromisoformat("2026-07-05T12:00:00"),
    )

    relative_humidity_chart = summary.dashboard_charts[3]
    basement_series = relative_humidity_chart.series[0]

    assert [timestamp for timestamp, _value in basement_series.points] == [
        datetime.fromisoformat("2026-05-01T05:00:00"),
        datetime.fromisoformat("2026-07-02T22:00:00"),
        datetime.fromisoformat("2026-07-02T22:10:00"),
    ]
    assert [value for _timestamp, value in basement_series.points] == [81.0, 72.0, 76.0]
    assert [value for _timestamp, value in basement_series.min_points] == [80.0, 70.0, 76.0]
    assert [value for _timestamp, value in basement_series.max_points] == [82.0, 74.0, 76.0]

    dashboard_html = render_index_html(summary)
    raw_payload = chart_payload(dashboard_html, "Relative humidity")

    assert raw_payload["bands"]


def test_line_chart_runtime_spans_mixed_cadence_alignment_gaps() -> None:
    summary = build_site_analysis_summary(
        sensor_readings=[
            sensor_reading("2026-07-02T22:03:00", "Basement", 19.0, 70.0),
            sensor_reading("2026-07-02T22:13:00", "Basement", 19.0, 76.0),
            sensor_reading("2026-07-02T22:03:00", "Bedroom", 20.0, 60.0),
            sensor_reading("2026-07-02T22:03:00", "Living room", 21.0, 58.0),
        ],
        events=[],
        weather_hours=[
            weather_hour("2026-07-02T22:00:00", 17.0, 68.0),
            weather_hour("2026-07-02T23:00:00", 17.5, 69.0),
        ],
        rain_readings=[],
        generated_at=datetime.fromisoformat("2026-07-05T12:00:00"),
    )

    dashboard_html = render_index_html(summary)
    moisture_payload = chart_payload(dashboard_html, "Absolute humidity")
    moisture_data = cast(list[list[float | None]], moisture_payload["data"])
    outdoor_values = moisture_data[4]
    first_weather_value = weather_hour(
        "2026-07-02T22:00:00",
        17.0,
        68.0,
    ).absolute_humidity_g_m3
    second_weather_value = weather_hour(
        "2026-07-02T23:00:00",
        17.5,
        69.0,
    ).absolute_humidity_g_m3

    assert first_weather_value is not None
    assert second_weather_value is not None
    assert outdoor_values == [
        round(first_weather_value, 3),
        None,
        round(second_weather_value, 3),
    ]
    assert "normalizeLineGaps(payload);" in dashboard_html


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
    rendered_html = f"{dashboard_html}\n{report_html}"

    assert 'href="physics-report.html"' not in dashboard_html
    assert "<title>Watch a basement dry</title>" in dashboard_html
    assert "<h1>Watch a basement dry</h1>" in dashboard_html
    assert '<body class="theme-aero">' in dashboard_html
    assert "position: relative;" in dashboard_html
    assert ".aero-deep {" in dashboard_html
    assert "overflow: hidden;" in dashboard_html
    assert "aero-aurora" in dashboard_html
    assert "aero-bokeh" in dashboard_html
    assert "Basement relative humidity" in dashboard_html
    assert "Basement temperature" in dashboard_html
    for chart_title in (
        "Basement conditions",
        "Absolute humidity",
        "Temperature",
        "Relative humidity",
    ):
        assert chart_title in dashboard_html
    for old_chart_title in (
        "Daily Basement Trends",
        "Basement Versus Outdoor Moisture",
        "Raw Sensor Context",
    ):
        assert old_chart_title not in dashboard_html
    for removed_dashboard_section in (
        "Latest basement sample",
        "Hypothesis Evidence",
        "Event-Bounded Period Metrics",
        "Compatible with active basement drying",
    ):
        assert removed_dashboard_section not in dashboard_html
    for asset_path in (
        "assets/frutiger-aero/tall-scene-960.webp",
        "assets/frutiger-aero/tall-scene-1440.webp",
        "assets/frutiger-aero/tall-scene-2048.webp",
        "assets/frutiger-aero/floor-strip.webp",
        "assets/frutiger-aero/dehumidifier.webp",
        "assets/frutiger-aero/goldfish.webp",
        "assets/frutiger-aero/dragonfly.webp",
    ):
        assert asset_path in dashboard_html
    for chart_hook in (
        "drawEventBubbles(plot",
        "rainBarPlugin(payload)",
        "waterFill(themedSeriesColor(series))",
        'body.classList.contains("theme-aero")',
    ):
        assert chart_hook in dashboard_html
    assert "Data to 02 Jul 2026, 23:00" in dashboard_html
    assert "Prototype scope" not in dashboard_html
    assert 'href="index.html"' in report_html
    assert "Uncertainty Budget" in report_html
    assert "Comparability flags" in report_html
    assert "Compatible with active basement drying" in report_html
    visible_html = visible_markup(rendered_html).lower()
    for removed_wording in ("local", "prototype", "provisional", "work-in-progress"):
        assert removed_wording not in visible_html


def test_dashboard_renders_self_contained_uplot_charts() -> None:
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

    dashboard_html = render_index_html(summary)

    assert "new uPlot(" in dashboard_html
    assert "uPlot.paths.bars" in dashboard_html
    assert 'type="application/json"' in dashboard_html
    assert '"initialWindowSeconds":604800' in dashboard_html
    assert "<noscript>" in dashboard_html
    assert "Enable JavaScript to view the interactive chart." in dashboard_html
    assert '"bands":[' in dashboard_html
    assert "<svg" not in dashboard_html
    assert not re.search(r"""<(script|link|img)\b[^>]+(?:src|href)=["']https?://""", dashboard_html)


def test_charts_include_touch_interactions_without_trapping_page_scroll() -> None:
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

    for rendered_html in (render_index_html(summary), render_physics_report_html(summary)):
        assert "addTouchNavigation(frame, plot, bounds);" in rendered_html
        assert 'addEventListener("touchstart"' in rendered_html
        assert 'addEventListener("touchmove"' in rendered_html
        assert 'addEventListener("touchend"' in rendered_html
        assert "touch-action: pan-y;" in rendered_html
        # One-finger vertical movement stays with the browser so the page can scroll.
        assert 'gesture = deltaX > deltaY ? "scrub" : "scroll";' in rendered_html
        assert "addWheelNavigation(frame, plot, bounds);" in rendered_html
        assert "drag: { x: true, y: false, setScale: true }" in rendered_html


def test_render_site_pages_returns_public_relative_path_to_html_mapping() -> None:
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

    assert set(pages) == {"index.html"}
    assert pages["index.html"] == render_index_html(summary)


def test_render_private_report_pages_keeps_local_report_available() -> None:
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

    pages = render_private_report_pages(summary)

    assert set(pages) == {"physics-report.html"}
    assert pages["physics-report.html"] == render_physics_report_html(summary)


def test_write_site_pages_persists_mapping_under_output_dir(tmp_path: Path) -> None:
    pages = {"index.html": "<p>dashboard</p>", "nested/report.html": "<p>report</p>"}

    written_paths = write_site_pages(pages, tmp_path / "site")

    assert written_paths["index.html"] == tmp_path / "site" / "index.html"
    assert written_paths["nested/report.html"] == tmp_path / "site" / "nested" / "report.html"
    for relative_path, content in pages.items():
        assert written_paths[relative_path].read_text(encoding="utf-8") == content


def summary_from_tank_series(
    segments: list[tuple[str, int]], tank_full_minutes: tuple[int, ...] = ()
) -> SiteAnalysisSummary:
    tank_full_events = [
        Event(timestamp=minutes_after_install(minute), description="dehumidifer tank full")
        for minute in tank_full_minutes
    ]
    return build_site_analysis_summary(
        sensor_readings=synthetic_series(segments),
        events=tank_full_events,
        weather_hours=[weather_hour("2026-07-02T22:00:00", 17.0, 68.0)],
        rain_readings=[],
        generated_at=datetime.fromisoformat("2026-07-10T12:00:00"),
    )


def assert_footer_paragraph_after_sources(dashboard_html: str, paragraph: str) -> None:
    assert re.search(
        r'class="sources">.*?</p>\s*<p>' + re.escape(paragraph) + r"</p>",
        dashboard_html,
        re.DOTALL,
    ), f"footer paragraph not found immediately after the sources paragraph: {paragraph!r}"


def test_footer_renders_filling_paragraph_after_sources_paragraph() -> None:
    summary = summary_from_tank_series([("cycling", 190)], tank_full_minutes=(2880, 5760))

    dashboard_html = render_index_html(summary)

    assert_footer_paragraph_after_sources(
        dashboard_html,
        "The dehumidifier has filled 2 times so far, removing 50 litres of water. "
        "The current tank is about 62% full (~16 of 25 litres) — roughly 27 cycles left, "
        "likely full Tue 7 Jul 21:39 ± half a day.",
    )


def test_footer_renders_not_running_paragraph_when_no_recent_cycles() -> None:
    summary = summary_from_tank_series(
        [("cycling", 144), ("open_episode", 6000)], tank_full_minutes=(2880,)
    )

    dashboard_html = render_index_html(summary)

    assert_footer_paragraph_after_sources(
        dashboard_html,
        "The dehumidifier has filled 1 times so far, removing 25 litres of water. "
        "The dehumidifier is not running as of the latest data.",
    )


def test_footer_renders_full_or_overdue_paragraph_with_the_calibration_window() -> None:
    # Uneven fill intervals give a non-zero calibration spread, so the "may be full"
    # window has distinct endpoints; the open tank runs well past one tank's worth.
    summary = summary_from_tank_series([("cycling", 300)], tank_full_minutes=(2000, 5760))

    dashboard_html = render_index_html(summary)

    assert_footer_paragraph_after_sources(
        dashboard_html,
        "The dehumidifier has filled 2 times so far, removing 50 litres of water. "
        "The current tank is estimated to be full — "
        "likely between Thu 9 Jul 14:19 and Fri 10 Jul 19:39.",
    )


def test_footer_paragraph_is_omitted_with_a_warning_without_logged_events(
    capsys: pytest.CaptureFixture[str],
) -> None:
    # Healthy cycling but no logged tank-full events: nothing to calibrate from.
    summary = summary_from_tank_series([("cycling", 190)])

    dashboard_html = render_index_html(summary)

    assert "The dehumidifier has filled" not in dashboard_html
    captured = capsys.readouterr()
    assert "warning" in captured.err.lower()
    assert "dehumidifier" in captured.err.lower()


def test_site_build_survives_an_estimator_exception_with_a_warning(
    capsys: pytest.CaptureFixture[str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import basement_analysis.summaries as summaries_module

    def raising_estimator(sensor_readings: object, tank_full_events: object) -> object:
        raise RuntimeError("synthetic estimator bug")

    monkeypatch.setattr(summaries_module, "estimate_tank_gauge", raising_estimator)
    summary = summary_from_tank_series([("cycling", 190)], tank_full_minutes=(2880, 5760))

    dashboard_html = render_index_html(summary)

    assert "The dehumidifier has filled" not in dashboard_html
    captured = capsys.readouterr()
    assert "warning" in captured.err.lower()
