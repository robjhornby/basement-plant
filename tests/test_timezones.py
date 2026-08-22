from __future__ import annotations

from datetime import UTC, datetime

import pytest

from basement_analysis.timezones import (
    london_wall_clock_to_utc,
    utc_to_london_wall_clock,
)


def test_gmt_winter_wall_clock_converts_without_offset() -> None:
    # Mid-January is GMT (== UTC), so the wall clock and the UTC instant coincide.
    assert london_wall_clock_to_utc(datetime(2026, 1, 15, 12, 0)) == datetime(
        2026, 1, 15, 12, 0, tzinfo=UTC
    )


def test_bst_summer_wall_clock_shifts_back_one_hour() -> None:
    # Mid-July is BST (UTC+1), so 12:00 local is 11:00 UTC.
    assert london_wall_clock_to_utc(datetime(2026, 7, 15, 12, 0)) == datetime(
        2026, 7, 15, 11, 0, tzinfo=UTC
    )


def test_autumn_fall_back_ambiguous_hour_resolves_to_the_bst_occurrence() -> None:
    # 2026-10-25 01:30 occurs twice in Europe/London: first 01:30 BST (00:30 UTC), then after the
    # clocks go back, 01:30 GMT (01:30 UTC). The documented fold=0 policy picks the first (BST)
    # occurrence, so the canonical instant is 00:30 UTC.
    ambiguous = datetime(2026, 10, 25, 1, 30)

    assert london_wall_clock_to_utc(ambiguous) == datetime(2026, 10, 25, 0, 30, tzinfo=UTC)
    # The GMT (second) occurrence would have been 01:30 UTC — confirm fold=0 did not pick it.
    assert london_wall_clock_to_utc(ambiguous) != datetime(2026, 10, 25, 1, 30, tzinfo=UTC)


def test_aware_input_is_rejected() -> None:
    with pytest.raises(ValueError, match="naive"):
        london_wall_clock_to_utc(datetime(2026, 7, 15, 12, 0, tzinfo=UTC))


def test_utc_to_london_wall_clock_round_trips_a_bst_instant() -> None:
    # Presentation inverse: a UTC instant renders back to the local wall clock it came from.
    utc_instant = datetime(2026, 7, 15, 11, 0, tzinfo=UTC)
    assert utc_to_london_wall_clock(utc_instant) == datetime(2026, 7, 15, 12, 0)


def test_utc_to_london_wall_clock_passes_naive_through_unchanged() -> None:
    # A naive value is assumed already-local (legacy fixtures) and is returned unchanged.
    naive_local = datetime(2026, 7, 15, 12, 0)
    assert utc_to_london_wall_clock(naive_local) == naive_local
