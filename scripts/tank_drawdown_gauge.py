"""Moisture-drawdown fuel gauge for the dehumidifier tank — a tinkerable analysis script.

Run:  uv run python scripts/tank_drawdown_gauge.py

This is a *workbench*, not the production estimator. It reads a local Parquet snapshot of the
curated dataset plus the current events derived from the R2 event store, then reports:

  1. how the tank is best measured (compares candidate "fuel gauges" by how constant they are
     across completed tanks — each completed tank == 25 L of water);
  2. the calibration and per-tank breakdown of the chosen gauge;
  3. the live state of the current (open) tank: % full, cycles remaining, time remaining;
  4. an honest leave-one-out backtest against the old calendar-days model.

The core idea (see .scratch/tank-fill-reassessment/FINDINGS.md): the tank fills with a fixed
volume of water, so the right state variable is *litres accumulated since empty*. Each extraction
cycle's absolute-humidity drawdown (peak -> trough drop) is a proxy for the water it condensed;
summing those drawdowns tracks litres far better than counting cycles (which over-counts the
shallow cycles of a dry basement) or counting days (which ignores idle spells).

Everything you'd want to tinker with is a CONSTANT below. No production code depends on this file.
"""

from __future__ import annotations

from datetime import datetime
from pathlib import Path

import duckdb
import numpy as np

from basement_analysis.curated_dataset import load_events_from_event_store, r2_events_glob
from basement_analysis.event_store import EventType
from basement_analysis.summaries import Event, dehumidifier_installed_at

# ---------------------------------------------------------------------------------------------
# KNOBS — edit these
# ---------------------------------------------------------------------------------------------
REPOSITORY_ROOT = Path(__file__).resolve().parent.parent
SNAPSHOT_DIRECTORY = (
    REPOSITORY_ROOT / "data" / "parquet-2026-08-07"
)  # local `aws s3 cp` of datasets/ from R2
TANK_CAPACITY_LITRES = 25

# Signal processing (kept aligned with the shipped estimator so cycle detection is comparable)
SMOOTH_WINDOW_MINUTES = 9  # centred rolling median over 1-min relative humidity
TROUGH_HALF_WINDOW_MINUTES = 10  # a trough/peak is a local extremum over +/- this window
PROMINENCE_WINDOW_MINUTES = 90  # prominence measured against this surrounding span
PROMINENCE_MINIMUM_RELATIVE_HUMIDITY = (
    0.8  # relative-humidity points a cycle must stand out by to count
)
COLLAPSE_MINUTES = 15  # extrema closer than this collapse into one

# Gauge / live estimate
DRAWDOWN_METRIC = (
    "absolute_humidity"  # "absolute_humidity" (physical, placement-robust) or "relative_humidity"
)
RECENT_WINDOW_DAYS = 3  # trailing window used for the *current* fill rate
RESUME_MINIMUM_TROUGHS = 3  # cycling has "resumed" once this many troughs fall within...
RESUME_WINDOW_MINUTES = 180  # ...this span after a tank-full event -> the emptied time


# ---------------------------------------------------------------------------------------------
# Load
# ---------------------------------------------------------------------------------------------
def load_basement(installed_at: datetime) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    """Return timestamp, minute, RH, and AH arrays for Basement readings since install."""
    connection = duckdb.connect()
    rows = connection.execute(
        f"""
        select epoch(timestamp)::bigint, relative_humidity_pct, absolute_humidity_g_m3
        from read_parquet(
            '{SNAPSHOT_DIRECTORY}/sensor-readings/**/*.parquet', hive_partitioning=true
        )
        where location = 'Basement'
          and timestamp >= timestamptz '{installed_at.isoformat()}'
        order by timestamp
        """
    ).fetchall()
    columns = np.array(rows, dtype=float)
    timestamps = columns[:, 0].astype("datetime64[s]")
    minute_index = (timestamps - timestamps[0]).astype("timedelta64[m]").astype(int)
    return timestamps, minute_index, columns[:, 1], columns[:, 2]


def load_tank_events() -> tuple[datetime, list[datetime]]:
    """Install instant and tank-full instants from the current R2 event-store state.

    With multiple install events the earliest wins; without one the workbench cannot establish
    its first fill interval and exits with a useful error.
    """
    events: list[Event] = load_events_from_event_store(r2_events_glob())
    installed_at = dehumidifier_installed_at(events)
    if installed_at is None:
        raise SystemExit("No dehumidifier_installed event found in the event store")
    tank_full_events = sorted(
        event.timestamp for event in events if event.event_type == EventType.dehumidifier_tank_full
    )
    return installed_at, tank_full_events


# ---------------------------------------------------------------------------------------------
# Signal processing
# ---------------------------------------------------------------------------------------------
def rolling_median(values: np.ndarray, window: int) -> np.ndarray:
    half_window = window // 2
    return np.array(
        [
            np.median(values[max(0, i - half_window) : i + half_window + 1])
            for i in range(len(values))
        ]
    )


def find_extrema(values: np.ndarray, kind: int) -> list[int]:
    """Indices of prominent local minima (kind=-1) or maxima (kind=+1)."""
    half_window = TROUGH_HALF_WINDOW_MINUTES
    prominence_half_window = PROMINENCE_WINDOW_MINUTES // 2
    raw_indices = []
    for i in range(len(values)):
        segment = values[max(0, i - half_window) : min(len(values), i + half_window + 1)]
        is_extreme = values[i] == segment.min() if kind == -1 else values[i] == segment.max()
        if not is_extreme:
            continue
        left = values[max(0, i - prominence_half_window) : i]
        right = values[i + 1 : i + prominence_half_window + 1]
        if not len(left) or not len(right):
            continue
        prominence = (
            (min(left.max(), right.max()) - values[i])
            if kind == -1
            else (values[i] - max(left.min(), right.min()))
        )
        if prominence >= PROMINENCE_MINIMUM_RELATIVE_HUMIDITY:
            raw_indices.append(i)
    collapsed: list[int] = []
    for i in raw_indices:
        if collapsed and i - collapsed[-1] < COLLAPSE_MINUTES:
            is_better = (
                values[i] < values[collapsed[-1]]
                if kind == -1
                else values[i] > values[collapsed[-1]]
            )
            if is_better:
                collapsed[-1] = i
        else:
            collapsed.append(i)
    return collapsed


# ---------------------------------------------------------------------------------------------
# Cycles, intervals, gauge
# ---------------------------------------------------------------------------------------------
class Analysis:
    """Everything derived from the raw signal, computed once."""

    def __init__(self) -> None:
        self.installed_at, self.full_events = load_tank_events()
        self.timestamps, self.minute_index, self.relative_humidity, self.absolute_humidity = (
            load_basement(self.installed_at)
        )
        self.smoothed_relative_humidity = rolling_median(
            self.relative_humidity, SMOOTH_WINDOW_MINUTES
        )
        self.troughs = find_extrema(self.smoothed_relative_humidity, kind=-1)
        self.peaks = find_extrema(self.smoothed_relative_humidity, kind=+1)
        self.drawdown_metric = (
            self.absolute_humidity
            if DRAWDOWN_METRIC == "absolute_humidity"
            else self.relative_humidity
        )
        # per cycle: (minute at trough, drawdown = preceding-peak metric - trough metric)
        self.cycles = []
        for trough_index in self.troughs:
            peak_index = self._preceding_peak(trough_index)
            if peak_index is not None:
                drawdown = max(
                    0.0, self.drawdown_metric[peak_index] - self.drawdown_metric[trough_index]
                )
                self.cycles.append((self.minute_index[trough_index], drawdown))
        self.cycle_minutes = np.array([cycle[0] for cycle in self.cycles])
        self.cycle_drawdowns = np.array([cycle[1] for cycle in self.cycles])
        self.emptied = [self._resume_after(event) for event in self.full_events]

    def _preceding_peak(self, trough_index: int) -> int | None:
        near = [
            peak
            for peak in self.peaks
            if peak < trough_index
            and self.minute_index[trough_index] - self.minute_index[peak] < 120
        ]
        return near[-1] if near else None

    def _minute_of(self, when: datetime | np.datetime64) -> int:
        return int((np.datetime64(when) - self.timestamps[0]).astype("timedelta64[m]").astype(int))

    def _resume_after(self, full: datetime) -> np.datetime64:
        """Emptied time = first trough after `full` with cycling clearly resumed around it."""
        full_minute = self._minute_of(full)
        for trough_index in self.troughs:
            if self.minute_index[trough_index] <= full_minute + 30:
                continue
            window = [
                other
                for other in self.troughs
                if self.minute_index[trough_index]
                <= self.minute_index[other]
                <= self.minute_index[trough_index] + RESUME_WINDOW_MINUTES
            ]
            if len(window) >= RESUME_MINIMUM_TROUGHS:
                return self.timestamps[trough_index]
        return np.datetime64(full) + np.timedelta64(6, "h")  # fallback

    def dose(self, start_minute: int, end_minute: int) -> float:
        """Cumulative per-cycle drawdown between two minute-indices."""
        return float(
            self.cycle_drawdowns[
                (self.cycle_minutes >= start_minute) & (self.cycle_minutes <= end_minute)
            ].sum()
        )

    def interval_bounds(self, tank_index: int) -> tuple[int, int]:
        start = (
            np.datetime64(self.installed_at.replace(tzinfo=None))
            if tank_index == 0
            else self.emptied[tank_index - 1]
        )
        return self._minute_of(start), self._minute_of(self.full_events[tank_index])

    def completed_tanks(self) -> list[tuple[float, float]]:
        """(dose, days) for each completed tank."""
        results = []
        for tank_index in range(len(self.full_events)):
            start_minute, end_minute = self.interval_bounds(tank_index)
            results.append(
                (self.dose(start_minute, end_minute), (end_minute - start_minute) / 1440)
            )
        return results


def coefficient_of_variation(values: np.ndarray) -> float:
    return float(np.std(values) / np.mean(values))


# ---------------------------------------------------------------------------------------------
# Report
# ---------------------------------------------------------------------------------------------
def main() -> None:
    if not SNAPSHOT_DIRECTORY.exists():
        raise SystemExit(
            f"Snapshot not found: {SNAPSHOT_DIRECTORY}\n"
            "Pull it with (creds in the repo .envrc):\n"
            "  AWS_ACCESS_KEY_ID=$R2_ACCESS_KEY_ID AWS_SECRET_ACCESS_KEY=$R2_SECRET_ACCESS_KEY \\\n"
            "  aws s3 cp s3://$R2_BUCKET/datasets/ <dir>/ --recursive "
            "--endpoint-url $R2_ENDPOINT_URL"
        )
    analysis = Analysis()
    tanks = np.array(analysis.completed_tanks())
    calibration = tanks[:, 0].mean()
    metric_label = DRAWDOWN_METRIC.replace("_", " ")  # "absolute humidity" for report headings

    print(
        f"data: Basement {str(analysis.timestamps[0])[:16]} -> {str(analysis.timestamps[-1])[:16]} "
        f"({len(analysis.timestamps)} min), {len(analysis.full_events)} logged tank-full events\n"
    )

    # 1. which gauge is most constant across tanks?
    print("=== fuel-gauge comparison (CoV across completed tanks; lower is better) ===")
    gauges = {
        f"per-cycle {metric_label}-drawdown sum": np.array(
            [
                analysis.dose(*analysis.interval_bounds(tank_index))
                for tank_index in range(len(analysis.full_events))
            ]
        ),
        "cycle count": np.array(
            [
                (
                    (analysis.cycle_minutes >= analysis.interval_bounds(tank_index)[0])
                    & (analysis.cycle_minutes <= analysis.interval_bounds(tank_index)[1])
                ).sum()
                for tank_index in range(len(analysis.full_events))
            ]
        ),
        "calendar days": tanks[:, 1],
    }
    for name, values in gauges.items():
        marker = "  <- chosen" if name.startswith("per-cycle") else ""
        print(f"  {name:38s} CoV={coefficient_of_variation(values):.3f}{marker}")

    # 2. calibration
    print(f"\n=== calibration ({metric_label}-drawdown per tank == {TANK_CAPACITY_LITRES} L) ===")
    print("  tank | emptied -> full | days | dose | dose/day")
    for tank_index, (dose, days) in enumerate(tanks):
        start = analysis.installed_at if tank_index == 0 else analysis.emptied[tank_index - 1]
        print(
            f"   {tank_index + 1}   | {str(start)[:16]} -> "
            f"{analysis.full_events[tank_index]:%Y-%m-%d %H:%M} | "
            f"{days:4.2f} | {dose:5.1f} | {dose / days:5.2f}"
        )
    print(
        f"  DOSE_PER_TANK = {calibration:.1f}   "
        f"scatter = +/-{tanks[:, 0].std() / calibration * 100:.0f}%"
    )

    # 3. live state
    now = int(analysis.minute_index[-1])
    open_start = analysis._minute_of(analysis.emptied[-1])
    open_dose = analysis.dose(open_start, now)
    fraction_full = open_dose / calibration
    remaining = max(0.0, calibration - open_dose)
    recent_drawdowns = analysis.cycle_drawdowns[
        (analysis.cycle_minutes >= now - RECENT_WINDOW_DAYS * 1440)
        & (analysis.cycle_minutes <= now)
    ]
    drawdown_per_cycle = (
        float(np.median(recent_drawdowns))
        if len(recent_drawdowns)
        else float(np.median(analysis.cycle_drawdowns))
    )
    cycles_remaining = remaining / drawdown_per_cycle if drawdown_per_cycle else float("inf")
    recent_rate = (
        analysis.dose(now - RECENT_WINDOW_DAYS * 1440, now) / RECENT_WINDOW_DAYS
    )  # dose/day
    days_remaining = remaining / recent_rate if recent_rate else float("inf")
    scatter_fraction = tanks[:, 0].std() / calibration
    print(f"\n=== LIVE (current open tank, emptied ~ {str(analysis.emptied[-1])[:16]}) ===")
    print(f"  elapsed              {(now - open_start) / 1440:.1f} d")
    print(
        f"  fraction full        {fraction_full * 100:.0f}%  "
        f"(~{fraction_full * TANK_CAPACITY_LITRES:.1f} of {TANK_CAPACITY_LITRES} L)"
    )
    print(f"  cycles remaining     ~{cycles_remaining:.0f}")
    print(
        f"  time remaining       ~{days_remaining:.1f} d  "
        f"(recent {RECENT_WINDOW_DAYS}d rate = {recent_rate:.1f} dose/day)"
    )
    print(
        f"                       range +/-{scatter_fraction * 100:.0f}% -> "
        f"{max(0.0, remaining * (1 - scatter_fraction)) / recent_rate if recent_rate else 0:.1f}"
        f"-{remaining * (1 + scatter_fraction) / recent_rate if recent_rate else 0:.1f} d"
    )

    # 4. backtest vs calendar-days, leave-one-out, causal at each interval midpoint
    print("\n=== backtest (predict at 50% of each tank's true time; leave-one-out) ===")
    print("  tank | true_d | gauge_d | naive_d")
    gauge_errors, naive_errors = [], []
    for tank_index in range(len(analysis.full_events)):
        start_minute, end_minute = analysis.interval_bounds(tank_index)
        true_days = (end_minute - start_minute) / 1440
        midpoint_minute = start_minute + (end_minute - start_minute) // 2
        dose_at_midpoint = analysis.dose(start_minute, midpoint_minute)
        calibration_excluding_tank = np.mean(
            [tanks[other, 0] for other in range(len(tanks)) if other != tank_index]
        )
        rate = dose_at_midpoint / max((midpoint_minute - start_minute) / 1440, 1e-9)
        gauge_days = (midpoint_minute - start_minute) / 1440 + max(
            0.0, calibration_excluding_tank - dose_at_midpoint
        ) / max(rate, 1e-9)
        naive_days = np.mean(
            [tanks[other, 1] for other in range(len(tanks)) if other != tank_index]
        )
        gauge_errors.append(gauge_days - true_days)
        naive_errors.append(naive_days - true_days)
        print(
            f"   {tank_index + 1}   | {true_days:5.2f}  | {gauge_days:5.2f}   | {naive_days:5.2f}"
        )
    print(
        f"  MAE: gauge {np.mean(np.abs(gauge_errors)):.2f} d   vs   "
        f"calendar-days {np.mean(np.abs(naive_errors)):.2f} d"
    )


if __name__ == "__main__":
    main()
