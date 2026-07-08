from __future__ import annotations

import os
import re
import shutil
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import cast

import duckdb
import polars as pl

from basement_analysis.summaries import (
    ENVIRONMENT_AGENCY_RAIN_STATION,
    Event,
    RainReading,
    SensorReading,
    WeatherHour,
)

# A curated dataset root is either a local directory or an `s3://bucket/prefix` URL that
# DuckDB reads directly (R2 via its S3-compatible endpoint).
CuratedDataRoot = Path | str

R2_CREDENTIAL_ENV_VARS = ("R2_ENDPOINT_URL", "R2_ACCESS_KEY_ID", "R2_SECRET_ACCESS_KEY")


@dataclass(frozen=True)
class CuratedDataset:
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
        base_path=dataset_dir / "events" / "source=local_manual",
        partition_columns=("year", "month"),
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


def load_curated_dataset(dataset_root: CuratedDataRoot) -> CuratedDataset:
    connection = duckdb.connect(database=":memory:")
    try:
        if isinstance(dataset_root, str):
            configure_r2_access(connection)
        return CuratedDataset(
            sensor_readings=tuple(load_sensor_readings_from_parquet(connection, dataset_root)),
            events=tuple(load_events_from_parquet(connection, dataset_root)),
            weather_hours=tuple(load_weather_hours_from_parquet(connection, dataset_root)),
            rain_readings=tuple(load_rain_readings_from_parquet(connection, dataset_root)),
            parquet_files=list_parquet_files(connection, dataset_root),
        )
    finally:
        connection.close()


def configure_r2_access(connection: duckdb.DuckDBPyConnection) -> None:
    """Point DuckDB's S3 support at R2 using credentials from the environment."""
    missing_names = [name for name in R2_CREDENTIAL_ENV_VARS if not os.getenv(name)]
    if missing_names:
        raise ValueError(
            "Reading curated Parquet from an s3:// location requires the "
            f"{', '.join(R2_CREDENTIAL_ENV_VARS)} environment variables; "
            f"missing: {', '.join(missing_names)}"
        )
    connection.execute("install httpfs")
    connection.execute("load httpfs")
    connection.execute("set s3_region = 'auto'")
    connection.execute("set s3_url_style = 'path'")
    connection.execute("set s3_endpoint = ?", [r2_endpoint_host(os.environ["R2_ENDPOINT_URL"])])
    connection.execute("set s3_access_key_id = ?", [os.environ["R2_ACCESS_KEY_ID"]])
    connection.execute("set s3_secret_access_key = ?", [os.environ["R2_SECRET_ACCESS_KEY"]])


def r2_endpoint_host(endpoint_url: str) -> str:
    return endpoint_url.removeprefix("https://").removeprefix("http://").rstrip("/")


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
            "timestamp": pl.Datetime,
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
            "description": [event.description for event in events],
        },
        schema={
            "timestamp": pl.Datetime,
            "description": pl.String,
        },
        strict=True,
    ).with_columns(partition_columns())


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
            "timestamp": pl.Datetime,
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
            "timestamp": pl.Datetime,
            "rainfall_mm": pl.Float64,
        },
        strict=True,
    ).with_columns(partition_columns())


def partition_columns() -> tuple[pl.Expr, pl.Expr]:
    return pl.col("timestamp").dt.year().alias("year"), pl.col("timestamp").dt.strftime("%m").alias(
        "month"
    )


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
            select timestamp, location, temperature_c, relative_humidity_pct,
                   absolute_humidity_g_m3
            from read_parquet($1, hive_partitioning = true)
            order by location, timestamp
            """,
        ),
    )
    return [
        SensorReading(
            timestamp=timestamp,
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
        list[tuple[datetime, str]],
        fetch_parquet_rows(
            connection,
            join_curated_data_path(dataset_root, "events"),
            """
            select timestamp, description
            from read_parquet($1, hive_partitioning = true)
            order by timestamp
            """,
        ),
    )
    return [Event(timestamp=timestamp, description=description) for timestamp, description in rows]


def load_weather_hours_from_parquet(
    connection: duckdb.DuckDBPyConnection, dataset_root: CuratedDataRoot
) -> list[WeatherHour]:
    rows = cast(
        list[tuple[datetime, float, float, float, float, float, float]],
        fetch_parquet_rows(
            connection,
            join_curated_data_path(dataset_root, "weather_hours"),
            """
            select timestamp, temperature_c, relative_humidity_pct, dew_point_c,
                   precipitation_mm, rain_mm, absolute_humidity_g_m3
            from read_parquet($1, hive_partitioning = true)
            order by timestamp
            """,
        ),
    )
    return [
        WeatherHour(
            timestamp=timestamp,
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
            select timestamp, rainfall_mm
            from read_parquet($1, hive_partitioning = true)
            order by timestamp
            """,
        ),
    )
    return [
        RainReading(timestamp=timestamp, rainfall_mm=rainfall_mm) for timestamp, rainfall_mm in rows
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
