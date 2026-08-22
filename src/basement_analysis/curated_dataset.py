from __future__ import annotations

import os
import re
import shutil
from collections.abc import Sequence
from datetime import datetime
from pathlib import Path
from typing import cast

import duckdb
import polars as pl
from pydantic import BaseModel, ConfigDict

from basement_analysis.event_store import (
    EventRecord,
    EventType,
    connect_event_store,
    current_events,
    production_events_glob,
)
from basement_analysis.r2_access import configure_r2_access
from basement_analysis.summaries import (
    ENVIRONMENT_AGENCY_RAIN_STATION,
    Event,
    RainReading,
    SensorReading,
    WeatherHour,
)
from basement_analysis.timezones import UTC

# A curated dataset root is either a local directory or an `s3://bucket/prefix` URL that
# DuckDB reads directly (R2 via its S3-compatible endpoint).
CuratedDataRoot = Path | str


class CuratedDataset(BaseModel):
    model_config = ConfigDict(frozen=True)

    sensor_readings: tuple[SensorReading, ...]
    events: tuple[Event, ...]
    weather_hours: tuple[WeatherHour, ...]
    rain_readings: tuple[RainReading, ...]
    parquet_files: tuple[Path | str, ...]


def parse_curated_data_location(value: str) -> CuratedDataRoot:
    """Interpret a CLI location as an s3:// URL or a local directory path."""
    if value.startswith("s3://"):
        if not value.removeprefix("s3://").strip("/"):
            raise ValueError(f"s3:// curated data location needs a bucket: {value!r}")
        return value.rstrip("/")
    return Path(value)


def join_curated_data_path(dataset_root: CuratedDataRoot, part: str) -> Path | str:
    if isinstance(dataset_root, str):
        return f"{dataset_root.rstrip('/')}/{part}"
    return dataset_root / part


def write_curated_dataset(
    dataset_dir: Path,
    sensor_readings: Sequence[SensorReading],
    events: Sequence[Event],
    weather_hours: Sequence[WeatherHour],
    rain_readings: Sequence[RainReading],
) -> tuple[Path, ...]:
    """Write local analytical inputs as deterministic object-style Parquet files."""
    if dataset_dir.exists():
        shutil.rmtree(dataset_dir)
    dataset_dir.mkdir(parents=True, exist_ok=True)

    write_partitioned_parquet(
        frame=sensor_frame(sensor_readings),
        base_path=dataset_dir / "sensor_readings" / "source=x_sense",
        partition_columns=("location_slug", "year", "month"),
    )
    write_partitioned_parquet(
        frame=event_frame(events),
        base_path=dataset_dir / "events",
        partition_columns=("year",),
    )
    write_partitioned_parquet(
        frame=weather_frame(weather_hours),
        base_path=dataset_dir / "weather_hours" / "source=open_meteo",
        partition_columns=("year", "month"),
    )
    write_partitioned_parquet(
        frame=rain_frame(rain_readings),
        base_path=(
            dataset_dir
            / "rain_readings"
            / "source=environment_agency"
            / f"station={ENVIRONMENT_AGENCY_RAIN_STATION}"
        ),
        partition_columns=("year", "month"),
    )
    return tuple(sorted(dataset_dir.glob("**/*.parquet")))


def load_curated_dataset(
    dataset_root: CuratedDataRoot, *, include_events: bool = True
) -> CuratedDataset:
    connection = duckdb.connect(database=":memory:")
    try:
        if isinstance(dataset_root, str):
            configure_r2_access(connection)
        return CuratedDataset(
            sensor_readings=tuple(load_sensor_readings_from_parquet(connection, dataset_root)),
            events=(
                tuple(load_events_from_parquet(connection, dataset_root)) if include_events else ()
            ),
            weather_hours=tuple(load_weather_hours_from_parquet(connection, dataset_root)),
            rain_readings=tuple(load_rain_readings_from_parquet(connection, dataset_root)),
            parquet_files=list_parquet_files(connection, dataset_root),
        )
    finally:
        connection.close()


def list_parquet_files(
    connection: duckdb.DuckDBPyConnection, dataset_root: CuratedDataRoot
) -> tuple[Path | str, ...]:
    if isinstance(dataset_root, str):
        rows = connection.execute(
            "select file from glob($1) order by file",
            [parquet_glob_pattern(dataset_root)],
        ).fetchall()
        return tuple(cast(str, row[0]) for row in rows)
    return tuple(sorted(dataset_root.glob("**/*.parquet")))


def sensor_frame(sensor_readings: Sequence[SensorReading]) -> pl.DataFrame:
    return pl.DataFrame(
        {
            "timestamp": [reading.timestamp for reading in sensor_readings],
            "location": [reading.location for reading in sensor_readings],
            "location_slug": [
                slugify_partition_value(reading.location) for reading in sensor_readings
            ],
            "temperature_c": [reading.temperature_c for reading in sensor_readings],
            "relative_humidity_pct": [reading.relative_humidity_pct for reading in sensor_readings],
            "absolute_humidity_g_m3": [
                reading.absolute_humidity_g_m3 for reading in sensor_readings
            ],
        },
        schema={
            "timestamp": pl.Datetime(time_zone="UTC"),
            "location": pl.String,
            "location_slug": pl.String,
            "temperature_c": pl.Float64,
            "relative_humidity_pct": pl.Float64,
            "absolute_humidity_g_m3": pl.Float64,
        },
        strict=True,
    ).with_columns(partition_columns())


def event_frame(events: Sequence[Event]) -> pl.DataFrame:
    return pl.DataFrame(
        {
            "timestamp": [event.timestamp for event in events],
            "event_type": [event.event_type.value for event in events],
            "notes": [event.notes for event in events],
        },
        schema={
            "timestamp": pl.Datetime(time_zone="UTC"),
            "event_type": pl.String,
            "notes": pl.String,
        },
        strict=True,
    ).with_columns(year_partition_column())


def weather_frame(weather_hours: Sequence[WeatherHour]) -> pl.DataFrame:
    return pl.DataFrame(
        {
            "timestamp": [weather_hour.timestamp for weather_hour in weather_hours],
            "temperature_c": [weather_hour.temperature_c for weather_hour in weather_hours],
            "relative_humidity_pct": [
                weather_hour.relative_humidity_pct for weather_hour in weather_hours
            ],
            "dew_point_c": [weather_hour.dew_point_c for weather_hour in weather_hours],
            "precipitation_mm": [weather_hour.precipitation_mm for weather_hour in weather_hours],
            "rain_mm": [weather_hour.rain_mm for weather_hour in weather_hours],
            "absolute_humidity_g_m3": [
                weather_hour.absolute_humidity_g_m3 for weather_hour in weather_hours
            ],
        },
        schema={
            "timestamp": pl.Datetime(time_zone="UTC"),
            "temperature_c": pl.Float64,
            "relative_humidity_pct": pl.Float64,
            "dew_point_c": pl.Float64,
            "precipitation_mm": pl.Float64,
            "rain_mm": pl.Float64,
            "absolute_humidity_g_m3": pl.Float64,
        },
        strict=True,
    ).with_columns(partition_columns())


def rain_frame(rain_readings: Sequence[RainReading]) -> pl.DataFrame:
    return pl.DataFrame(
        {
            "timestamp": [reading.timestamp for reading in rain_readings],
            "rainfall_mm": [reading.rainfall_mm for reading in rain_readings],
        },
        schema={
            "timestamp": pl.Datetime(time_zone="UTC"),
            "rainfall_mm": pl.Float64,
        },
        strict=True,
    ).with_columns(partition_columns())


def partition_columns() -> tuple[pl.Expr, pl.Expr]:
    return pl.col("timestamp").dt.year().alias("year"), pl.col("timestamp").dt.strftime("%m").alias(
        "month"
    )


def year_partition_column() -> pl.Expr:
    return pl.col("timestamp").dt.year().alias("year")


def write_partitioned_parquet(
    frame: pl.DataFrame,
    base_path: Path,
    partition_columns: Sequence[str],
) -> None:
    if frame.is_empty():
        return

    for partition_values in partition_value_rows(frame, partition_columns):
        partition_path = base_path
        predicates: list[pl.Expr] = []
        for column_name in partition_columns:
            value = partition_values[column_name]
            partition_path = partition_path / f"{column_name}={value}"
            predicates.append(pl.col(column_name).eq(value))

        partition_path.mkdir(parents=True, exist_ok=True)
        partition_frame = frame.filter(*predicates).drop(partition_columns)
        partition_frame.write_parquet(partition_path / "part-00000.parquet")


def partition_value_rows(
    frame: pl.DataFrame, partition_columns: Sequence[str]
) -> list[dict[str, object]]:
    rows = frame.select(partition_columns).unique().sort(partition_columns).iter_rows(named=True)
    return [cast(dict[str, object], row) for row in rows]


def load_sensor_readings_from_parquet(
    connection: duckdb.DuckDBPyConnection, dataset_root: CuratedDataRoot
) -> list[SensorReading]:
    rows = cast(
        list[tuple[datetime, str, float, float, float]],
        fetch_parquet_rows(
            connection,
            join_curated_data_path(dataset_root, "sensor_readings"),
            """
            select timestamp at time zone 'UTC' as timestamp, location, temperature_c,
                   relative_humidity_pct, absolute_humidity_g_m3
            from read_parquet($1, hive_partitioning = true)
            order by location, timestamp
            """,
        ),
    )
    return [
        SensorReading(
            timestamp=timestamp.replace(tzinfo=UTC),
            location=location,
            temperature_c=temperature_c,
            relative_humidity_pct=relative_humidity_pct,
            absolute_humidity_g_m3=absolute_humidity_g_m3,
        )
        for (
            timestamp,
            location,
            temperature_c,
            relative_humidity_pct,
            absolute_humidity_g_m3,
        ) in rows
    ]


def load_events_from_parquet(
    connection: duckdb.DuckDBPyConnection, dataset_root: CuratedDataRoot
) -> list[Event]:
    rows = cast(
        list[tuple[datetime, str, str | None]],
        fetch_parquet_rows(
            connection,
            join_curated_data_path(dataset_root, "events"),
            """
            select timestamp at time zone 'UTC' as timestamp, event_type, notes
            from read_parquet($1, hive_partitioning = true)
            order by timestamp
            """,
        ),
    )
    return [
        Event(
            timestamp=timestamp.replace(tzinfo=UTC),
            event_type=EventType(event_type),
            notes=notes,
        )
        for timestamp, event_type, notes in rows
    ]


def event_from_record(record: EventRecord) -> Event:
    """Map a current event-store :class:`EventRecord` to the presentation-layer :class:`Event`.

    ``effective_at`` is the canonical UTC instant the event occurred; ``current_events`` only
    returns create/update records, which always carry it (delete tombstones are excluded).
    """
    if record.effective_at is None:  # pragma: no cover - current_events excludes tombstones
        raise ValueError(f"current event {record.event_id} has no effective_at")
    return Event(
        timestamp=record.effective_at,
        event_type=record.event_type,
        notes=record.data.notes,
    )


def load_events_from_event_store(events_glob: str) -> list[Event]:
    """Derive the current events from the R2 (or local) JSON event store via DuckDB.

    ``events_glob`` is an ``s3://$R2_BUCKET/events/year=*/*.json`` production glob (see
    :func:`r2_events_glob`) or a local ``year=*/*.json`` corpus glob for tests. Events are ordered
    by their effective instant, matching the old CSV-sorted order.
    """
    connection = connect_event_store(events_glob)
    try:
        records = current_events(connection, events_glob)
    finally:
        connection.close()
    return sorted(
        (event_from_record(record) for record in records), key=lambda event: event.timestamp
    )


def r2_events_glob() -> str:
    """The production event-store glob ``s3://$R2_BUCKET/events/year=*/*.json``.

    ``R2_BUCKET`` is required (the local full build and the hosted build both read events from R2).
    """
    bucket_name = os.getenv("R2_BUCKET")
    if not bucket_name:
        raise ValueError("Reading events from the R2 event store requires R2_BUCKET.")
    return production_events_glob(bucket_name)


def load_weather_hours_from_parquet(
    connection: duckdb.DuckDBPyConnection, dataset_root: CuratedDataRoot
) -> list[WeatherHour]:
    rows = cast(
        list[tuple[datetime, float, float, float, float, float, float]],
        fetch_parquet_rows(
            connection,
            join_curated_data_path(dataset_root, "weather_hours"),
            """
            select timestamp at time zone 'UTC' as timestamp, temperature_c,
                   relative_humidity_pct, dew_point_c, precipitation_mm, rain_mm,
                   absolute_humidity_g_m3
            from read_parquet($1, hive_partitioning = true)
            order by timestamp
            """,
        ),
    )
    return [
        WeatherHour(
            timestamp=timestamp.replace(tzinfo=UTC),
            temperature_c=temperature_c,
            relative_humidity_pct=relative_humidity_pct,
            dew_point_c=dew_point_c,
            precipitation_mm=precipitation_mm,
            rain_mm=rain_mm,
            absolute_humidity_g_m3=absolute_humidity_g_m3,
        )
        for (
            timestamp,
            temperature_c,
            relative_humidity_pct,
            dew_point_c,
            precipitation_mm,
            rain_mm,
            absolute_humidity_g_m3,
        ) in rows
    ]


def load_rain_readings_from_parquet(
    connection: duckdb.DuckDBPyConnection, dataset_root: CuratedDataRoot
) -> list[RainReading]:
    rows = cast(
        list[tuple[datetime, float]],
        fetch_parquet_rows(
            connection,
            join_curated_data_path(dataset_root, "rain_readings"),
            """
            select timestamp at time zone 'UTC' as timestamp, rainfall_mm
            from read_parquet($1, hive_partitioning = true)
            order by timestamp
            """,
        ),
    )
    return [
        RainReading(timestamp=timestamp.replace(tzinfo=UTC), rainfall_mm=rainfall_mm)
        for timestamp, rainfall_mm in rows
    ]


def fetch_parquet_rows(
    connection: duckdb.DuckDBPyConnection, parquet_root: CuratedDataRoot, sql: str
) -> list[tuple[object, ...]]:
    glob_pattern = parquet_glob_pattern(parquet_root)
    if not parquet_root_has_files(connection, parquet_root):
        return []
    rows = connection.execute(sql, [glob_pattern]).fetchall()
    return cast(list[tuple[object, ...]], rows)


def parquet_glob_pattern(parquet_root: CuratedDataRoot) -> str:
    if isinstance(parquet_root, str):
        return f"{parquet_root.rstrip('/')}/**/*.parquet"
    return str(parquet_root / "**" / "*.parquet")


def parquet_root_has_files(
    connection: duckdb.DuckDBPyConnection, parquet_root: CuratedDataRoot
) -> bool:
    if isinstance(parquet_root, str):
        probe_rows = connection.execute(
            "select 1 from glob($1) limit 1", [parquet_glob_pattern(parquet_root)]
        ).fetchall()
        return bool(probe_rows)
    return any(parquet_root.glob("**/*.parquet"))


def slugify_partition_value(value: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")
    if not slug:
        raise ValueError(f"Cannot make a partition slug from {value!r}")
    return slug
