from __future__ import annotations

import json
import os
import re
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import cast

import duckdb
from pydantic import BaseModel, ConfigDict

from basement_analysis.curated_dataset import (
    CuratedDataRoot,
    join_curated_data_path,
    load_curated_dataset,
    load_events_from_event_store,
    r2_events_glob,
    write_curated_dataset,
)
from basement_analysis.object_layout import DATASETS_PREFIX, INGEST_OUTCOME_GLOB
from basement_analysis.observability import PhaseRecorder
from basement_analysis.r2_access import configure_r2_access
from basement_analysis.static_site import (
    fetch_environment_agency_rainfall,
    fetch_open_meteo_weather,
    sensor_location_for_filename,
    sensor_readings_from_csv_text,
)
from basement_analysis.summaries import RainReading, SensorReading, WeatherHour

# Re-ingest accepted CSVs whose export_date is within this many days *before* the curated
# watermark. The overlap plus the (location, timestamp) dedup make re-reading the last couple
# of days idempotent, so a CSV that straddles the boundary or lands a little late is never
# dropped. This is the one tunable.
OVERLAP_DAYS = 2


class HostedCurationResult(BaseModel):
    model_config = ConfigDict(frozen=True)

    curated_dataset_dir: Path
    accepted_csv_count: int
    selected_csv_count: int
    watermark: datetime | None
    existing_sensor_row_count: int
    staged_sensor_row_count: int
    merged_sensor_row_count: int
    event_count: int
    weather_hour_count: int
    rain_reading_count: int


def default_existing_curated_dataset_root() -> str:
    bucket_name = os.getenv("R2_BUCKET")
    if not bucket_name:
        raise ValueError(
            "Default hosted curation needs R2_BUCKET, or pass --existing-curated-data-dir."
        )
    return f"s3://{bucket_name}/{DATASETS_PREFIX}"


def sensor_reading_watermark(
    sensor_readings: tuple[SensorReading, ...],
) -> datetime | None:
    """The newest reading already in the curated parquet, or None if it is empty (cold start)."""
    if not sensor_readings:
        return None
    return max(reading.timestamp for reading in sensor_readings)


def incremental_weather_fetch_start(
    watermark: datetime | None,
    dataset_start: date,
    rebuild_all: bool,
) -> date:
    """First date to re-fetch from an upstream weather/rainfall API.

    Mirrors the sensor-reading cutoff: begin OVERLAP_DAYS before the newest hour/reading already
    curated so late-arriving or revised data is refreshed, but never before the sensor history
    starts. A cold start (no existing weather/rain) or --rebuild-all re-fetches from the dataset
    start instead.
    """
    if rebuild_all or watermark is None:
        return dataset_start
    return max(dataset_start, watermark.date() - timedelta(days=OVERLAP_DAYS))


def object_store_connection(object_store_root: CuratedDataRoot) -> duckdb.DuckDBPyConnection:
    """A DuckDB connection that reads the object store — R2 (s3://) or a local dir — directly."""
    connection = duckdb.connect(database=":memory:")
    if isinstance(object_store_root, str):
        configure_r2_access(connection)
    return connection


def list_object_paths(
    connection: duckdb.DuckDBPyConnection, object_store_root: CuratedDataRoot, pattern: str
) -> list[str]:
    glob_pattern = str(join_curated_data_path(object_store_root, pattern))
    rows = connection.execute("select file from glob($1) order by file", [glob_pattern]).fetchall()
    return [cast(str, row[0]) for row in rows]


def read_object_texts(
    connection: duckdb.DuckDBPyConnection, object_paths: list[str]
) -> list[tuple[str, str]]:
    """Return (path, text) for each object, read directly from the store (no local mirror)."""
    if not object_paths:
        return []
    rows = connection.execute(
        "select filename, content from read_text($1) order by filename", [object_paths]
    ).fetchall()
    return [(cast(str, filename), cast(str, content)) for filename, content in rows]


def partition_date_from_key(object_key: str, field: str) -> date | None:
    match = re.search(rf"{field}=(\d{{4}}-\d{{2}}-\d{{2}})", object_key)
    if match is None:
        return None
    try:
        return date.fromisoformat(match.group(1))
    except ValueError:
        return None


def accepted_csv_keys_from_manifest(manifest: dict[str, object]) -> list[str]:
    if manifest.get("status") != "accepted":
        return []
    attachments = manifest.get("attachments")
    if not isinstance(attachments, list):
        return []
    keys: list[str] = []
    for attachment in cast(list[object], attachments):
        if not isinstance(attachment, dict):
            continue
        attachment_values = cast(dict[object, object], attachment)
        if attachment_values.get("status") != "extracted":
            continue
        attachment_object_key = attachment_values.get("attachment_object_key")
        if isinstance(attachment_object_key, str) and attachment_object_key:
            keys.append(attachment_object_key)
    return keys


def accepted_csv_keys_from_manifest_texts(manifest_texts: list[str]) -> tuple[str, ...]:
    object_keys: set[str] = set()
    for text in manifest_texts:
        manifest = cast(dict[str, object], json.loads(text))
        object_keys.update(accepted_csv_keys_from_manifest(manifest))
    return tuple(sorted(object_keys))


def accepted_csv_object_keys(
    connection: duckdb.DuckDBPyConnection,
    object_store_root: CuratedDataRoot,
    cutoff_date: date | None,
) -> tuple[str, ...]:
    """Accepted CSV object keys per the ingest manifests, reading only the recent manifests.

    For an incremental run (`cutoff_date` set) only manifests whose `received_date` partition is
    at or after the cutoff need reading — received_date tracks export_date within a day, so no
    manifest referencing an in-window CSV is skipped. A `None` cutoff reads every manifest.
    """
    manifest_paths = list_object_paths(connection, object_store_root, INGEST_OUTCOME_GLOB)
    selected_manifest_paths = [
        path
        for path in manifest_paths
        if cutoff_date is None or _received_within_cutoff(path, cutoff_date)
    ]
    manifest_texts = [text for _, text in read_object_texts(connection, selected_manifest_paths)]
    return accepted_csv_keys_from_manifest_texts(manifest_texts)


def _received_within_cutoff(manifest_path: str, cutoff_date: date) -> bool:
    received_date = partition_date_from_key(manifest_path, "received_date")
    return received_date is None or received_date >= cutoff_date


def select_csv_keys_by_export_date(
    accepted_csv_keys: tuple[str, ...], cutoff_date: date | None
) -> tuple[str, ...]:
    """Keep only CSVs whose export_date is at or after the cutoff; older ones are already curated.

    A key whose export_date cannot be parsed is kept (never silently dropped). `None` keeps all.
    """
    if cutoff_date is None:
        return accepted_csv_keys
    selected: list[str] = []
    for object_key in accepted_csv_keys:
        export_date = partition_date_from_key(object_key, "export_date")
        if export_date is None or export_date >= cutoff_date:
            selected.append(object_key)
    return tuple(selected)


def parse_selected_csv_objects(
    connection: duckdb.DuckDBPyConnection,
    object_store_root: CuratedDataRoot,
    selected_csv_keys: tuple[str, ...],
) -> list[SensorReading]:
    csv_paths = [str(join_curated_data_path(object_store_root, key)) for key in selected_csv_keys]
    readings: list[SensorReading] = []
    for filename, content in read_object_texts(connection, csv_paths):
        location = sensor_location_for_filename(Path(filename).name)
        readings.extend(sensor_readings_from_csv_text(content, location))
    return readings


def curate_accepted_email_csvs(
    object_store_root: CuratedDataRoot,
    curated_dataset_dir: Path,
    work_dir: Path,
    events_glob: str | None = None,
    existing_curated_dataset_root: CuratedDataRoot | None = None,
    refresh_weather: bool = True,
    rebuild_all: bool = False,
    phase_recorder: PhaseRecorder | None = None,
) -> HostedCurationResult:
    recorder = phase_recorder if phase_recorder is not None else PhaseRecorder()
    existing_root = existing_curated_dataset_root or default_existing_curated_dataset_root()
    with recorder.phase("load-existing-curated-parquet"):
        # Existing event Parquet is never merged: the canonical JSON store rebuilds it below.
        # Skipping it also lets the first rollout replace the legacy description-only schema.
        existing_dataset = load_curated_dataset(existing_root, include_events=False)

    # The curated parquet is the full merged history; its newest reading is the watermark. Only
    # CSVs at or after `watermark - OVERLAP_DAYS` can carry anything not already curated, so those
    # are the only ones downloaded and parsed. `--rebuild-all` (or a cold-start empty parquet)
    # drops the cutoff and re-parses every accepted CSV.
    watermark = sensor_reading_watermark(existing_dataset.sensor_readings)
    cutoff_date = (
        None
        if (rebuild_all or watermark is None)
        else watermark.date() - timedelta(days=OVERLAP_DAYS)
    )

    # Rebuild the current event timeline from the canonical JSON event store on every run.
    # Tests inject a local corpus glob in place of R2.
    with recorder.phase("load-manual-events"):
        events = load_events_from_event_store(events_glob or r2_events_glob())

    with recorder.phase("select-and-parse-accepted-csvs"):
        connection = object_store_connection(object_store_root)
        try:
            accepted_csv_keys = accepted_csv_object_keys(connection, object_store_root, cutoff_date)
            selected_csv_keys = select_csv_keys_by_export_date(accepted_csv_keys, cutoff_date)
            new_sensor_readings = parse_selected_csv_objects(
                connection, object_store_root, selected_csv_keys
            )
        finally:
            connection.close()

    with recorder.phase("merge-sensor-readings"):
        merged_sensor_readings = merge_sensor_readings(
            [*existing_dataset.sensor_readings, *new_sensor_readings]
        )
    if not merged_sensor_readings:
        raise ValueError(
            f"No sensor readings found in existing dataset {existing_root!r} or accepted CSVs "
            f"under {object_store_root}"
        )

    dataset_start = min(reading.timestamp for reading in merged_sensor_readings).date()
    dataset_end = max(reading.timestamp for reading in merged_sensor_readings).date()

    # Fetch weather and rainfall incrementally, each from its own watermark: the Open-Meteo
    # archive lags the live sensor feed by a few days, so its newest curated hour trails the
    # sensor watermark. Bounding the request to the recent window (rather than the full history
    # from dataset_start) keeps it fast and stops the Environment Agency call — which only ever
    # returns the last ~4 weeks and slows down the wider the range — from creeping toward the
    # 30s timeout as the dataset grows.
    weather_watermark = max(
        (hour.timestamp for hour in existing_dataset.weather_hours), default=None
    )
    rain_watermark = max(
        (reading.timestamp for reading in existing_dataset.rain_readings), default=None
    )
    weather_start = incremental_weather_fetch_start(weather_watermark, dataset_start, rebuild_all)
    rain_start = incremental_weather_fetch_start(rain_watermark, dataset_start, rebuild_all)

    cache_dir = work_dir / "cache"
    with recorder.phase("fetch-open-meteo-weather"):
        fresh_weather_hours = fetch_open_meteo_weather(
            start_date=weather_start,
            end_date=dataset_end,
            cache_dir=cache_dir,
            refresh=refresh_weather,
        )
    with recorder.phase("fetch-environment-agency-rainfall"):
        fresh_rain_readings = fetch_environment_agency_rainfall(
            start_date=rain_start,
            end_date=dataset_end,
            cache_dir=cache_dir,
            refresh=refresh_weather,
        )
    # The upstream APIs serve a bounded window (the EA rainfall API keeps ~4 weeks), so
    # replacing these partitions would silently discard older history every night.
    weather_hours = merge_weather_hours([*existing_dataset.weather_hours, *fresh_weather_hours])
    rain_readings = merge_rain_readings([*existing_dataset.rain_readings, *fresh_rain_readings])
    with recorder.phase("write-curated-parquet"):
        write_curated_dataset(
            dataset_dir=curated_dataset_dir,
            sensor_readings=merged_sensor_readings,
            events=events,
            weather_hours=weather_hours,
            rain_readings=rain_readings,
        )
    return HostedCurationResult(
        curated_dataset_dir=curated_dataset_dir,
        accepted_csv_count=len(accepted_csv_keys),
        selected_csv_count=len(selected_csv_keys),
        watermark=watermark,
        existing_sensor_row_count=len(existing_dataset.sensor_readings),
        staged_sensor_row_count=len(new_sensor_readings),
        merged_sensor_row_count=len(merged_sensor_readings),
        event_count=len(events),
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
