from __future__ import annotations

import argparse
import json
import sys
from collections.abc import Sequence
from pathlib import Path
from typing import cast

from basement_analysis.curated_dataset import parse_curated_data_location
from basement_analysis.hosted_curation import curate_accepted_email_csvs
from basement_analysis.observability import (
    PhaseRecorder,
    configure_run_logging,
    load_command_timing_records,
    render_timings_markdown,
    write_build_info,
    write_command_timing_record,
)
from basement_analysis.raw_email_ingest import print_ingest_results, process_raw_email_batch
from basement_analysis.static_site import build_static_site

DEFAULT_TIMINGS_DIR = Path("build/timings")


def main(argv: Sequence[str] | None = None) -> None:
    configure_run_logging()
    argument_list = list(argv) if argv is not None else sys.argv[1:]
    if argument_list and argument_list[0] == "ingest-emails":
        ingest_emails(argument_list[1:])
        return
    if argument_list and argument_list[0] == "curate-ingested-r2":
        curate_ingested_r2(argument_list[1:])
        return
    if argument_list and argument_list[0] == "timings-summary":
        timings_summary(argument_list[1:])
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
    parser.add_argument(
        "--timings-dir",
        type=Path,
        default=DEFAULT_TIMINGS_DIR,
        help="Directory where per-command phase-timing JSON records are written and read.",
    )
    args = parser.parse_args(argv)

    recorder = PhaseRecorder()
    result = build_static_site(
        data_dir=args.data_dir,
        output_dir=args.output_dir,
        refresh_weather=bool(args.refresh_weather),
        curated_dataset_dir=args.curated_data_dir,
        rebuild_curated_dataset=not bool(args.reuse_curated),
        phase_recorder=recorder,
    )
    site_counts = {
        "sensor_row_count": result.sensor_row_count,
        "weather_hour_count": result.weather_hour_count,
        "rain_reading_count": result.rain_reading_count,
    }
    write_command_timing_record(
        timings_dir=args.timings_dir,
        command="build-site",
        recorder=recorder,
        counts=site_counts,
    )
    build_info_path = write_build_info(
        build_info_path=args.output_dir / "build-info.json",
        newest_sensor_reading=result.newest_sensor_reading,
        counts=site_counts,
        command_records=load_command_timing_records(args.timings_dir),
    )

    print(f"Wrote {result.index_path}")
    print(f"Wrote {result.report_path}")
    print(f"Wrote {build_info_path}")
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


def curate_ingested_r2(argv: Sequence[str] | None = None) -> None:
    parser = argparse.ArgumentParser(
        description=(
            "Merge accepted X-Sense CSV objects from a local R2 mirror into hosted "
            "partitioned Parquet."
        )
    )
    parser.add_argument(
        "--object-store-dir",
        type=Path,
        default=Path("build/r2-pipeline"),
        help="Local directory mirroring the R2 pipeline bucket's manifests and csv prefixes.",
    )
    parser.add_argument(
        "--curated-data-dir",
        type=Path,
        default=Path("build/curated-r2-parquet"),
        help="Local directory where the refreshed partitioned Parquet tree is written.",
    )
    parser.add_argument(
        "--existing-curated-data-dir",
        type=parse_curated_data_location,
        default=None,
        help=("Existing curated Parquet root to merge from. Defaults to s3://$R2_BUCKET/parquet."),
    )
    parser.add_argument(
        "--work-dir",
        type=Path,
        default=Path("build/hosted-curation"),
        help="Scratch directory for staged accepted CSVs and weather API cache files.",
    )
    parser.add_argument(
        "--refresh-weather",
        action="store_true",
        help="Ignore cached public weather API responses while rebuilding weather partitions.",
    )
    parser.add_argument(
        "--timings-dir",
        type=Path,
        default=DEFAULT_TIMINGS_DIR,
        help="Directory where this command's phase-timing JSON record is written.",
    )
    args = parser.parse_args(argv)

    recorder = PhaseRecorder()
    result = curate_accepted_email_csvs(
        object_store_dir=args.object_store_dir,
        curated_dataset_dir=args.curated_data_dir,
        work_dir=args.work_dir,
        existing_curated_dataset_root=args.existing_curated_data_dir,
        refresh_weather=bool(args.refresh_weather),
        phase_recorder=recorder,
    )
    write_command_timing_record(
        timings_dir=args.timings_dir,
        command="curate-ingested-r2",
        recorder=recorder,
        counts={
            "accepted_csv_count": result.accepted_csv_count,
            "existing_sensor_row_count": result.existing_sensor_row_count,
            "staged_sensor_row_count": result.staged_sensor_row_count,
            "merged_sensor_row_count": result.merged_sensor_row_count,
            "weather_hour_count": result.weather_hour_count,
            "rain_reading_count": result.rain_reading_count,
        },
    )
    print(f"Accepted CSV objects: {result.accepted_csv_count:,}")
    print(f"Existing sensor rows: {result.existing_sensor_row_count:,}")
    print(f"Staged sensor rows: {result.staged_sensor_row_count:,}")
    print(f"Merged sensor rows: {result.merged_sensor_row_count:,}")
    print(f"Weather hours: {result.weather_hour_count:,}")
    print(f"Rain readings: {result.rain_reading_count:,}")
    print(f"Curated data: {result.curated_dataset_dir}")


def timings_summary(argv: Sequence[str] | None = None) -> None:
    parser = argparse.ArgumentParser(
        description=(
            "Print recorded pipeline phase timings (and optional build info) as markdown, "
            "for example into a GitHub Actions job summary."
        )
    )
    parser.add_argument(
        "--timings-dir",
        type=Path,
        default=DEFAULT_TIMINGS_DIR,
        help="Directory containing per-command phase-timing JSON records.",
    )
    parser.add_argument(
        "--build-info",
        type=Path,
        default=None,
        help="Optional build-info.json whose freshness fields are appended to the summary.",
    )
    args = parser.parse_args(argv)

    build_info: dict[str, object] | None = None
    if args.build_info is not None:
        build_info = cast(
            dict[str, object], json.loads(args.build_info.read_text(encoding="utf-8"))
        )
    print(render_timings_markdown(load_command_timing_records(args.timings_dir), build_info))
