"""Event store: reproducible write-path snapshots + DuckDB read-path derivation.

The snapshot corpus is committed under ``tests/data/event_store/year=YYYY/<revision_id>.json``
(a semantically named location, not pytest-snapshot's default dir). Both this test and the
throwaway generator build it from :func:`build_snapshot_records`, so the emitted JSON is
byte-identical across runs given the frozen clock and fixed id factory below.
"""

from __future__ import annotations

import uuid
from collections.abc import Callable, Iterable
from datetime import UTC, datetime
from pathlib import Path

import pytest
from pydantic import ValidationError

from basement_analysis import event_store as event_store_module
from basement_analysis.event_store import (
    EventRecord,
    EventSource,
    EventType,
    Operation,
    build_create_record,
    build_delete_record,
    build_update_record,
    connect_event_store,
    current_events,
    deleted_events,
    event_history,
    full_history,
    local_events_glob,
    object_key,
    parse_event_effective_at,
    serialize_record,
    write_record,
)

CORPUS_DIR = Path(__file__).parent / "data" / "event_store"

# A frozen clock (all mutations recorded at one instant; revision-id UUIDv7 order breaks ties)
# plus a fixed, pre-sorted UUIDv7 sequence make the write path emit byte-identical JSON.
FROZEN_RECORDED_AT = datetime(2026, 8, 22, 10, 15, 32, tzinfo=UTC)

FIXED_IDS: tuple[str, ...] = (
    "01a0298f-83c8-7321-8efc-10e1d95c915e",  # 0: event A
    "01a0298f-83c8-7321-8efc-10e2f4f8a774",  # 1: A create revision
    "01a0298f-83c8-7321-8efc-10e33889b3c7",  # 2: A update revision
    "01a0298f-83c8-7321-8efc-10e404b26c0f",  # 3: event B
    "01a0298f-83c8-7321-8efc-10e5bdb16656",  # 4: B create revision
    "01a0298f-83c8-7321-8efc-10e6cb818793",  # 5: event C
    "01a0298f-83c8-7321-8efc-10e75f75f9c1",  # 6: C create revision
    "01a0298f-83c8-7321-8efc-10e86bde1f15",  # 7: C delete revision
)

UPDATED_A_NOTES = "Damp patch near the north wall (corrected: also behind the boiler)"

EVENT_A_ID = uuid.UUID(FIXED_IDS[0])
EVENT_B_ID = uuid.UUID(FIXED_IDS[3])
EVENT_C_ID = uuid.UUID(FIXED_IDS[5])


def frozen_clock() -> datetime:
    return FROZEN_RECORDED_AT


def fixed_id_factory() -> Callable[[], uuid.UUID]:
    """A UUIDv7 generator that hands out FIXED_IDS in order (deterministic across runs)."""
    ids = iter(uuid.UUID(value) for value in FIXED_IDS)

    def factory() -> uuid.UUID:
        return next(ids)

    return factory


def build_snapshot_records() -> list[tuple[EventRecord, int | None]]:
    """The corpus, as ``(record, delete_effective_year)`` pairs, built in id-consumption order.

    Event A (custom): create -> update. Event B (tank full): create. Event C (installed): create
    -> delete. Exercises current state (A latest update, B), a tombstone (C), multi-revision
    history (A), and two year partitions (2026, 2027).
    """
    new_id = fixed_id_factory()
    source = EventSource(workflow="pytest-snapshot")

    a_create = build_create_record(
        event_type=EventType.custom,
        effective_at=parse_event_effective_at("2026-07-05 00:51:03"),
        notes="Noticed damp patch near the north wall",
        source=source,
        now=frozen_clock,
        new_id=new_id,
    )
    a_update = build_update_record(
        event_id=EVENT_A_ID,
        event_type=EventType.custom,
        effective_at=parse_event_effective_at("2026-07-05 00:51:03"),
        notes=UPDATED_A_NOTES,
        source=source,
        now=frozen_clock,
        new_id=new_id,
    )
    b_create = build_create_record(
        event_type=EventType.dehumidifier_tank_full,
        effective_at=parse_event_effective_at("2026-08-15 09:00:00"),
        source=source,
        now=frozen_clock,
        new_id=new_id,
    )
    c_create = build_create_record(
        event_type=EventType.dehumidifier_installed,
        effective_at=parse_event_effective_at("2027-02-10 12:00:00"),
        source=source,
        now=frozen_clock,
        new_id=new_id,
    )
    c_delete = build_delete_record(
        event_id=EVENT_C_ID,
        event_type=EventType.dehumidifier_installed,
        source=source,
        now=frozen_clock,
        new_id=new_id,
    )
    return [
        (a_create, None),
        (a_update, None),
        (b_create, None),
        (c_create, None),
        (c_delete, 2027),  # tombstone colocated with event C's 2027 partition
    ]


def corpus_path_for(record: EventRecord, effective_year: int | None) -> Path:
    # The committed corpus drops the `events/` prefix for a semantic on-disk location.
    key = object_key(record, effective_year=effective_year).removeprefix("events/")
    return CORPUS_DIR / key


# --- Write-path snapshot test ------------------------------------------------------------------


def test_write_path_matches_committed_snapshot_corpus() -> None:
    for record, effective_year in build_snapshot_records():
        expected_path = corpus_path_for(record, effective_year)
        assert expected_path.exists(), f"missing committed snapshot: {expected_path}"
        assert serialize_record(record) == expected_path.read_text(encoding="utf-8")


def test_write_record_emits_bytes_identical_to_corpus(tmp_path: Path) -> None:
    for record, effective_year in build_snapshot_records():
        key = write_record(record, tmp_path, effective_year=effective_year)
        written = (tmp_path / key).read_text(encoding="utf-8")
        expected = corpus_path_for(record, effective_year).read_text(encoding="utf-8")
        assert written == expected


def test_object_key_uses_effective_at_year_and_delete_fallback() -> None:
    a_create, _ = build_snapshot_records()[0]
    assert object_key(a_create) == f"events/year=2026/{a_create.revision_id}.json"

    c_delete, year = build_snapshot_records()[4]
    assert (
        object_key(c_delete, effective_year=year)
        == f"events/year=2027/{c_delete.revision_id}.json"
    )
    # Without a supplied year, a tombstone falls back to its recorded_at (2026) partition.
    assert object_key(c_delete) == f"events/year=2026/{c_delete.revision_id}.json"


# --- Read-path (DuckDB) test -------------------------------------------------------------------


@pytest.fixture
def read_glob() -> str:
    return local_events_glob(CORPUS_DIR)


def test_current_events_excludes_tombstoned_and_keeps_latest_revision(read_glob: str) -> None:
    connection = connect_event_store(read_glob)
    try:
        current = current_events(connection, read_glob)
    finally:
        connection.close()

    # Event A's latest (update) and event B remain; event C is tombstoned and excluded.
    assert [record.event_id for record in current] == [EVENT_A_ID, EVENT_B_ID]
    a_current = current[0]
    assert a_current.operation == Operation.update
    assert a_current.data.notes == UPDATED_A_NOTES


def test_current_events_validates_duckdb_rows_without_reopening_paths(
    read_glob: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    def fail_if_reopened(_paths: Iterable[Path | str]) -> list[EventRecord]:
        raise AssertionError("selected object paths must not be reopened outside DuckDB")

    monkeypatch.setattr(event_store_module, "load_records", fail_if_reopened)
    connection = connect_event_store(read_glob)
    try:
        assert len(current_events(connection, read_glob)) == 2
    finally:
        connection.close()


def test_event_history_returns_every_revision_oldest_first(read_glob: str) -> None:
    connection = connect_event_store(read_glob)
    try:
        history = event_history(connection, read_glob, EVENT_A_ID)
        everything = full_history(connection, read_glob)
    finally:
        connection.close()

    assert [record.operation for record in history] == [Operation.create, Operation.update]
    assert {record.event_id for record in history} == {EVENT_A_ID}
    assert len(everything) == 5


def test_deleted_events_returns_tombstones(read_glob: str) -> None:
    connection = connect_event_store(read_glob)
    try:
        deleted = deleted_events(connection, read_glob)
    finally:
        connection.close()

    assert [record.event_id for record in deleted] == [EVENT_C_ID]
    assert deleted[0].operation == Operation.delete
    assert deleted[0].effective_at is None


# --- Model round-trip + validation -------------------------------------------------------------


def test_event_record_round_trips_losslessly() -> None:
    record = build_create_record(
        event_type=EventType.dehumidifier_tank_emptied,
        effective_at=parse_event_effective_at("2026-08-15 09:00:00"),
        notes="emptied 3.2 L",
        source=EventSource(
            repository="owner/repo", workflow="log-event", run_id="123", git_sha="abc"
        ),
        now=frozen_clock,
        new_id=fixed_id_factory(),
    )
    parsed = EventRecord.model_validate_json(serialize_record(record))
    assert parsed == record


def test_effective_at_parsing_interprets_input_as_london_and_stores_utc() -> None:
    # 2026-07-05 00:51:03 BST -> 2026-07-04T23:51:03Z (Appendix B worked example).
    assert parse_event_effective_at("2026-07-05 00:51:03") == datetime(
        2026, 7, 4, 23, 51, 3, tzinfo=UTC
    )


def test_effective_at_parsing_requires_seconds() -> None:
    with pytest.raises(ValueError, match=r"does not match format|unconverted"):
        parse_event_effective_at("2026-07-05 00:51")


def test_validation_rejects_unknown_event_type() -> None:
    with pytest.raises(ValidationError):
        EventRecord.model_validate(
            {
                "event_id": FIXED_IDS[0],
                "revision_id": FIXED_IDS[1],
                "operation": "create",
                "recorded_at": "2026-08-22T10:15:32Z",
                "effective_at": "2026-07-04T23:51:03Z",
                "event_type": "not_a_real_type",
                "data": {"notes": "x"},
            }
        )


def test_validation_rejects_custom_without_notes() -> None:
    with pytest.raises(ValidationError, match="custom events require non-empty notes"):
        build_create_record(
            event_type=EventType.custom,
            effective_at=parse_event_effective_at("2026-07-05 00:51:03"),
            notes="   ",
            now=frozen_clock,
            new_id=fixed_id_factory(),
        )


def test_validation_rejects_naive_canonical_timestamp() -> None:
    with pytest.raises(ValidationError, match="UTC instants"):
        EventRecord(
            event_id=EVENT_A_ID,
            revision_id=EVENT_B_ID,
            operation=Operation.create,
            recorded_at=datetime(2026, 8, 22, 10, 15, 32),  # naive
            effective_at=datetime(2026, 7, 4, 23, 51, 3, tzinfo=UTC),
            event_type=EventType.dehumidifier_tank_full,
        )


def test_validation_rejects_non_utc_canonical_timestamp() -> None:
    from datetime import timedelta, timezone

    with pytest.raises(ValidationError, match="UTC instants"):
        EventRecord(
            event_id=EVENT_A_ID,
            revision_id=EVENT_B_ID,
            operation=Operation.create,
            recorded_at=FROZEN_RECORDED_AT,
            effective_at=datetime(2026, 7, 5, 0, 51, 3, tzinfo=timezone(timedelta(hours=1))),
            event_type=EventType.dehumidifier_tank_full,
        )
