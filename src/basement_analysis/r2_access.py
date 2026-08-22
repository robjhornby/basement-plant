"""Shared R2 (S3-compatible) access configuration for DuckDB.

Extracted from ``curated_dataset`` so both the curated-parquet reader and the event store can
configure httpfs without importing each other (the event store maps records into the ``Event``
model that lives alongside the curated reader, which would otherwise form an import cycle).
"""

from __future__ import annotations

import os

import duckdb

R2_CREDENTIAL_ENV_VARS = ("R2_ENDPOINT_URL", "R2_ACCESS_KEY_ID", "R2_SECRET_ACCESS_KEY")


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
