"""Timezone boundary helpers.

The pipeline keeps a single canonical timeline: **UTC instants**. ``Europe/London``
is an *ingestion* concern (interpreting naive wall-clock source data) and a
*presentation* concern (rendering an instant as a human-readable local time), and
nothing in between. This module is the one place the ``Europe/London`` IANA zone is
interpreted, so callers never hardcode a ``+00:00``/``+01:00`` offset and the
timezone database decides GMT vs BST per date.

Ticket 03 (event input parsing) reuses :func:`london_wall_clock_to_utc` — keep it
cleanly importable.
"""

from __future__ import annotations

from datetime import UTC, datetime
from zoneinfo import ZoneInfo

# `UTC` is re-exported from this module (imported above) so the whole pipeline draws the
# canonical zone from one place. The IANA `Europe/London` name is hardcoded (never a fixed
# offset) so the tz database resolves GMT vs BST from the date.
LONDON = ZoneInfo("Europe/London")

__all__ = ["LONDON", "UTC", "london_wall_clock_to_utc", "utc_to_london_wall_clock"]


def london_wall_clock_to_utc(value: datetime) -> datetime:
    """Interpret a naive ``Europe/London`` wall-clock datetime as a canonical UTC instant.

    Source timestamps (X-Sense sensor CSVs, Open-Meteo hourly weather, manually entered
    events) carry no offset; this system documents them as ``Europe/London`` wall-clock
    values and converts them to UTC here at the ingestion boundary.

    DST fall-back policy: **``fold=0``** — the *first* (BST) occurrence of an ambiguous
    autumn wall-clock time. During the autumn transition a local time such as
    ``2026-10-25 01:30`` occurs twice (01:30 BST, then 01:30 GMT); the source format
    discards the information needed to tell them apart, so we pick the earlier (BST)
    instant deterministically. This is a documented, tested choice, not a silent library
    default, and can be revisited if better information about export behaviour appears.

    Raises ``ValueError`` if ``value`` is timezone-aware — the input contract is a naive
    wall-clock datetime.
    """
    if value.tzinfo is not None:
        raise ValueError("Expected naive Europe/London wall-clock datetime")
    local = value.replace(tzinfo=LONDON, fold=0)
    return local.astimezone(UTC)


def utc_to_london_wall_clock(value: datetime) -> datetime:
    """Presentation boundary: render a canonical UTC instant in ``Europe/London`` local time.

    Returns a *naive* datetime carrying the local wall-clock the viewer expects, ready for
    ``strftime``. A naive input is assumed to already be local wall-clock (the legacy
    representation used by unit-test fixtures and any not-yet-migrated call site) and is
    returned unchanged, so the local time rendered is stable across the migration.
    """
    if value.tzinfo is None:
        return value
    return value.astimezone(LONDON).replace(tzinfo=None)
