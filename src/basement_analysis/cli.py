from __future__ import annotations

import argparse
from collections.abc import Sequence
from pathlib import Path

from basement_analysis.static_site import build_static_site


def main(argv: Sequence[str] | None = None) -> None:
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
        type=Path,
        default=None,
        help=(
            "Directory for the local partitioned Parquet analytical dataset. Defaults to "
            "<output-dir>/curated-data."
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
