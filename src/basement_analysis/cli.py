from __future__ import annotations

import argparse
from collections.abc import Sequence
from pathlib import Path

from basement_analysis.curated_dataset import parse_curated_data_location
from basement_analysis.raw_email_ingest import print_ingest_results, process_raw_email_batch
from basement_analysis.static_site import build_static_site


def main(argv: Sequence[str] | None = None) -> None:
    argument_list = list(argv) if argv is not None else None
    if argument_list and argument_list[0] == "ingest-emails":
        ingest_emails(argument_list[1:])
        return
    if argument_list and argument_list[0] == "build-site":
        argument_list = argument_list[1:]
    build_site(argument_list)


def build_site(argv: Sequence[str] | None = None) -> None:
    """Run the local basement analysis command."""
    parser = argparse.ArgumentParser(description="Build the local basement analysis static site.")
    parser.add_argument(
        "--data-dir",
        type=Path,
        default=Path("data"),
        help="Directory containing thermohygrometer CSV exports and basement_events.csv.",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("build/basement-site"),
        help="Directory for the generated local static site.",
    )
    parser.add_argument(
        "--refresh-weather",
        action="store_true",
        help="Ignore cached public weather API responses.",
    )
    parser.add_argument(
        "--curated-data-dir",
        type=parse_curated_data_location,
        default=None,
        help=(
            "Location of the partitioned Parquet analytical dataset: a local directory or an "
            "s3:// URL read directly via DuckDB (R2 credentials from R2_ENDPOINT_URL, "
            "R2_ACCESS_KEY_ID, and R2_SECRET_ACCESS_KEY; s3:// requires --reuse-curated). "
            "Defaults to <output-dir>/curated-data."
        ),
    )
    parser.add_argument(
        "--reuse-curated",
        action="store_true",
        help="Build the site from existing curated Parquet files without reading CSVs or APIs.",
    )
    args = parser.parse_args(argv)

    result = build_static_site(
        data_dir=args.data_dir,
        output_dir=args.output_dir,
        refresh_weather=bool(args.refresh_weather),
        curated_dataset_dir=args.curated_data_dir,
        rebuild_curated_dataset=not bool(args.reuse_curated),
    )

    print(f"Wrote {result.index_path}")
    print(f"Wrote {result.report_path}")
    print(f"Curated data: {result.curated_dataset_dir}")
    print(f"Sensor rows: {result.sensor_row_count:,}")
    print(f"Weather hours: {result.weather_hour_count:,}")
    print(f"Rain readings: {result.rain_reading_count:,}")


def ingest_emails(argv: Sequence[str] | None = None) -> None:
    parser = argparse.ArgumentParser(
        description="Parse raw X-Sense .eml files into an R2-shaped local object tree."
    )
    parser.add_argument(
        "--raw-email-dir",
        type=Path,
        default=Path("data/email"),
        help="Directory to scan recursively for raw .eml files.",
    )
    parser.add_argument(
        "--object-store-dir",
        type=Path,
        default=Path("build/basement-ingest-objects"),
        help="Local directory that mirrors the R2 object-key layout.",
    )
    parser.add_argument(
        "--raw-object-key-prefix",
        default="raw-emails/source=x-sense",
        help=(
            "Object-key prefix prepended to local .eml relative paths. Use an empty string when "
            "--raw-email-dir already points at an object-store root."
        ),
    )
    args = parser.parse_args(argv)

    results = process_raw_email_batch(
        raw_email_dir=args.raw_email_dir,
        object_store_dir=args.object_store_dir,
        raw_object_key_prefix=args.raw_object_key_prefix,
    )
    print_ingest_results(results)
