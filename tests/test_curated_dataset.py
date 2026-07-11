from __future__ import annotations

from datetime import date, datetime
from pathlib import Path

import pytest

from basement_analysis import static_site
from basement_analysis.curated_dataset import (
    join_curated_data_path,
    load_curated_dataset,
    parse_curated_data_location,
    write_curated_dataset,
)
from basement_analysis.summaries import (
    ENVIRONMENT_AGENCY_RAIN_STATION,
    Event,
    RainReading,
    SensorReading,
    WeatherHour,
    absolute_humidity_g_m3,
)


def sensor_reading(
    raw_timestamp: str,
    location: str,
    temperature_c: float,
    relative_humidity_pct: float,
) -> SensorReading:
    return SensorReading(
        timestamp=datetime.fromisoformat(raw_timestamp),
        location=location,
        temperature_c=temperature_c,
        relative_humidity_pct=relative_humidity_pct,
        absolute_humidity_g_m3=absolute_humidity_g_m3(temperature_c, relative_humidity_pct),
    )


def weather_hour(raw_timestamp: str) -> WeatherHour:
    temperature_c = 16.0
    relative_humidity_pct = 70.0
    return WeatherHour(
        timestamp=datetime.fromisoformat(raw_timestamp),
        temperature_c=temperature_c,
        relative_humidity_pct=relative_humidity_pct,
        dew_point_c=10.0,
        precipitation_mm=0.0,
        rain_mm=0.0,
        absolute_humidity_g_m3=absolute_humidity_g_m3(temperature_c, relative_humidity_pct),
    )


def test_curated_dataset_round_trips_through_partitioned_parquet_and_duckdb(
    tmp_path: Path,
) -> None:
    dataset_dir = tmp_path / "curated-data"

    parquet_files = write_curated_dataset(
        dataset_dir=dataset_dir,
        sensor_readings=[
            sensor_reading("2026-06-28T15:00:00", "Basement", 18.0, 88.0),
            sensor_reading("2026-07-02T22:00:00", "Living room", 21.0, 58.0),
        ],
        events=[Event(datetime.fromisoformat("2026-06-28T16:20:00"), "Bare floor exposed")],
        weather_hours=[weather_hour("2026-06-28T15:00:00")],
        rain_readings=[RainReading(datetime.fromisoformat("2026-06-28T15:15:00"), 0.2)],
    )

    relative_paths = {path.relative_to(dataset_dir).as_posix() for path in parquet_files}
    assert (
        "sensor_readings/source=x_sense/location_slug=basement/year=2026/month=06/"
        "part-00000.parquet"
    ) in relative_paths
    assert (
        f"rain_readings/source=environment_agency/station={ENVIRONMENT_AGENCY_RAIN_STATION}/"
        "year=2026/month=06/part-00000.parquet"
    ) in relative_paths

    curated_dataset = load_curated_dataset(dataset_dir)

    assert [reading.location for reading in curated_dataset.sensor_readings] == [
        "Basement",
        "Living room",
    ]
    assert curated_dataset.events[0].description == "Bare floor exposed"
    assert curated_dataset.weather_hours[0].absolute_humidity_g_m3 > 0
    assert curated_dataset.rain_readings[0].rainfall_mm == 0.2


def test_static_site_builds_from_curated_parquet_path(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    data_dir = tmp_path / "data"
    data_dir.mkdir()
    sensor_csv = data_dir / "Thermo-hygrometer_Export Data_202601031200_202607031200.csv"
    sensor_csv.write_text(
        "\n".join(
            [
                "Time,Temperature_Celsius,Relative Humidity_Percent",
                "2026/06/28 15:00,18.0,88.0",
                "2026/06/28 17:00,18.5,86.0",
                "2026/07/02 22:00,19.0,72.0",
                "2026/07/02 23:00,19.0,71.0",
            ]
        ),
        encoding="utf-8",
    )
    (data_dir / "basement_events.csv").write_text(
        "\n".join(
            [
                "Time,Event",
                "2026/06/28 16:20,Bare floor exposed",
                "2026/07/02 21:00,Fan orientation uncertain",
            ]
        ),
        encoding="utf-8",
    )

    def fake_open_meteo_weather(
        start_date: date,
        end_date: date,
        cache_dir: Path,
        refresh: bool,
    ) -> list[WeatherHour]:
        assert start_date == date(2026, 6, 28)
        assert end_date == date(2026, 7, 2)
        assert not refresh
        assert cache_dir.name == "cache"
        return [weather_hour("2026-06-28T15:00:00"), weather_hour("2026-07-02T22:00:00")]

    def fake_environment_agency_rainfall(
        start_date: date,
        end_date: date,
        cache_dir: Path,
        refresh: bool,
    ) -> list[RainReading]:
        assert start_date == date(2026, 6, 28)
        assert end_date == date(2026, 7, 2)
        assert not refresh
        assert cache_dir.name == "cache"
        return [RainReading(datetime.fromisoformat("2026-07-02T22:10:00"), 0.4)]

    monkeypatch.setattr(static_site, "fetch_open_meteo_weather", fake_open_meteo_weather)
    monkeypatch.setattr(
        static_site,
        "fetch_environment_agency_rainfall",
        fake_environment_agency_rainfall,
    )

    result = static_site.build_static_site(
        data_dir=data_dir,
        output_dir=tmp_path / "site",
        curated_dataset_dir=tmp_path / "curated-data",
    )

    assert result.index_path.exists()
    assert result.private_report_path is None
    assert not (tmp_path / "site" / "physics-report.html").exists()
    assert result.sensor_row_count == 4
    assert result.weather_hour_count == 2
    assert isinstance(result.curated_dataset_dir, Path)
    assert list(result.curated_dataset_dir.glob("**/*.parquet"))


def test_parse_curated_data_location_handles_local_and_s3() -> None:
    assert parse_curated_data_location("build/curated") == Path("build/curated")
    assert parse_curated_data_location("s3://bucket/parquet/") == "s3://bucket/parquet"
    with pytest.raises(ValueError, match="bucket"):
        parse_curated_data_location("s3://")


def test_join_curated_data_path_for_both_location_kinds() -> None:
    assert join_curated_data_path(Path("curated"), "events") == Path("curated") / "events"
    assert join_curated_data_path("s3://bucket/parquet", "events") == "s3://bucket/parquet/events"


def test_load_curated_dataset_from_s3_requires_r2_environment(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    for variable_name in ("R2_ENDPOINT_URL", "R2_ACCESS_KEY_ID", "R2_SECRET_ACCESS_KEY"):
        monkeypatch.delenv(variable_name, raising=False)

    with pytest.raises(ValueError, match="R2_ENDPOINT_URL"):
        load_curated_dataset("s3://bucket/parquet")


def test_build_static_site_rejects_rebuilding_into_s3_location(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="reuse-curated"):
        static_site.build_static_site(
            data_dir=tmp_path,
            output_dir=tmp_path / "site",
            curated_dataset_dir="s3://bucket/parquet",
        )


def test_build_static_site_can_write_private_report_for_local_analysis(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    data_dir = tmp_path / "data"
    data_dir.mkdir()
    (data_dir / "Thermo-hygrometer_Export Data_202601031200_202607031200.csv").write_text(
        "\n".join(
            [
                "Time,Temperature_Celsius,Relative Humidity_Percent",
                "2026/06/28 15:00,18.0,88.0",
                "2026/07/02 22:00,19.0,72.0",
            ]
        ),
        encoding="utf-8",
    )
    (data_dir / "basement_events.csv").write_text(
        "Time,Event\n2026/06/28 16:20,Bare floor exposed",
        encoding="utf-8",
    )

    def fake_open_meteo_weather(
        start_date: date,
        end_date: date,
        cache_dir: Path,
        refresh: bool,
    ) -> list[WeatherHour]:
        assert start_date == date(2026, 6, 28)
        assert end_date == date(2026, 7, 2)
        assert cache_dir.name == "cache"
        assert not refresh
        return [weather_hour("2026-07-02T22:00:00")]

    def fake_environment_agency_rainfall(
        start_date: date,
        end_date: date,
        cache_dir: Path,
        refresh: bool,
    ) -> list[RainReading]:
        assert start_date == date(2026, 6, 28)
        assert end_date == date(2026, 7, 2)
        assert cache_dir.name == "cache"
        assert not refresh
        return [RainReading(datetime.fromisoformat("2026-07-02T22:10:00"), 0.4)]

    monkeypatch.setattr(static_site, "fetch_open_meteo_weather", fake_open_meteo_weather)
    monkeypatch.setattr(
        static_site,
        "fetch_environment_agency_rainfall",
        fake_environment_agency_rainfall,
    )

    result = static_site.build_static_site(
        data_dir=data_dir,
        output_dir=tmp_path / "site",
        curated_dataset_dir=tmp_path / "curated-data",
        include_private_report=True,
    )

    assert result.index_path.exists()
    assert result.private_report_path == tmp_path / "site" / "physics-report.html"
    private_report_path = result.private_report_path
    assert private_report_path is not None
    assert private_report_path.exists()
