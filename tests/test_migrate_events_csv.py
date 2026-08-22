from __future__ import annotations

import sys
import uuid
from collections.abc import Callable
from datetime import UTC, datetime
from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path
from types import ModuleType

import pytest

from basement_analysis.event_store import EventType, Operation


def load_migration_script() -> ModuleType:
    script_path = Path(__file__).parents[1] / "scripts" / "migrate_events_csv.py"
    spec = spec_from_file_location("migrate_events_csv", script_path)
    assert spec is not None and spec.loader is not None
    module = module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


MIGRATION = load_migration_script()
INSTALLED_TEXT = MIGRATION.INSTALLED_TEXT
TANK_FULL_TEXT = MIGRATION.TANK_FULL_TEXT
build_migration_records = MIGRATION.build_migration_records
load_legacy_events = MIGRATION.load_legacy_events
verify_migration_records = MIGRATION.verify_migration_records

RECORDED_AT = datetime(2026, 8, 22, 12, 34, 56, tzinfo=UTC)
LEGACY_CSV = (
    "\n".join(
        (
            "Time,Event",
            "2026/06/28 12:40,began clearing out basement",
            "2026/06/28 16:20,removed carpet and underlay and carpet grippers "
            "leaving the room bare then re-added a couple of boxes and a few other things",
            "2026/07/01 21:00,dehumidifier installed in centre of room and extractor fan "
            "turned off set to 50% RH",
            "2026/07/02 14:35,added a small fan to introduce airflow pointing at the wall "
            "with the radiator",
            "2026/07/02 14:40,moved the temperature humidity sensor from the wall with the "
            "radiator to a box near the extractor fan",
            "2026/07/02 18:30,(uncertain timestamp) dehumidifier rotated in place so that "
            "the intake faces away from the wetter side of the room and box moved which may "
            "have affected airflow",
            "2026/07/02 21:00,(uncertain timestamp) dehumidifier rotated in place so that "
            "the intake faces the wetter side of the room",
            "2026/07/05 00:51:03,dehumidifer tank full",
            "2026/07/11 01:46:29,dehumidifer tank full",
            "2026/07/15 07:31:16,dehumidifer tank full",
            "2026/07/23 21:42:08,dehumidifer tank full",
            "2026/07/29 15:39:48,dehumidifer tank full",
        )
    )
    + "\n"
)


def uuid7_factory() -> Callable[[], uuid.UUID]:
    values = iter(uuid.UUID(int=(index << 80) | (7 << 76) | (2 << 62)) for index in range(1, 25))
    return lambda: next(values)


def legacy_csv_path(tmp_path: Path) -> Path:
    csv_path = tmp_path / "basement_events.csv"
    csv_path.write_text(LEGACY_CSV, encoding="utf-8")
    return csv_path


def test_migration_maps_all_legacy_rows_exactly(tmp_path: Path) -> None:
    events = load_legacy_events(legacy_csv_path(tmp_path))
    records = build_migration_records(events, recorded_at=RECORDED_AT, new_id=uuid7_factory())

    assert len(records) == 12
    assert all(record.operation == Operation.create for record in records)
    assert all(record.recorded_at == RECORDED_AT for record in records)
    assert all(
        record.source.model_dump(exclude_none=True) == {"workflow": "csv-migration"}
        for record in records
    )

    tank_records = [
        record for record in records if record.event_type == EventType.dehumidifier_tank_full
    ]
    assert len(tank_records) == 5
    assert all(record.data.notes is None for record in tank_records)

    installed = [
        record for record in records if record.event_type == EventType.dehumidifier_installed
    ]
    assert len(installed) == 1
    assert installed[0].effective_at == datetime(2026, 7, 1, 20, 0, tzinfo=UTC)
    assert installed[0].data.notes == INSTALLED_TEXT

    custom = [record for record in records if record.event_type == EventType.custom]
    assert len(custom) == 6
    expected_custom_notes = {
        event.description
        for event in events
        if event.description not in {TANK_FULL_TEXT, INSTALLED_TEXT}
    }
    assert {record.data.notes for record in custom} == expected_custom_notes
    assert records[0].effective_at == datetime(2026, 6, 28, 11, 40, tzinfo=UTC)
    assert records[-1].effective_at == datetime(2026, 7, 29, 14, 39, 48, tzinfo=UTC)
    assert verify_migration_records(records, events) == RECORDED_AT


def test_verification_rejects_partial_prior_migration(tmp_path: Path) -> None:
    events = load_legacy_events(legacy_csv_path(tmp_path))
    records = build_migration_records(events, recorded_at=RECORDED_AT, new_id=uuid7_factory())

    with pytest.raises(ValueError, match="Expected 12 csv-migration records, found 11"):
        verify_migration_records(records[:-1], events)
