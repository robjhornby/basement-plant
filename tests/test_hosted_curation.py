from __future__ import annotations

import json
from datetime import date, datetime
from pathlib import Path

import pytest

from basement_analysis import hosted_curation
from basement_analysis.curated_dataset import load_curated_dataset, write_curated_dataset
from basement_analysis.hosted_curation import (
    accepted_csv_object_keys,
    curate_accepted_email_csvs,
)
from basement_analysis.summaries import (
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


def write_manifest(
    object_store_dir: Path,
    name: str,
    status: str,
    attachment_status: str,
    csv_object_key: str | None,
) -> None:
    manifest_path = object_store_dir / "manifests" / "ingest" / f"{name}.json"
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    manifest_path.write_text(
        json.dumps(
            {
                "status": status,
                "attachments": [
                    {
                        "status": attachment_status,
                        "csv_object_key": csv_object_key,
                    }
                ],
            }
        ),
        encoding="utf-8",
    )


def write_csv_object(object_store_dir: Path, object_key: str, rows: list[str]) -> None:
    csv_path = object_store_dir / object_key
    csv_path.parent.mkdir(parents=True, exist_ok=True)
    csv_path.write_text(
        "\n".join(["Time,Temperature_Celsius,Relative Humidity_Percent", *rows]),
        encoding="utf-8",
    )


def test_accepted_csv_object_keys_only_uses_extracted_accepted_attachments(
    tmp_path: Path,
) -> None:
    object_store_dir = tmp_path / "objects"
    write_manifest(object_store_dir, "accepted", "accepted", "extracted", "csv/source=x/a.csv")
    write_manifest(object_store_dir, "rejected", "rejected", "extracted", "csv/source=x/b.csv")
    write_manifest(object_store_dir, "invalid_attachment", "accepted", "invalid_csv", None)

    assert accepted_csv_object_keys(object_store_dir) == ("csv/source=x/a.csv",)


def test_curate_accepted_email_csvs_merges_existing_parquet_and_staged_csvs(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    existing_dataset_dir = tmp_path / "existing-parquet"
    write_curated_dataset(
        dataset_dir=existing_dataset_dir,
        sensor_readings=[
            sensor_reading("2026-07-03T00:00:00", "Basement", 18.5, 67.2),
            sensor_reading("2026-07-03T00:01:00", "Basement", 18.5, 67.1),
            sensor_reading("2026-07-04T00:00:00", "Thermo-hygrometer_3", 20.0, 58.0),
        ],
        events=[Event(datetime.fromisoformat("2026-07-02T21:00:00"), "Dehumidifier on")],
        weather_hours=[weather_hour("2026-07-03T00:00:00")],
        rain_readings=[RainReading(datetime.fromisoformat("2026-07-03T00:00:00"), 0.0)],
    )

    object_store_dir = tmp_path / "objects"
    bedroom_csv_key = (
        "csv/source=x-sense/export_date=2026-07-04/attachment_sha256=abc123/"
        "Thermo-hygrometer_2_Export_Data_20260704.csv"
    )
    write_csv_object(
        object_store_dir,
        bedroom_csv_key,
        [
            "2026/07/03 00:01,21.0,55.0",
            "2026/07/04 00:00,20.5,56.0",
        ],
    )
    write_manifest(object_store_dir, "accepted", "accepted", "extracted", bedroom_csv_key)

    def fake_open_meteo_weather(
        start_date: date,
        end_date: date,
        cache_dir: Path,
        refresh: bool,
    ) -> list[WeatherHour]:
        assert start_date == date(2026, 7, 3)
        assert end_date == date(2026, 7, 4)
        assert cache_dir == tmp_path / "work" / "cache"
        assert refresh
        return [weather_hour("2026-07-03T00:00:00"), weather_hour("2026-07-04T00:00:00")]

    def fake_environment_agency_rainfall(
        start_date: date,
        end_date: date,
        cache_dir: Path,
        refresh: bool,
    ) -> list[RainReading]:
        assert start_date == date(2026, 7, 3)
        assert end_date == date(2026, 7, 4)
        assert cache_dir == tmp_path / "work" / "cache"
        assert refresh
        return [RainReading(datetime.fromisoformat("2026-07-04T00:00:00"), 0.2)]

    monkeypatch.setattr(hosted_curation, "fetch_open_meteo_weather", fake_open_meteo_weather)
    monkeypatch.setattr(
        hosted_curation,
        "fetch_environment_agency_rainfall",
        fake_environment_agency_rainfall,
    )

    result = curate_accepted_email_csvs(
        object_store_dir=object_store_dir,
        curated_dataset_dir=tmp_path / "curated",
        work_dir=tmp_path / "work",
        existing_curated_dataset_root=existing_dataset_dir,
        refresh_weather=True,
    )

    curated_dataset = load_curated_dataset(tmp_path / "curated")
    assert result.accepted_csv_count == 1
    assert result.existing_sensor_row_count == 3
    assert result.staged_sensor_row_count == 2
    assert result.merged_sensor_row_count == 5
    assert [event.description for event in curated_dataset.events] == ["Dehumidifier on"]
    assert {reading.location for reading in curated_dataset.sensor_readings} == {
        "Basement",
        "Bedroom",
        "Living room",
    }
    assert curated_dataset.weather_hours[-1].timestamp == datetime.fromisoformat(
        "2026-07-04T00:00:00"
    )
