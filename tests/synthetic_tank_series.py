"""Synthetic 1-minute basement RH fixtures for tank-estimator and render tests.

Segment slopes are symmetric around every trough so that the estimator's median
smoothing keeps trough centres on their nominal minutes, letting tests derive
expected event timestamps from the construction alone.
"""

from __future__ import annotations

from datetime import datetime, timedelta

from basement_analysis.summaries import SensorReading, absolute_humidity_g_m3
from basement_analysis.tank_estimator import DEHUMIDIFIER_INSTALLED_AT

CYCLE_PERIOD_MINUTES = 40
TROUGH_RH = 60.0
PEAK_RH = 64.0
EPISODE_RH = 70.0
EPISODE_RAMP_MINUTES = 50


def basement_reading(timestamp: datetime, relative_humidity_pct: float) -> SensorReading:
    return SensorReading(
        timestamp=timestamp,
        location="Basement",
        temperature_c=19.0,
        relative_humidity_pct=relative_humidity_pct,
        absolute_humidity_g_m3=absolute_humidity_g_m3(19.0, relative_humidity_pct),
    )


def cycling_rh(minute_in_cycle: int) -> float:
    """Triangle wave with a trough at minute 0 and a peak mid-cycle."""
    half_period = CYCLE_PERIOD_MINUTES / 2
    return PEAK_RH - (PEAK_RH - TROUGH_RH) * abs(minute_in_cycle - half_period) / half_period


def episode_rh(minute_in_episode: int, hold_minutes: int) -> float:
    """Symmetric ramp up to the episode plateau and back down to the next trough.

    The ramps share the cycling slope (0.2 RH points per minute) so that median
    smoothing keeps the bounding troughs centred on their nominal minutes.
    """
    slope = (PEAK_RH - TROUGH_RH) / (CYCLE_PERIOD_MINUTES / 2)
    if minute_in_episode <= EPISODE_RAMP_MINUTES:
        return TROUGH_RH + slope * minute_in_episode
    if minute_in_episode <= EPISODE_RAMP_MINUTES + hold_minutes:
        return EPISODE_RH
    return EPISODE_RH - slope * (minute_in_episode - EPISODE_RAMP_MINUTES - hold_minutes)


def episode_gap_minutes(hold_minutes: int) -> int:
    """Trough-to-trough gap of an episode segment."""
    return 2 * EPISODE_RAMP_MINUTES + hold_minutes


def synthetic_series(segments: list[tuple[str, int]]) -> list[SensorReading]:
    """Build a 1-minute basement RH series starting at the installation event.

    Segments: ("cycling", n_cycles) appends n_cycles extraction cycles with
    troughs at segment minutes 0, 40, 80, ...; ("episode", hold_minutes)
    appends a tank-full episode whose bounding troughs are the segment's first
    minute and the first minute of the following segment; ("open_episode",
    hold_minutes) appends an episode still in progress at the end of the data —
    it ramps up and holds but never ramps back down to a tank-emptied trough.
    """
    readings: list[SensorReading] = []
    minute = 0
    for kind, parameter in segments:
        if kind == "cycling":
            duration = parameter * CYCLE_PERIOD_MINUTES
            values = [cycling_rh(m % CYCLE_PERIOD_MINUTES) for m in range(duration)]
        elif kind == "open_episode":
            duration = EPISODE_RAMP_MINUTES + parameter
            values = [episode_rh(m, parameter) for m in range(duration)]
        else:
            duration = episode_gap_minutes(parameter)
            values = [episode_rh(m, parameter) for m in range(duration)]
        for offset, rh in enumerate(values):
            readings.append(
                basement_reading(DEHUMIDIFIER_INSTALLED_AT + timedelta(minutes=minute + offset), rh)
            )
        minute += duration
    return readings


def minutes_after_install(minutes: int) -> datetime:
    return DEHUMIDIFIER_INSTALLED_AT + timedelta(minutes=minutes)
