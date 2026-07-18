from __future__ import annotations

from datetime import datetime, timedelta

from basement_analysis.tank_estimator import (
    DEHUMIDIFIER_INSTALLED_AT,
    TankEstimateFailure,
    TankHistory,
    displayed_uncertainty_days,
    estimate_tank_history,
    uncertainty_words,
)
from synthetic_tank_series import (
    CYCLE_PERIOD_MINUTES,
    episode_gap_minutes,
    minutes_after_install,
    synthetic_series,
)


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
    # Anchor: emptied 2026-07-04 09:20 + mean fill duration of exactly 2 days.
    assert result.next_full_estimate == datetime(2026, 7, 6, 9, 20)
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
        full_minute
        + episode_gap_minutes(200)
        + 9 * CYCLE_PERIOD_MINUTES
        + episode_gap_minutes(300)
    )

    result = estimate_tank_history(readings)

    assert isinstance(result, TankHistory)
    assert result.tank_full_events == (minutes_after_install(full_minute),)
    assert result.tank_emptied_events == (minutes_after_install(emptied_minute),)
    assert result.completed_fill_count == 1
