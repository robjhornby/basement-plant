from __future__ import annotations

import argparse
import html
import json
import os
import platform
import shutil
import sys
import time
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any, cast

import duckdb


DEFAULT_PARQUET_ROOT = Path("../../build/basement-site/curated-data")
DEFAULT_OUTPUT_DIR = Path("build/site-output")
DEFAULT_SITE_PREFIX = "site/prototypes/container-analysis"


@dataclass(frozen=True)
class RuntimeSnapshot:
    python: str
    platform: str
    duckdb: str
    memory_limit: str | None
    cpu_limit: str | None
    tmp_disk_free_bytes: int


@dataclass(frozen=True)
class QuerySummary:
    sensor_rows: int
    event_rows: int
    weather_hour_rows: int
    rain_reading_rows: int
    first_sensor_timestamp: str
    last_sensor_timestamp: str
    latest_basement_absolute_humidity_g_m3: float | None
    mean_basement_absolute_humidity_g_m3: float | None


def main() -> None:
    parser = create_parser()
    args = parser.parse_args()
    if args.serve:
        serve(args)
        return

    manifest = run_job(args)
    print(json.dumps(manifest, indent=2, sort_keys=True))


def create_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Run a Cloudflare Container-shaped DuckDB analysis job against a partitioned "
            "Parquet dataset and publish representative static artifacts."
        )
    )
    parser.add_argument("--serve", action="store_true")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8080)
    parser.add_argument("--mode", choices=("local", "r2"), default=os.getenv("PROTOTYPE_MODE", "local"))
    parser.add_argument("--parquet-root", type=Path, default=DEFAULT_PARQUET_ROOT)
    parser.add_argument("--r2-bucket", default=os.getenv("R2_BUCKET"))
    parser.add_argument("--r2-parquet-prefix", default=os.getenv("R2_PARQUET_PREFIX", "parquet"))
    parser.add_argument("--r2-endpoint-url", default=os.getenv("R2_ENDPOINT_URL"))
    parser.add_argument("--r2-access-key-id", default=os.getenv("R2_ACCESS_KEY_ID"))
    parser.add_argument("--r2-secret-access-key", default=os.getenv("R2_SECRET_ACCESS_KEY"))
    parser.add_argument("--r2-use-ssl", action=argparse.BooleanOptionalAction, default=True)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("--site-prefix", default=DEFAULT_SITE_PREFIX)
    return parser


def run_job(args: argparse.Namespace) -> dict[str, Any]:
    started_at = time.perf_counter()
    connection = duckdb.connect(database=":memory:")
    try:
        base_path = configure_source(connection, args)
        summary = query_dataset(connection, base_path)
    finally:
        connection.close()

    runtime = runtime_snapshot()
    generated_at = datetime.now(UTC).replace(microsecond=0).isoformat()
    duration_seconds = round(time.perf_counter() - started_at, 3)
    manifest: dict[str, Any] = {
        "generated_at": generated_at,
        "duration_seconds": duration_seconds,
        "mode": args.mode,
        "parquet_base": base_path,
        "summary": asdict(summary),
        "runtime": asdict(runtime),
        "site_prefix": args.site_prefix,
    }
    artifacts = {
        "index.html": render_html(summary, runtime, generated_at, duration_seconds),
        "manifest.json": json.dumps(manifest, indent=2, sort_keys=True) + "\n",
    }

    if args.mode == "r2":
        publish_to_r2(args, artifacts)
    else:
        publish_to_local_dir(args.output_dir, args.site_prefix, artifacts)

    return manifest


def serve(args: argparse.Namespace) -> None:
    class Handler(BaseHTTPRequestHandler):
        def do_GET(self) -> None:
            if self.path == "/health":
                self.send_response(HTTPStatus.OK)
                self.end_headers()
                self.wfile.write(b"ok\n")
                return
            self.send_response(HTTPStatus.NOT_FOUND)
            self.end_headers()

        def do_POST(self) -> None:
            if self.path != "/run":
                self.send_response(HTTPStatus.NOT_FOUND)
                self.end_headers()
                return

            try:
                manifest = run_job(args)
            except Exception as exc:
                payload = json.dumps({"error": str(exc)}, indent=2).encode("utf-8")
                self.send_response(HTTPStatus.INTERNAL_SERVER_ERROR)
                self.send_header("content-type", "application/json; charset=utf-8")
                self.send_header("content-length", str(len(payload)))
                self.end_headers()
                self.wfile.write(payload)
                return

            payload = json.dumps(manifest, indent=2, sort_keys=True).encode("utf-8")
            self.send_response(HTTPStatus.OK)
            self.send_header("content-type", "application/json; charset=utf-8")
            self.send_header("content-length", str(len(payload)))
            self.end_headers()
            self.wfile.write(payload)

        def log_message(self, format: str, *args: object) -> None:
            sys.stderr.write(f"{self.address_string()} - {format % args}\n")

    server = ThreadingHTTPServer((args.host, args.port), Handler)
    print(f"Serving prototype runner on http://{args.host}:{args.port}", flush=True)
    server.serve_forever()


def configure_source(connection: duckdb.DuckDBPyConnection, args: argparse.Namespace) -> str:
    if args.mode == "local":
        parquet_root = args.parquet_root.resolve()
        if not parquet_root.exists():
            raise FileNotFoundError(
                f"Curated Parquet root does not exist: {parquet_root}. "
                "Run `uv run basement` from the repo root first."
            )
        return str(parquet_root)

    required = {
        "R2_BUCKET": args.r2_bucket,
        "R2_ENDPOINT_URL": args.r2_endpoint_url,
        "R2_ACCESS_KEY_ID": args.r2_access_key_id,
        "R2_SECRET_ACCESS_KEY": args.r2_secret_access_key,
    }
    missing = [name for name, value in required.items() if not value]
    if missing:
        raise ValueError(f"Missing required R2 settings for --mode r2: {', '.join(missing)}")

    endpoint = endpoint_without_scheme(cast(str, args.r2_endpoint_url))
    connection.execute("install httpfs")
    connection.execute("load httpfs")
    connection.execute("set s3_region = 'auto'")
    connection.execute("set s3_url_style = 'path'")
    connection.execute("set s3_use_ssl = ?", [args.r2_use_ssl])
    connection.execute("set s3_endpoint = ?", [endpoint])
    connection.execute("set s3_access_key_id = ?", [args.r2_access_key_id])
    connection.execute("set s3_secret_access_key = ?", [args.r2_secret_access_key])
    return f"s3://{args.r2_bucket}/{args.r2_parquet_prefix.strip('/')}"


def endpoint_without_scheme(endpoint_url: str) -> str:
    return endpoint_url.removeprefix("https://").removeprefix("http://").rstrip("/")


def query_dataset(connection: duckdb.DuckDBPyConnection, base_path: str) -> QuerySummary:
    sensor_glob = f"{base_path.rstrip('/')}/sensor_readings/**/*.parquet"
    event_glob = f"{base_path.rstrip('/')}/events/**/*.parquet"
    weather_glob = f"{base_path.rstrip('/')}/weather_hours/**/*.parquet"
    rain_glob = f"{base_path.rstrip('/')}/rain_readings/**/*.parquet"

    sensor_row = connection.execute(
        """
        select
            count(*)::integer as sensor_rows,
            min(timestamp)::varchar as first_sensor_timestamp,
            max(timestamp)::varchar as last_sensor_timestamp
        from read_parquet($1, hive_partitioning = true)
        """,
        [sensor_glob],
    ).fetchone()
    basement_row = connection.execute(
        """
        with basement as (
            select timestamp, absolute_humidity_g_m3
            from read_parquet($1, hive_partitioning = true)
            where location = 'Basement'
        )
        select
            avg(absolute_humidity_g_m3)::double as mean_absolute_humidity,
            (
                select absolute_humidity_g_m3::double
                from basement
                order by timestamp desc
                limit 1
            ) as latest_absolute_humidity
        from basement
        """,
        [sensor_glob],
    ).fetchone()
    event_rows = count_parquet_rows(connection, event_glob)
    weather_hour_rows = count_parquet_rows(connection, weather_glob)
    rain_reading_rows = count_parquet_rows(connection, rain_glob)

    if sensor_row is None or basement_row is None:
        raise ValueError("Expected curated sensor data, got no query result")

    return QuerySummary(
        sensor_rows=int(sensor_row[0]),
        event_rows=event_rows,
        weather_hour_rows=weather_hour_rows,
        rain_reading_rows=rain_reading_rows,
        first_sensor_timestamp=str(sensor_row[1]),
        last_sensor_timestamp=str(sensor_row[2]),
        mean_basement_absolute_humidity_g_m3=optional_float(basement_row[0]),
        latest_basement_absolute_humidity_g_m3=optional_float(basement_row[1]),
    )


def count_parquet_rows(connection: duckdb.DuckDBPyConnection, parquet_glob: str) -> int:
    row = connection.execute(
        "select count(*)::integer from read_parquet($1, hive_partitioning = true)",
        [parquet_glob],
    ).fetchone()
    if row is None:
        return 0
    return int(row[0])


def optional_float(value: object) -> float | None:
    if value is None:
        return None
    return float(value)


def runtime_snapshot() -> RuntimeSnapshot:
    return RuntimeSnapshot(
        python=sys.version.split()[0],
        platform=platform.platform(),
        duckdb=duckdb.__version__,
        memory_limit=read_text_if_present(Path("/sys/fs/cgroup/memory.max")),
        cpu_limit=read_text_if_present(Path("/sys/fs/cgroup/cpu.max")),
        tmp_disk_free_bytes=shutil.disk_usage("/tmp").free,
    )


def read_text_if_present(path: Path) -> str | None:
    if not path.exists():
        return None
    return path.read_text(encoding="utf-8").strip()


def render_html(
    summary: QuerySummary,
    runtime: RuntimeSnapshot,
    generated_at: str,
    duration_seconds: float,
) -> str:
    rows = {
        "Sensor rows": f"{summary.sensor_rows:,}",
        "Event rows": f"{summary.event_rows:,}",
        "Weather hours": f"{summary.weather_hour_rows:,}",
        "Rain readings": f"{summary.rain_reading_rows:,}",
        "Sensor window": (
            f"{summary.first_sensor_timestamp} to {summary.last_sensor_timestamp}"
        ),
        "Latest basement absolute humidity": format_optional(
            summary.latest_basement_absolute_humidity_g_m3
        ),
        "Mean basement absolute humidity": format_optional(
            summary.mean_basement_absolute_humidity_g_m3
        ),
        "Python": runtime.python,
        "DuckDB": runtime.duckdb,
        "Platform": runtime.platform,
        "Cgroup memory limit": runtime.memory_limit or "not detected",
        "Cgroup CPU limit": runtime.cpu_limit or "not detected",
        "Run duration": f"{duration_seconds:.3f}s",
    }
    table_rows = "\n".join(
        f"<tr><th>{html.escape(label)}</th><td>{html.escape(value)}</td></tr>"
        for label, value in rows.items()
    )
    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Cloudflare Container DuckDB Prototype</title>
  <style>
    body {{ font-family: system-ui, sans-serif; margin: 2rem; line-height: 1.45; }}
    table {{ border-collapse: collapse; min-width: min(100%, 760px); }}
    th, td {{ border-bottom: 1px solid #ddd; padding: .5rem .65rem; text-align: left; }}
    th {{ width: 18rem; }}
    code {{ background: #f3f4f6; padding: .1rem .25rem; }}
  </style>
</head>
<body>
  <h1>Cloudflare Container DuckDB Prototype</h1>
  <p>
    Generated <code>{html.escape(generated_at)}</code> from partitioned Parquet with DuckDB.
    This is a representative static publication artifact, not the production dashboard.
  </p>
  <table>{table_rows}</table>
</body>
</html>
"""


def format_optional(value: float | None) -> str:
    if value is None:
        return "n/a"
    return f"{value:.2f} g/m3"


def publish_to_local_dir(output_dir: Path, site_prefix: str, artifacts: dict[str, str]) -> None:
    target_dir = output_dir / site_prefix
    target_dir.mkdir(parents=True, exist_ok=True)
    for filename, content in artifacts.items():
        (target_dir / filename).write_text(content, encoding="utf-8")


def publish_to_r2(args: argparse.Namespace, artifacts: dict[str, str]) -> None:
    import boto3

    client = boto3.client(
        service_name="s3",
        endpoint_url=args.r2_endpoint_url,
        aws_access_key_id=args.r2_access_key_id,
        aws_secret_access_key=args.r2_secret_access_key,
        region_name="auto",
    )
    for filename, content in artifacts.items():
        key = f"{args.site_prefix.strip('/')}/{filename}"
        client.put_object(
            Bucket=args.r2_bucket,
            Key=key,
            Body=content.encode("utf-8"),
            ContentType=content_type(filename),
        )


def content_type(filename: str) -> str:
    if filename.endswith(".html"):
        return "text/html; charset=utf-8"
    if filename.endswith(".json"):
        return "application/json; charset=utf-8"
    return "application/octet-stream"


if __name__ == "__main__":
    main()
