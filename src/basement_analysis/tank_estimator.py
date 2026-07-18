"""Infer dehumidifier tank history from the basement relative-humidity signal.

Detection thresholds are spec-verbatim from the "Dehumidifier next-full estimate" PRD:

1. Smooth relative humidity with a centred 9-minute rolling median.
2. Extraction-cycle troughs: local minima over a ±10-minute window with at least 0.8 RH
   points of prominence against the surrounding 90 minutes; troughs closer than 15 minutes
   collapse into one.
3. Tank-full episode: a trough-to-trough gap longer than 2 hours in which smoothed RH exceeds
   the current fill interval's 90th-percentile trough RH by more than 3 points; bounding
   troughs are the tank-full and tank-emptied events. Percentile computed per fill interval,
   not globally.
4. Resumed cycling shorter than 8 hours between qualifying gaps does not split a tank-full
   episode.

Model: next-full estimate = most recent tank-emptied event + equal-weighted mean duration of
all complete fill intervals; displayed uncertainty = half the range of observed complete fill
durations, rounded to the nearest half day, with a floor of half a day.
"""

from __future__ import annotations

import math
import statistics
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Literal, Protocol


class BasementReading(Protocol):
    """The slice of a sensor reading the tank estimator consumes."""

    @property
    def timestamp(self) -> datetime: ...

    @property
    def location(self) -> str: ...

    @property
    def relative_humidity_pct(self) -> float: ...


DEHUMIDIFIER_INSTALLED_AT = datetime(2026, 7, 1, 21, 0)
TANK_CAPACITY_LITRES = 25

SMOOTHING_WINDOW_MINUTES = 9
LOCAL_MINIMUM_HALF_WINDOW_MINUTES = 10
PROMINENCE_SURROUNDING_MINUTES = 90
PROMINENCE_MINIMUM_RH_POINTS = 0.8
TROUGH_COLLAPSE_MINUTES = 15
TANK_FULL_GAP_HOURS = 2
CYCLING_BAND_EXCESS_RH_POINTS = 3
EPISODE_MERGE_RESUMED_CYCLING_HOURS = 8

TankState = Literal["predicted_next_full", "not_running", "filling_longer_than_expected"]


@dataclass(frozen=True)
class TankEstimateFailure:
    reason: str


@dataclass(frozen=True)
class FillInterval:
    started_at: datetime
    full_at: datetime
    extraction_cycles: int


@dataclass(frozen=True)
class TankHistory:
    tank_full_events: tuple[datetime, ...]
    tank_emptied_events: tuple[datetime, ...]
    complete_fill_intervals: tuple[FillInterval, ...]
    completed_fill_count: int
    litres_removed: int
    state: TankState
    next_full_estimate: datetime | None
    uncertainty_days: float | None
    footer_text: str


@dataclass(frozen=True)
class TankFullEpisode:
    full_position: int
    emptied_position: int


def estimate_tank_history(
    sensor_readings: Sequence[BasementReading],
) -> TankHistory | TankEstimateFailure:
    basement_readings = sorted(
        (
            reading
            for reading in sensor_readings
            if reading.location == "Basement"
            and reading.timestamp >= DEHUMIDIFIER_INSTALLED_AT
        ),
        key=lambda reading: reading.timestamp,
    )
    if not basement_readings:
        return TankEstimateFailure(
            reason="no basement readings at or after the dehumidifier installation"
        )

    timestamps = [reading.timestamp for reading in basement_readings]
    smoothed = smoothed_relative_humidity(basement_readings)
    trough_indices = detect_trough_indices(smoothed)
    episodes = detect_tank_full_episodes(timestamps, smoothed, trough_indices)
    if not episodes:
        return TankEstimateFailure(reason="no complete fill intervals detected")

    trough_times = [timestamps[index] for index in trough_indices]
    tank_full_events = tuple(trough_times[episode.full_position] for episode in episodes)
    tank_emptied_events = tuple(trough_times[episode.emptied_position] for episode in episodes)
    complete_fill_intervals = tuple(
        FillInterval(
            started_at=started_at,
            full_at=full_at,
            extraction_cycles=sum(
                1 for trough_time in trough_times if started_at <= trough_time <= full_at
            ),
        )
        for started_at, full_at in zip(
            (DEHUMIDIFIER_INSTALLED_AT, *tank_emptied_events[:-1]),
            tank_full_events,
            strict=True,
        )
    )

    completed_fill_count = len(episodes)
    litres_removed = completed_fill_count * TANK_CAPACITY_LITRES
    fill_durations = [
        interval.full_at - interval.started_at for interval in complete_fill_intervals
    ]
    mean_fill_duration = sum(fill_durations, timedelta()) / len(fill_durations)
    latest_reading_at = timestamps[-1]

    if in_tank_full_episode_at_latest_reading(
        timestamps, smoothed, trough_indices, episodes[-1].emptied_position
    ):
        state: TankState = "not_running"
        next_full_estimate = None
        uncertainty_days = None
    else:
        next_full_estimate = tank_emptied_events[-1] + mean_fill_duration
        uncertainty_days = displayed_uncertainty_days(fill_durations)
        state = (
            "predicted_next_full"
            if next_full_estimate >= latest_reading_at
            else "filling_longer_than_expected"
        )

    return TankHistory(
        tank_full_events=tank_full_events,
        tank_emptied_events=tank_emptied_events,
        complete_fill_intervals=complete_fill_intervals,
        completed_fill_count=completed_fill_count,
        litres_removed=litres_removed,
        state=state,
        next_full_estimate=next_full_estimate,
        uncertainty_days=uncertainty_days,
        footer_text=footer_text(
            completed_fill_count, litres_removed, state, next_full_estimate, uncertainty_days
        ),
    )


def smoothed_relative_humidity(readings: Sequence[BasementReading]) -> list[float]:
    """Centred 9-minute rolling median over the 1-minute series."""
    values = [reading.relative_humidity_pct for reading in readings]
    half_window = SMOOTHING_WINDOW_MINUTES // 2
    return [
        statistics.median(values[max(0, index - half_window) : index + half_window + 1])
        for index in range(len(values))
    ]


def detect_trough_indices(smoothed: Sequence[float]) -> list[int]:
    """Extraction-cycle troughs per the spec-verbatim rules."""
    local_minimum_indices = [
        index
        for index in range(len(smoothed))
        if smoothed[index]
        == min(
            smoothed[
                max(0, index - LOCAL_MINIMUM_HALF_WINDOW_MINUTES) : index
                + LOCAL_MINIMUM_HALF_WINDOW_MINUTES
                + 1
            ]
        )
    ]

    plateau_centres: list[int] = []
    run_start = 0
    for position in range(1, len(local_minimum_indices) + 1):
        is_run_end = (
            position == len(local_minimum_indices)
            or local_minimum_indices[position] != local_minimum_indices[position - 1] + 1
        )
        if is_run_end:
            run = local_minimum_indices[run_start:position]
            plateau_centres.append(run[len(run) // 2])
            run_start = position

    prominence_half_window = PROMINENCE_SURROUNDING_MINUTES // 2
    prominent: list[int] = []
    for index in plateau_centres:
        left = smoothed[max(0, index - prominence_half_window) : index]
        right = smoothed[index + 1 : index + prominence_half_window + 1]
        if not left or not right:
            continue
        prominence = min(max(left), max(right)) - smoothed[index]
        if prominence >= PROMINENCE_MINIMUM_RH_POINTS:
            prominent.append(index)

    collapsed: list[int] = []
    for index in prominent:
        if collapsed and index - collapsed[-1] < TROUGH_COLLAPSE_MINUTES:
            if smoothed[index] < smoothed[collapsed[-1]]:
                collapsed[-1] = index
        else:
            collapsed.append(index)
    return collapsed


def percentile_90(values: Sequence[float]) -> float:
    ordered = sorted(values)
    return ordered[max(0, math.ceil(0.9 * len(ordered)) - 1)]


def cycling_band_threshold(
    smoothed: Sequence[float],
    trough_indices: Sequence[int],
    interval_start_position: int,
    leading_position: int,
) -> float:
    """Current fill interval's 90th-percentile trough RH plus the 3-point excess."""
    interval_trough_rh = [
        smoothed[trough_indices[position]]
        for position in range(interval_start_position, leading_position + 1)
    ]
    return percentile_90(interval_trough_rh) + CYCLING_BAND_EXCESS_RH_POINTS


def gap_qualifies(
    timestamps: Sequence[datetime],
    smoothed: Sequence[float],
    trough_indices: Sequence[int],
    interval_start_position: int,
    leading_position: int,
) -> bool:
    leading_index = trough_indices[leading_position]
    trailing_index = trough_indices[leading_position + 1]
    gap = timestamps[trailing_index] - timestamps[leading_index]
    if gap <= timedelta(hours=TANK_FULL_GAP_HOURS):
        return False
    threshold = cycling_band_threshold(
        smoothed, trough_indices, interval_start_position, leading_position
    )
    return max(smoothed[leading_index + 1 : trailing_index]) > threshold


def detect_tank_full_episodes(
    timestamps: Sequence[datetime],
    smoothed: Sequence[float],
    trough_indices: Sequence[int],
) -> list[TankFullEpisode]:
    """Group trough-to-trough gaps into tank-full episodes per the spec-verbatim rules."""
    episodes: list[TankFullEpisode] = []
    interval_start_position = 0

    position = 0
    while position < len(trough_indices) - 1:
        if not gap_qualifies(
            timestamps, smoothed, trough_indices, interval_start_position, position
        ):
            position += 1
            continue
        full_position = position
        emptied_position = position + 1
        # Absorb resumed-cycling blips shorter than 8 hours between qualifying gaps.
        scan = emptied_position
        while scan < len(trough_indices) - 1:
            if gap_qualifies(timestamps, smoothed, trough_indices, interval_start_position, scan):
                resumed_cycling = (
                    timestamps[trough_indices[scan]]
                    - timestamps[trough_indices[emptied_position]]
                )
                if resumed_cycling < timedelta(hours=EPISODE_MERGE_RESUMED_CYCLING_HOURS):
                    emptied_position = scan + 1
            scan += 1
        episodes.append(
            TankFullEpisode(full_position=full_position, emptied_position=emptied_position)
        )
        interval_start_position = emptied_position
        position = emptied_position

    return episodes


def in_tank_full_episode_at_latest_reading(
    timestamps: Sequence[datetime],
    smoothed: Sequence[float],
    trough_indices: Sequence[int],
    interval_start_position: int,
) -> bool:
    """An in-progress episode: a qualifying gap open from the final trough to the data's end."""
    final_trough_index = trough_indices[-1]
    gap = timestamps[-1] - timestamps[final_trough_index]
    if gap <= timedelta(hours=TANK_FULL_GAP_HOURS):
        return False
    threshold = cycling_band_threshold(
        smoothed, trough_indices, interval_start_position, len(trough_indices) - 1
    )
    return max(smoothed[final_trough_index + 1 :]) > threshold


def displayed_uncertainty_days(fill_durations: Sequence[timedelta]) -> float:
    """Half the duration range, rounded to the nearest half day, floored at half a day."""
    half_range_days = (
        max(fill_durations) - min(fill_durations)
    ).total_seconds() / 2 / 86400
    return max(0.5, round(half_range_days * 2) / 2)


def uncertainty_words(uncertainty_days: float) -> str:
    if uncertainty_days == 0.5:
        return "half a day"
    whole_days = int(uncertainty_days)
    if uncertainty_days == whole_days:
        return f"{whole_days} day" if whole_days == 1 else f"{whole_days} days"
    return f"{whole_days}½ days"


def format_footer_datetime(timestamp: datetime) -> str:
    return f"{timestamp:%a} {timestamp.day} {timestamp:%b} {timestamp:%H:%M}"


def footer_text(
    completed_fill_count: int,
    litres_removed: int,
    state: TankState,
    next_full_estimate: datetime | None,
    uncertainty_days: float | None,
) -> str:
    lead = (
        f"The dehumidifier has filled {completed_fill_count} times so far, "
        f"removing {litres_removed} litres of water."
    )
    if state == "not_running":
        return f"{lead} The dehumidifier is not running as of the latest data."
    if state == "filling_longer_than_expected":
        return (
            f"{lead} Dehumidifier tank has been filling longer than expected, "
            "it may be full at any time."
        )
    assert next_full_estimate is not None and uncertainty_days is not None
    return (
        f"{lead} Dehumidifier tank predicted next full "
        f"{format_footer_datetime(next_full_estimate)} ± {uncertainty_words(uncertainty_days)}."
    )
