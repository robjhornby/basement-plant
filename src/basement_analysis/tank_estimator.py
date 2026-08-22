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
from datetime import datetime, timedelta
from typing import Literal, Protocol

from pydantic import BaseModel, ConfigDict


class BasementReading(Protocol):
    """The slice of a sensor reading the tank estimator consumes."""

    @property
    def timestamp(self) -> datetime: ...

    @property
    def location(self) -> str: ...

    @property
    def relative_humidity_pct(self) -> float: ...

    @property
    def absolute_humidity_g_m3(self) -> float: ...


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


class TankEstimateFailure(BaseModel):
    model_config = ConfigDict(frozen=True)

    reason: str


class FillInterval(BaseModel):
    model_config = ConfigDict(frozen=True)

    started_at: datetime
    full_at: datetime
    extraction_cycles: int


class TankHistory(BaseModel):
    model_config = ConfigDict(frozen=True)

    tank_full_events: tuple[datetime, ...]
    tank_emptied_events: tuple[datetime, ...]
    complete_fill_intervals: tuple[FillInterval, ...]
    completed_fill_count: int
    litres_removed: int
    state: TankState
    next_full_estimate: datetime | None
    uncertainty_days: float | None
    footer_text: str


class TankFullEpisode(BaseModel):
    model_config = ConfigDict(frozen=True)

    full_position: int
    emptied_position: int


def estimate_tank_history(
    sensor_readings: Sequence[BasementReading],
) -> TankHistory | TankEstimateFailure:
    basement_readings = sorted(
        (
            reading
            for reading in sensor_readings
            if reading.location == "Basement" and reading.timestamp >= DEHUMIDIFIER_INSTALLED_AT
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
    return detect_extremum_indices(smoothed, "trough")


def detect_peak_indices(smoothed: Sequence[float]) -> list[int]:
    """Extraction-cycle peaks: the trough rule applied to local maxima."""
    return detect_extremum_indices(smoothed, "peak")


def detect_extremum_indices(
    smoothed: Sequence[float], kind: Literal["trough", "peak"]
) -> list[int]:
    """Prominent local minima (troughs) or maxima (peaks) per the spec-verbatim rules.

    Troughs and peaks share the detection: a ±10-minute local extremum with at least
    0.8 RH points of prominence against the surrounding 90 minutes, with extrema closer
    than 15 minutes collapsed to the more extreme of the two.
    """
    is_trough = kind == "trough"
    local_extremum_indices = [
        index
        for index in range(len(smoothed))
        if smoothed[index]
        == (min if is_trough else max)(
            smoothed[
                max(0, index - LOCAL_MINIMUM_HALF_WINDOW_MINUTES) : index
                + LOCAL_MINIMUM_HALF_WINDOW_MINUTES
                + 1
            ]
        )
    ]

    plateau_centres: list[int] = []
    run_start = 0
    for position in range(1, len(local_extremum_indices) + 1):
        is_run_end = (
            position == len(local_extremum_indices)
            or local_extremum_indices[position] != local_extremum_indices[position - 1] + 1
        )
        if is_run_end:
            run = local_extremum_indices[run_start:position]
            plateau_centres.append(run[len(run) // 2])
            run_start = position

    prominence_half_window = PROMINENCE_SURROUNDING_MINUTES // 2
    prominent: list[int] = []
    for index in plateau_centres:
        left = smoothed[max(0, index - prominence_half_window) : index]
        right = smoothed[index + 1 : index + prominence_half_window + 1]
        if not left or not right:
            continue
        prominence = (
            min(max(left), max(right)) - smoothed[index]
            if is_trough
            else smoothed[index] - max(min(left), min(right))
        )
        if prominence >= PROMINENCE_MINIMUM_RH_POINTS:
            prominent.append(index)

    collapsed: list[int] = []
    for index in prominent:
        if collapsed and index - collapsed[-1] < TROUGH_COLLAPSE_MINUTES:
            is_more_extreme = (
                smoothed[index] < smoothed[collapsed[-1]]
                if is_trough
                else smoothed[index] > smoothed[collapsed[-1]]
            )
            if is_more_extreme:
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
                    timestamps[trough_indices[scan]] - timestamps[trough_indices[emptied_position]]
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
    half_range_days = (max(fill_durations) - min(fill_durations)).total_seconds() / 2 / 86400
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


# ---------------------------------------------------------------------------
# Moisture-drawdown fuel gauge
#
# Replaces the calendar-days next-full model with a "litres accumulated since
# empty" gauge. See .scratch/tank-fill-reassessment/{PRD.md,FINDINGS.md} and the
# workbench scripts/tank_drawdown_gauge.py, which this ports into production shape.
# Footer rendering is issue 02; getting logged events into the hosted feed is
# issue 03 — this function is handed the tank-full events directly.
# ---------------------------------------------------------------------------

GaugeState = Literal["filling", "full_or_overdue", "not_running"]

PRECEDING_PEAK_MINUTES = 120
RECENT_WINDOW_DAYS = 3
RESUME_MINIMUM_DELAY_MINUTES = 30
RESUME_MINIMUM_TROUGHS = 3
RESUME_WINDOW_MINUTES = 180
RESUME_FALLBACK_HOURS = 6
# filling -> full_or_overdue boundary, pinned against the real 2026-08-07 snapshot (issue 02):
# the live tank sat at fraction_full 0.999, and percent renders to the nearest whole, so anything
# from 0.95 up prints "about 100% full" and belongs in the "may be full" sentence, not "filling".
FULL_FRACTION_THRESHOLD = 0.95


class DrawdownCycle(BaseModel):
    """One extraction cycle's moisture drawdown: the trough time and the
    absolute-humidity drop from its preceding peak (clamped at zero)."""

    model_config = ConfigDict(frozen=True)

    trough_at: datetime
    drawdown: float


class TankGauge(BaseModel):
    model_config = ConfigDict(frozen=True)

    completed_fill_count: int
    litres_removed: int
    dose_per_tank: float
    uncertainty_fraction: float
    # Current open tank:
    fraction_full: float
    litres_so_far: float
    state: GaugeState
    cycles_remaining: int | None
    time_remaining_days: float | None
    next_full: datetime | None
    # Calibration-spread window around next_full, in days (uncertainty_fraction *
    # dose_per_tank / recent fill rate) - the "may be full" range for a near-full tank,
    # which does not collapse to zero the way time_remaining * u does. None when no recent rate.
    full_window_days: float | None


def estimate_tank_gauge(
    sensor_readings: Sequence[BasementReading],
    tank_full_events: Sequence[datetime],
) -> TankGauge | TankEstimateFailure:
    """Moisture-drawdown fuel gauge for the current open tank.

    Calibrated from the owner-logged `tank_full_events` (not RH-rebound detection,
    which is unreliable in the dry regime). Tank-emptied times are still detected
    from the signal — cycling clearly resumes after a refill.
    """
    basement_readings = sorted(
        (
            reading
            for reading in sensor_readings
            if reading.location == "Basement" and reading.timestamp >= DEHUMIDIFIER_INSTALLED_AT
        ),
        key=lambda reading: reading.timestamp,
    )
    if not basement_readings:
        return TankEstimateFailure(
            reason="no basement readings at or after the dehumidifier installation"
        )
    full_events = sorted(tank_full_events)
    if not full_events:
        return TankEstimateFailure(reason="no logged tank-full events to calibrate from")

    timestamps = [reading.timestamp for reading in basement_readings]
    smoothed = smoothed_relative_humidity(basement_readings)
    cycles = drawdown_cycles(basement_readings, timestamps, smoothed)
    trough_times = [timestamps[index] for index in detect_trough_indices(smoothed)]

    emptied_events = [tank_emptied_after(event, trough_times) for event in full_events]
    interval_starts = [DEHUMIDIFIER_INSTALLED_AT, *emptied_events[:-1]]
    tank_doses = [
        drawdown_dose(cycles, start, full)
        for start, full in zip(interval_starts, full_events, strict=True)
    ]
    dose_per_tank = statistics.mean(tank_doses)
    if dose_per_tank <= 0:
        return TankEstimateFailure(reason="no extraction cycles across completed tanks")
    uncertainty_fraction = statistics.pstdev(tank_doses) / dose_per_tank

    latest_reading_at = timestamps[-1]
    open_dose = drawdown_dose(cycles, emptied_events[-1], latest_reading_at)
    fraction_full = open_dose / dose_per_tank
    remaining_dose = max(0.0, dose_per_tank - open_dose)

    recent_cycles = [
        cycle
        for cycle in cycles
        if latest_reading_at - timedelta(days=RECENT_WINDOW_DAYS)
        <= cycle.trough_at
        <= latest_reading_at
    ]

    cycles_remaining: int | None = None
    time_remaining_days: float | None = None
    next_full: datetime | None = None
    full_window_days: float | None = None
    if not recent_cycles:
        state: GaugeState = "not_running"
    else:
        recent_rate = sum(cycle.drawdown for cycle in recent_cycles) / RECENT_WINDOW_DAYS
        recent_drawdown_per_cycle = statistics.median(cycle.drawdown for cycle in recent_cycles)
        if recent_rate > 0:
            time_remaining_days = remaining_dose / recent_rate
            next_full = latest_reading_at + timedelta(days=time_remaining_days)
            full_window_days = uncertainty_fraction * dose_per_tank / recent_rate
        if recent_drawdown_per_cycle > 0:
            cycles_remaining = round(remaining_dose / recent_drawdown_per_cycle)
        if (
            fraction_full >= FULL_FRACTION_THRESHOLD
            or next_full is None
            or next_full < latest_reading_at
        ):
            state = "full_or_overdue"
        else:
            state = "filling"

    return TankGauge(
        completed_fill_count=len(full_events),
        litres_removed=len(full_events) * TANK_CAPACITY_LITRES,
        dose_per_tank=dose_per_tank,
        uncertainty_fraction=uncertainty_fraction,
        fraction_full=fraction_full,
        litres_so_far=TANK_CAPACITY_LITRES * fraction_full,
        state=state,
        cycles_remaining=cycles_remaining,
        time_remaining_days=time_remaining_days,
        next_full=next_full,
        full_window_days=full_window_days,
    )


def drawdown_cycles(
    readings: Sequence[BasementReading],
    timestamps: Sequence[datetime],
    smoothed: Sequence[float],
) -> list[DrawdownCycle]:
    """One DrawdownCycle per trough that has a preceding peak within 120 minutes.

    Drawdown is the absolute-humidity drop from that peak to the trough, clamped
    at zero — the physical moisture quantity, least sensitive to sensor placement.
    """
    trough_indices = detect_trough_indices(smoothed)
    peak_indices = detect_peak_indices(smoothed)
    absolute_humidity = [reading.absolute_humidity_g_m3 for reading in readings]
    cycles: list[DrawdownCycle] = []
    for trough_index in trough_indices:
        peak_index = preceding_peak_index(trough_index, peak_indices, timestamps)
        if peak_index is None:
            continue
        drawdown = max(0.0, absolute_humidity[peak_index] - absolute_humidity[trough_index])
        cycles.append(DrawdownCycle(trough_at=timestamps[trough_index], drawdown=drawdown))
    return cycles


def preceding_peak_index(
    trough_index: int, peak_indices: Sequence[int], timestamps: Sequence[datetime]
) -> int | None:
    """The last peak within 120 minutes before the trough, or None."""
    window = timedelta(minutes=PRECEDING_PEAK_MINUTES)
    trough_time = timestamps[trough_index]
    preceding = [
        peak_index
        for peak_index in peak_indices
        if peak_index < trough_index and trough_time - timestamps[peak_index] <= window
    ]
    return preceding[-1] if preceding else None


def drawdown_dose(cycles: Sequence[DrawdownCycle], start: datetime, end: datetime) -> float:
    """Sum of per-cycle drawdowns for troughs falling within [start, end]."""
    return sum(cycle.drawdown for cycle in cycles if start <= cycle.trough_at <= end)


def half_day_words(days: float) -> str:
    """Render a day count in words rounded to the nearest half day, floored at half a day."""
    return uncertainty_words(max(0.5, round(days * 2) / 2))


def gauge_footer_text(gauge: TankGauge) -> str:
    """The site footer paragraph for a fuel-gauge estimate (issue 02, wording confirmed
    with the owner 2026-08-08 and pinned in the issue). One state sentence after the lead.

    Number formatting: percent and litres to the nearest whole; times in the dataset's
    local-time frame as weekday + day + abbreviated month + 24-hour clock; day ranges in
    words rounded to the nearest half day (reusing ``uncertainty_words``).
    """
    lead = (
        f"The dehumidifier has filled {gauge.completed_fill_count} times so far, "
        f"removing {gauge.litres_removed} litres of water."
    )
    if gauge.state == "not_running":
        return f"{lead} The dehumidifier is not running as of the latest data."

    if gauge.state == "full_or_overdue":
        assert gauge.next_full is not None and gauge.full_window_days is not None
        window = timedelta(days=gauge.full_window_days)
        earliest = format_footer_datetime(gauge.next_full - window)
        latest = format_footer_datetime(gauge.next_full + window)
        return (
            f"{lead} The current tank is estimated to be full — "
            f"likely between {earliest} and {latest}."
        )

    # filling
    assert (
        gauge.cycles_remaining is not None
        and gauge.time_remaining_days is not None
        and gauge.next_full is not None
    )
    percent = round(gauge.fraction_full * 100)
    litres = round(gauge.litres_so_far)
    plus_minus = half_day_words(gauge.time_remaining_days * gauge.uncertainty_fraction)
    return (
        f"{lead} The current tank is about {percent}% full (~{litres} of "
        f"{TANK_CAPACITY_LITRES} litres) — roughly {gauge.cycles_remaining} cycles left, "
        f"likely full {format_footer_datetime(gauge.next_full)} ± {plus_minus}."
    )


def tank_emptied_after(full_event: datetime, trough_times: Sequence[datetime]) -> datetime:
    """Detected tank-emptied time: the first trough at least 30 minutes after the
    tank-full event with cycling clearly resumed (≥ 3 troughs within the next 180
    minutes). Falls back to the tank-full event plus 6 hours if none qualifies."""
    resume_window = timedelta(minutes=RESUME_WINDOW_MINUTES)
    for candidate in trough_times:
        if candidate <= full_event + timedelta(minutes=RESUME_MINIMUM_DELAY_MINUTES):
            continue
        resumed = sum(
            1 for other in trough_times if candidate <= other <= candidate + resume_window
        )
        if resumed >= RESUME_MINIMUM_TROUGHS:
            return candidate
    return full_event + timedelta(hours=RESUME_FALLBACK_HOURS)
