from __future__ import annotations

import json
import re
from datetime import date, datetime
from pathlib import Path
from typing import cast

from basement_analysis.static_site import (
    fetch_open_meteo_weather,
    render_index_html,
    render_physics_report_html,
    render_private_report_pages,
    render_site_assets,
    render_site_pages,
    write_site_assets,
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
    assert summary.dashboard_charts[0].title == "Daily Basement Trends"
    assert "event timestamp uncertainty" in summary.period_summaries[-1].comparability_flags


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

    raw_sensor_chart = summary.dashboard_charts[2]
    basement_series = raw_sensor_chart.series[0]

    assert [timestamp for timestamp, _value in basement_series.points] == [
        datetime.fromisoformat("2026-05-01T05:00:00"),
        datetime.fromisoformat("2026-07-02T22:00:00"),
        datetime.fromisoformat("2026-07-02T22:10:00"),
    ]
    assert [value for _timestamp, value in basement_series.points] == [81.0, 72.0, 76.0]
    assert [value for _timestamp, value in basement_series.min_points] == [80.0, 70.0, 76.0]
    assert [value for _timestamp, value in basement_series.max_points] == [82.0, 74.0, 76.0]

    dashboard_html = render_index_html(summary)
    raw_payload = chart_payload(dashboard_html, "Raw Sensor Context")

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
    moisture_payload = chart_payload(dashboard_html, "Basement Versus Outdoor Moisture")
    moisture_data = cast(list[list[float | None]], moisture_payload["data"])
    outdoor_values = moisture_data[2]
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

    assert outdoor_values == [first_weather_value, None, second_weather_value]
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
    assert "<title>Basement Dampness</title>" in dashboard_html
    assert "<h1>Basement dampness</h1>" in dashboard_html
    assert "Latest basement sample" in dashboard_html
    assert dashboard_html.index("Latest basement sample") < dashboard_html.index(
        "Hypothesis Evidence"
    )
    assert "Basement Versus Outdoor Moisture" in dashboard_html
    assert "Compatible with active basement drying" in dashboard_html
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


def test_render_site_assets_derives_production_frutiger_aero_manifest() -> None:
    assets = render_site_assets()
    expected_paths = {
        "assets/frutiger-aero/dehumidifier.webp",
        "assets/frutiger-aero/dragonfly.webp",
        "assets/frutiger-aero/floor-strip.webp",
        "assets/frutiger-aero/goldfish.webp",
        "assets/frutiger-aero/manifest.json",
        "assets/frutiger-aero/tall-scene-960.webp",
        "assets/frutiger-aero/tall-scene-1440.webp",
        "assets/frutiger-aero/tall-scene-2048.webp",
    }

    assert set(assets) == expected_paths
    assert all(
        asset.cache_control == "public, max-age=600, no-transform" for asset in assets.values()
    )
    assert all(asset.content for asset in assets.values())

    manifest = cast(
        dict[str, object],
        json.loads(assets["assets/frutiger-aero/manifest.json"].content.decode("utf-8")),
    )
    entries = cast(list[dict[str, object]], manifest["assets"])
    entries_by_path = {str(entry["path"]): entry for entry in entries}

    assert set(entries_by_path) == expected_paths - {"assets/frutiger-aero/manifest.json"}
    assert entries_by_path["assets/frutiger-aero/tall-scene-2048.webp"]["source"] == (
        "tall-scene-source.webp"
    )
    assert entries_by_path["assets/frutiger-aero/tall-scene-2048.webp"]["width"] == 2048
    assert entries_by_path["assets/frutiger-aero/tall-scene-1440.webp"]["width"] == 1440
    assert entries_by_path["assets/frutiger-aero/tall-scene-960.webp"]["width"] == 960
    assert entries_by_path["assets/frutiger-aero/dehumidifier.webp"]["source"] == (
        "dehumidifier-no-shadow.png"
    )
    assert "tall-scene.png" not in json.dumps(manifest)
    assert "dehumidifier.png" not in json.dumps(manifest)
    assert "sky" not in json.dumps(manifest)
    assert "waterline" not in json.dumps(manifest)
    assert "grass" not in json.dumps(manifest)

    source_dir = Path("src/basement_analysis/site_assets/frutiger_aero/source")
    assert (source_dir / "tall-scene-source.webp").read_bytes() == Path(
        "prototypes/site-redesign-mockups/assets/upscalemedia-tall-scene.webp"
    ).read_bytes()
    assert (source_dir / "dehumidifier-no-shadow.png").exists()
    assert not (source_dir / "dehumidifier.png").exists()


def test_write_site_assets_persists_generated_binary_assets(tmp_path: Path) -> None:
    assets = render_site_assets()
    selected_paths = (
        "assets/frutiger-aero/goldfish.webp",
        "assets/frutiger-aero/manifest.json",
    )
    selected_assets = {relative_path: assets[relative_path] for relative_path in selected_paths}

    written_paths = write_site_assets(selected_assets, tmp_path / "site")

    for relative_path in selected_paths:
        assert written_paths[relative_path] == tmp_path / "site" / relative_path
        assert written_paths[relative_path].read_bytes() == assets[relative_path].content
