from __future__ import annotations

import json
import os
import shutil
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import cast

from basement_analysis.curated_dataset import (
    CuratedDataRoot,
    load_curated_dataset,
    write_curated_dataset,
)
from basement_analysis.static_site import (
    fetch_environment_agency_rainfall,
    fetch_open_meteo_weather,
    load_sensor_readings,
)
from basement_analysis.summaries import RainReading, SensorReading, WeatherHour


@dataclass(frozen=True)
class HostedCurationResult:
    curated_dataset_dir: Path
    accepted_csv_count: int
    existing_sensor_row_count: int
    staged_sensor_row_count: int
    merged_sensor_row_count: int
    weather_hour_count: int
    rain_reading_count: int


def default_existing_curated_dataset_root() -> str:
    bucket_name = os.getenv("R2_BUCKET")
    if not bucket_name:
        raise ValueError(
            "Default hosted curation needs R2_BUCKET, or pass --existing-curated-data-dir."
        )
    return f"s3://{bucket_name}/parquet"


def accepted_csv_object_keys(object_store_dir: Path) -> tuple[str, ...]:
    object_keys: set[str] = set()
    manifest_root = object_store_dir / "manifests" / "ingest"
    for manifest_path in sorted(manifest_root.glob("**/*.json")):
        manifest = cast(dict[str, object], json.loads(manifest_path.read_text(encoding="utf-8")))
        if manifest.get("status") != "accepted":
            continue
        attachments = manifest.get("attachments")
        if not isinstance(attachments, list):
            continue
        for attachment in cast(list[object], attachments):
            if not isinstance(attachment, dict):
                continue
            attachment_values = cast(dict[object, object], attachment)
            if attachment_values.get("status") != "extracted":
                continue
            csv_object_key = attachment_values.get("csv_object_key")
            if isinstance(csv_object_key, str) and csv_object_key:
                object_keys.add(csv_object_key)
    return tuple(sorted(object_keys))


def stage_accepted_csv_objects(
    object_store_dir: Path, staged_data_dir: Path, csv_object_keys: tuple[str, ...]
) -> tuple[Path, ...]:
    if staged_data_dir.exists():
        shutil.rmtree(staged_data_dir)
    staged_data_dir.mkdir(parents=True, exist_ok=True)

    staged_paths: list[Path] = []
    for object_key in csv_object_keys:
        source_path = object_store_dir / object_key
        if not source_path.exists():
            raise FileNotFoundError(
                f"Accepted ingest manifest references missing CSV object {object_key!r}"
            )
        destination_path = staged_data_dir / object_key
        destination_path.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source_path, destination_path)
        staged_paths.append(destination_path)
    return tuple(staged_paths)


def curate_accepted_email_csvs(
    object_store_dir: Path,
    curated_dataset_dir: Path,
    work_dir: Path,
    existing_curated_dataset_root: CuratedDataRoot | None = None,
    refresh_weather: bool = True,
) -> HostedCurationResult:
    existing_root = existing_curated_dataset_root or default_existing_curated_dataset_root()
    existing_dataset = load_curated_dataset(existing_root)

    csv_object_keys = accepted_csv_object_keys(object_store_dir)
    staged_data_dir = work_dir / "accepted-csvs"
    stage_accepted_csv_objects(object_store_dir, staged_data_dir, csv_object_keys)
    staged_sensor_readings = load_sensor_readings(staged_data_dir)

    merged_sensor_readings = merge_sensor_readings(
        [*existing_dataset.sensor_readings, *staged_sensor_readings]
    )
    if not merged_sensor_readings:
        raise ValueError(
            f"No sensor readings found in existing dataset {existing_root!r} or accepted CSVs "
            f"under {object_store_dir}"
        )

    dataset_start = min(reading.timestamp for reading in merged_sensor_readings)
    dataset_end = max(reading.timestamp for reading in merged_sensor_readings)
    cache_dir = work_dir / "cache"
    fresh_weather_hours = fetch_open_meteo_weather(
        start_date=dataset_start.date(),
        end_date=dataset_end.date(),
        cache_dir=cache_dir,
        refresh=refresh_weather,
    )
    fresh_rain_readings = fetch_environment_agency_rainfall(
        start_date=dataset_start.date(),
        end_date=dataset_end.date(),
        cache_dir=cache_dir,
        refresh=refresh_weather,
    )
    # The upstream APIs serve a bounded window (the EA rainfall API keeps ~4 weeks), so
    # replacing these partitions would silently discard older history every night.
    weather_hours = merge_weather_hours([*existing_dataset.weather_hours, *fresh_weather_hours])
    rain_readings = merge_rain_readings([*existing_dataset.rain_readings, *fresh_rain_readings])
    write_curated_dataset(
        dataset_dir=curated_dataset_dir,
        sensor_readings=merged_sensor_readings,
        events=existing_dataset.events,
        weather_hours=weather_hours,
        rain_readings=rain_readings,
    )
    return HostedCurationResult(
        curated_dataset_dir=curated_dataset_dir,
        accepted_csv_count=len(csv_object_keys),
        existing_sensor_row_count=len(existing_dataset.sensor_readings),
        staged_sensor_row_count=len(staged_sensor_readings),
        merged_sensor_row_count=len(merged_sensor_readings),
        weather_hour_count=len(weather_hours),
        rain_reading_count=len(rain_readings),
    )


def merge_weather_hours(weather_hours: list[WeatherHour]) -> list[WeatherHour]:
    hours_by_timestamp: dict[datetime, WeatherHour] = {
        weather_hour.timestamp: weather_hour for weather_hour in weather_hours
    }
    return sorted(hours_by_timestamp.values(), key=lambda weather_hour: weather_hour.timestamp)


def merge_rain_readings(readings: list[RainReading]) -> list[RainReading]:
    readings_by_timestamp: dict[datetime, RainReading] = {
        reading.timestamp: reading for reading in readings
    }
    return sorted(readings_by_timestamp.values(), key=lambda reading: reading.timestamp)


def merge_sensor_readings(readings: list[SensorReading]) -> list[SensorReading]:
    readings_by_identity: dict[tuple[str, datetime], SensorReading] = {}
    for reading in readings:
        normalized_reading = normalize_sensor_reading_location(reading)
        readings_by_identity[(normalized_reading.location, normalized_reading.timestamp)] = (
            normalized_reading
        )
    return sorted(
        readings_by_identity.values(),
        key=lambda reading: (reading.location, reading.timestamp),
    )


def normalize_sensor_reading_location(reading: SensorReading) -> SensorReading:
    canonical_location = canonical_sensor_location(reading.location)
    if canonical_location == reading.location:
        return reading
    return SensorReading(
        timestamp=reading.timestamp,
        location=canonical_location,
        temperature_c=reading.temperature_c,
        relative_humidity_pct=reading.relative_humidity_pct,
        absolute_humidity_g_m3=reading.absolute_humidity_g_m3,
    )


def canonical_sensor_location(location: str) -> str:
    normalized_location = " ".join(location.replace("_", " ").split())
    match normalized_location:
        case "Thermo-hygrometer":
            return "Basement"
        case "Thermo-hygrometer 2":
            return "Bedroom"
        case "Thermo-hygrometer 3":
            return "Living room"
        case _:
            return location
