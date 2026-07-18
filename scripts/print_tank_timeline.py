"""Print the inferred tank timeline from the local curated snapshot."""

from __future__ import annotations

from pathlib import Path

from basement_analysis.curated_dataset import load_curated_dataset
from basement_analysis.tank_estimator import TankEstimateFailure, estimate_tank_history

SNAPSHOT_DIR = Path(__file__).resolve().parent.parent / "local" / "r2-parquet-snapshot"


def main() -> None:
    if not SNAPSHOT_DIR.exists():
        raise SystemExit(f"Curated snapshot not found: {SNAPSHOT_DIR}")

    curated_dataset = load_curated_dataset(SNAPSHOT_DIR)
    result = estimate_tank_history(curated_dataset.sensor_readings)
    if isinstance(result, TankEstimateFailure):
        raise SystemExit(f"Could not infer tank timeline: {result.reason}")

    print("Inferred tank timeline from the local curated snapshot:")
    for interval in result.complete_fill_intervals:
        duration_days = (interval.full_at - interval.started_at).total_seconds() / 86400
        print(
            f"  fill {interval.started_at} -> {interval.full_at} "
            f"({duration_days:.2f} d, {interval.extraction_cycles} cycles)"
        )
    print(f"  tank-emptied events: {[str(event) for event in result.tank_emptied_events]}")
    print(f"  state: {result.state}")
    print(f"  footer: {result.footer_text}")


if __name__ == "__main__":
    main()
