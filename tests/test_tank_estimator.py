from __future__ import annotations

from datetime import UTC, datetime, timedelta

from basement_analysis.summaries import SensorReading
from basement_analysis.tank_estimator import (
    TankEstimateFailure,
    TankGauge,
    TankHistory,
    displayed_uncertainty_days,
    gauge_footer_text,
    uncertainty_words,
)
from basement_analysis.tank_estimator import (
    estimate_tank_gauge as _estimate_tank_gauge,
)
from basement_analysis.tank_estimator import (
    estimate_tank_history as _estimate_tank_history,
)
from synthetic_tank_series import (
    CYCLE_PERIOD_MINUTES,
    DEHUMIDIFIER_INSTALLED_AT,
    TROUGH_RH,
    basement_reading,
    episode_gap_minutes,
    minutes_after_install,
    synthetic_series,
)


def estimate_tank_history(readings: list[SensorReading]) -> TankHistory | TankEstimateFailure:
    return _estimate_tank_history(readings, DEHUMIDIFIER_INSTALLED_AT)


def estimate_tank_gauge(
    readings: list[SensorReading], tank_full_events: tuple[datetime, ...] | list[datetime]
) -> TankGauge | TankEstimateFailure:
    return _estimate_tank_gauge(readings, tank_full_events, DEHUMIDIFIER_INSTALLED_AT)


def test_empty_input_reports_failure_instead_of_raising() -> None:
    result = estimate_tank_history([])

    assert isinstance(result, TankEstimateFailure)
    assert result.reason


def test_healthy_cycling_without_any_episode_reports_zero_complete_fill_intervals() -> None:
    readings = synthetic_series([("cycling", 72)])

    result = estimate_tank_history(readings)

    assert isinstance(result, TankEstimateFailure)
    assert "complete fill interval" in result.reason


def test_single_complete_episode_yields_events_totals_and_prediction_footer() -> None:
    # Fill for exactly 2 days (72 cycles), tank-full episode with a 740-minute
    # trough-to-trough gap, then resume cycling for 1 day.
    readings = synthetic_series([("cycling", 72), ("episode", 640), ("cycling", 36)])
    full_minute = 72 * CYCLE_PERIOD_MINUTES
    emptied_minute = full_minute + episode_gap_minutes(640)

    result = estimate_tank_history(readings)

    assert isinstance(result, TankHistory)
    assert result.tank_full_events == (minutes_after_install(full_minute),)
    assert result.tank_emptied_events == (minutes_after_install(emptied_minute),)
    assert len(result.complete_fill_intervals) == 1
    interval = result.complete_fill_intervals[0]
    assert interval.started_at == DEHUMIDIFIER_INSTALLED_AT
    assert interval.full_at == minutes_after_install(full_minute)
    # 73 nominal troughs including the undetectable one at the series edge.
    assert 71 <= interval.extraction_cycles <= 73
    assert result.completed_fill_count == 1
    assert result.litres_removed == 25
    assert result.state == "predicted_next_full"
    # Anchor: emptied 2026-07-04 09:20 local (BST) + mean fill duration of exactly 2 days, as a
    # canonical UTC instant (09:20 BST == 08:20 UTC).
    assert result.next_full_estimate == datetime(2026, 7, 6, 8, 20, tzinfo=UTC)
    assert result.footer_text == (
        "The dehumidifier has filled 1 times so far, removing 25 litres of water. "
        "Dehumidifier tank predicted next full Mon 6 Jul 09:20 ± half a day."
    )


def test_in_progress_episode_at_latest_reading_reports_not_running() -> None:
    # One completed fill, then a second episode that is still open at the end
    # of the data: a 350-minute gap since the last trough with RH above the
    # cycling band.
    readings = synthetic_series(
        [("cycling", 72), ("episode", 640), ("cycling", 36), ("open_episode", 300)]
    )

    result = estimate_tank_history(readings)

    assert isinstance(result, TankHistory)
    assert result.state == "not_running"
    assert result.next_full_estimate is None
    assert result.completed_fill_count == 1
    assert result.footer_text == (
        "The dehumidifier has filled 1 times so far, removing 25 litres of water. "
        "The dehumidifier is not running as of the latest data."
    )


def test_quick_empty_shortly_after_the_2_hour_threshold_is_detected() -> None:
    # A tank emptied promptly: the episode's trough-to-trough gap is 130
    # minutes, just past the 2-hour detection threshold.
    readings = synthetic_series([("cycling", 72), ("episode", 30), ("cycling", 36)])
    full_minute = 72 * CYCLE_PERIOD_MINUTES
    emptied_minute = full_minute + episode_gap_minutes(30)

    result = estimate_tank_history(readings)

    assert isinstance(result, TankHistory)
    assert result.tank_full_events == (minutes_after_install(full_minute),)
    assert result.tank_emptied_events == (minutes_after_install(emptied_minute),)
    assert result.completed_fill_count == 1


def test_two_fills_with_a_two_day_spread_predict_with_one_day_uncertainty() -> None:
    # Fills of exactly 2 days and 4 days: mean 3 days, half range exactly 1 day.
    readings = synthetic_series(
        [("cycling", 72), ("episode", 640), ("cycling", 144), ("episode", 640), ("cycling", 36)]
    )

    result = estimate_tank_history(readings)

    assert isinstance(result, TankHistory)
    assert result.completed_fill_count == 2
    assert result.litres_removed == 50
    # Second emptied event: install + 10120 minutes = Wed 8 Jul 21:40; + 3 days.
    assert result.footer_text == (
        "The dehumidifier has filled 2 times so far, removing 50 litres of water. "
        "Dehumidifier tank predicted next full Sat 11 Jul 21:40 ± 1 day."
    )


def test_displayed_uncertainty_rounds_to_nearest_half_day_with_a_half_day_floor() -> None:
    two_days = timedelta(days=2)

    assert displayed_uncertainty_days([two_days, two_days]) == 0.5
    assert displayed_uncertainty_days([two_days, timedelta(days=2, hours=26)]) == 0.5
    assert displayed_uncertainty_days([two_days, timedelta(days=4)]) == 1.0
    assert displayed_uncertainty_days([two_days, timedelta(days=4, hours=19, minutes=20)]) == 1.5


def test_uncertainty_renders_in_words_rounded_to_half_days() -> None:
    assert uncertainty_words(0.5) == "half a day"
    assert uncertainty_words(1.0) == "1 day"
    assert uncertainty_words(1.5) == "1½ days"
    assert uncertainty_words(2.0) == "2 days"
    assert uncertainty_words(2.5) == "2½ days"


def test_gap_shorter_than_2_hours_is_not_a_tank_full_episode() -> None:
    # 110-minute trough-to-trough gap with raised RH: below the 2-hour
    # threshold, indistinguishable from an ordinary between-cycle pause.
    readings = synthetic_series([("cycling", 72), ("episode", 10), ("cycling", 36)])

    result = estimate_tank_history(readings)

    assert isinstance(result, TankEstimateFailure)
    assert "complete fill interval" in result.reason


def test_current_fill_outlasting_the_estimate_reports_filling_longer_than_expected() -> None:
    # The only complete fill took 2 days; the current fill has been running
    # for 4 days at the latest reading, well past the estimate.
    readings = synthetic_series([("cycling", 72), ("episode", 640), ("cycling", 144)])

    result = estimate_tank_history(readings)

    assert isinstance(result, TankHistory)
    assert result.state == "filling_longer_than_expected"
    assert result.footer_text == (
        "The dehumidifier has filled 1 times so far, removing 25 litres of water. "
        "Dehumidifier tank has been filling longer than expected, it may be full at any time."
    )


def test_resumed_cycling_blip_shorter_than_8_hours_does_not_split_an_episode() -> None:
    # A 6-hour cycling blip (9 cycles) sits between two qualifying gaps: one
    # episode, bounded by the first gap's leading trough and the second gap's
    # trailing trough.
    readings = synthetic_series(
        [("cycling", 72), ("episode", 200), ("cycling", 9), ("episode", 300), ("cycling", 36)]
    )
    full_minute = 72 * CYCLE_PERIOD_MINUTES
    emptied_minute = (
        full_minute + episode_gap_minutes(200) + 9 * CYCLE_PERIOD_MINUTES + episode_gap_minutes(300)
    )

    result = estimate_tank_history(readings)

    assert isinstance(result, TankHistory)
    assert result.tank_full_events == (minutes_after_install(full_minute),)
    assert result.tank_emptied_events == (minutes_after_install(emptied_minute),)
    assert result.completed_fill_count == 1


# ---------------------------------------------------------------------------
# Moisture-drawdown fuel gauge (estimate_tank_gauge)
#
# The synthetic series is continuous 40-minute cycling with a constant per-cycle
# absolute-humidity drawdown, so each fill interval's dose is proportional to the
# extraction cycles it contains. Tank-full events are the *logged* timestamps we
# pass in; tank-emptied is detected from the resumed cycling. Two logged fills at
# minutes 2880 and 5760 give equal 72-cycle intervals — a flat calibration.
# ---------------------------------------------------------------------------

TWO_LOGGED_FILLS = (minutes_after_install(2880), minutes_after_install(5760))


def append_flat_readings(
    readings: list[SensorReading], from_minute: int, count: int, relative_humidity: float
) -> list[SensorReading]:
    """Append `count` cycle-free 1-minute readings — a stalled dehumidifier."""
    return readings + [
        basement_reading(minutes_after_install(from_minute + offset), relative_humidity)
        for offset in range(count)
    ]


def test_gauge_reports_failure_on_empty_readings() -> None:
    result = estimate_tank_gauge([], TWO_LOGGED_FILLS)

    assert isinstance(result, TankEstimateFailure)
    assert result.reason


def test_gauge_reports_failure_without_logged_events() -> None:
    readings = synthetic_series([("cycling", 72)])

    result = estimate_tank_gauge(readings, [])

    assert isinstance(result, TankEstimateFailure)
    assert "tank-full event" in result.reason


def test_gauge_calibrates_from_logged_events_even_without_an_rh_episode() -> None:
    # Continuous cycling: no tank-full RH rebound at all (the dry-regime case that
    # defeats episode detection). The gauge must still find two completed tanks,
    # calibrated purely from the logged events.
    readings = synthetic_series([("cycling", 190)])

    result = estimate_tank_gauge(readings, TWO_LOGGED_FILLS)
    signal_only = estimate_tank_history(readings)

    assert isinstance(result, TankGauge)
    assert result.completed_fill_count == 2
    assert result.litres_removed == 50
    # The equal 72-cycle intervals calibrate with negligible scatter.
    assert result.uncertainty_fraction < 0.05
    assert result.dose_per_tank > 0
    # ...and the old RH-rebound detector finds nothing to key on in the same signal.
    assert isinstance(signal_only, TankEstimateFailure)


def test_gauge_reports_a_mid_tank_fill_as_filling() -> None:
    # After the second logged fill (minute 5760) the open tank runs ~45 more
    # cycles by the end of the data — a little under two-thirds of a 72-cycle tank.
    readings = synthetic_series([("cycling", 190)])

    result = estimate_tank_gauge(readings, TWO_LOGGED_FILLS)

    assert isinstance(result, TankGauge)
    assert result.state == "filling"
    assert 0.55 <= result.fraction_full <= 0.70
    assert result.litres_so_far == 25 * result.fraction_full
    assert result.cycles_remaining is not None and 24 <= result.cycles_remaining <= 30
    assert result.time_remaining_days is not None and 0.4 < result.time_remaining_days < 1.5
    assert result.next_full is not None and result.next_full > readings[-1].timestamp


def test_gauge_reports_an_overfilled_open_tank_as_full_or_overdue() -> None:
    # The open tank runs far past one tank's worth of cycles by the end of data.
    readings = synthetic_series([("cycling", 300)])

    result = estimate_tank_gauge(readings, TWO_LOGGED_FILLS)

    assert isinstance(result, TankGauge)
    assert result.state == "full_or_overdue"
    assert result.fraction_full > 1.0


def test_gauge_reports_not_running_when_no_recent_cycles() -> None:
    # One logged fill, then the unit stalls: a cycle-free tail longer than the
    # 3-day recent window, so there is no recent rate to project.
    cycling = synthetic_series([("cycling", 144)])
    readings = append_flat_readings(
        cycling, from_minute=5760, count=5000, relative_humidity=TROUGH_RH
    )

    result = estimate_tank_gauge(readings, (minutes_after_install(2880),))

    assert isinstance(result, TankGauge)
    assert result.state == "not_running"
    assert result.completed_fill_count == 1
    assert result.cycles_remaining is None
    assert result.time_remaining_days is None
    assert result.next_full is None


# ---------------------------------------------------------------------------
# Fuel-gauge footer rendering (gauge_footer_text)
#
# Wording confirmed with the owner 2026-08-08 and pinned in issue 02. These test
# the renderer in isolation from the signal maths (already covered above), so the
# gauge fields — percent, litres, the full-window endpoints — are set directly.
# ---------------------------------------------------------------------------

FOOTER_LEAD = "The dehumidifier has filled 5 times so far, removing 125 litres of water."


def gauge_with(**overrides: object) -> TankGauge:
    fields: dict[str, object] = {
        "completed_fill_count": 5,
        "litres_removed": 125,
        "dose_per_tank": 135.0,
        "uncertainty_fraction": 0.206,
        "fraction_full": 0.34,
        "litres_so_far": 8.4,
        "state": "filling",
        "cycles_remaining": 126,
        "time_remaining_days": 7.7,
        "next_full": datetime(2026, 8, 11, 4, 32),
        "full_window_days": 1.0,
    }
    fields.update(overrides)
    return TankGauge(**fields)  # type: ignore[arg-type]


def test_footer_filling_renders_percent_litres_cycles_and_signed_range() -> None:
    # 0.34 -> 34%, 8.4 L -> 8, range = 7.7 d x 0.206 = 1.586 d -> 1.5 d -> "1½ days".
    assert gauge_footer_text(gauge_with()) == (
        f"{FOOTER_LEAD} The current tank is about 34% full (~8 of 25 litres) — "
        "roughly 126 cycles left, likely full Tue 11 Aug 04:32 ± 1½ days."
    )


def test_footer_percent_and_litres_round_to_the_nearest_whole() -> None:
    footer = gauge_footer_text(gauge_with(fraction_full=0.129, litres_so_far=3.2))

    assert "about 13% full (~3 of 25 litres)" in footer


def test_footer_full_or_overdue_renders_the_calibration_window() -> None:
    footer = gauge_footer_text(
        gauge_with(
            state="full_or_overdue",
            fraction_full=0.999,
            next_full=datetime(2026, 8, 7, 0, 0),
            full_window_days=1.0,
        )
    )

    assert footer == (
        f"{FOOTER_LEAD} The current tank is estimated to be full — "
        "likely between Thu 6 Aug 00:00 and Sat 8 Aug 00:00."
    )


def test_footer_not_running_is_a_single_flat_sentence() -> None:
    footer = gauge_footer_text(
        gauge_with(
            state="not_running",
            cycles_remaining=None,
            time_remaining_days=None,
            next_full=None,
            full_window_days=None,
        )
    )

    assert footer == f"{FOOTER_LEAD} The dehumidifier is not running as of the latest data."


def test_footer_filling_range_floors_at_half_a_day() -> None:
    # A tiny time-remaining still renders a half-day range, never "0 days".
    footer = gauge_footer_text(gauge_with(time_remaining_days=0.1))

    assert footer.endswith("± half a day.")
