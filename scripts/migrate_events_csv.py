#!/usr/bin/env python3
"""One-off, duplicate-safe migration of ``data/basement_events.csv`` to R2.

The event store is append-only, so this script always downloads and validates any
existing ``csv-migration`` records before it writes.  A complete prior migration is
a verified no-op; a partial or mismatched migration stops for manual investigation.
"""

from __future__ import annotations

import argparse
import csv
import os
import shutil
import subprocess
import tempfile
import uuid
from collections import Counter
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

from basement_analysis.event_store import (
    EventRecord,
    EventSource,
    EventType,
    build_create_record,
    write_record,
)
from basement_analysis.timezones import london_wall_clock_to_utc

REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_CSV_PATH = REPO_ROOT / "data" / "basement_events.csv"
EXPECTED_EVENT_COUNT = 12
MIGRATION_WORKFLOW = "csv-migration"
TANK_FULL_TEXT = "dehumidifer tank full"
INSTALLED_TEXT = (
    "dehumidifier installed in centre of room and extractor fan turned off set to 50% RH"
)
CSV_TIME_FORMATS = ("%Y/%m/%d %H:%M:%S", "%Y/%m/%d %H:%M")
MigrationSignature = tuple[datetime | None, EventType, str]
REQUIRED_R2_ENV = (
    "R2_ENDPOINT_URL",
    "R2_ACCESS_KEY_ID",
    "R2_SECRET_ACCESS_KEY",
    "R2_BUCKET",
)


@dataclass(frozen=True)
class LegacyEvent:
    effective_at: datetime
    description: str


def load_legacy_events(csv_path: Path) -> list[LegacyEvent]:
    """Load and validate the fixed legacy corpus, preserving descriptions verbatim."""
    with csv_path.open(newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        if reader.fieldnames != ["Time", "Event"]:
            raise ValueError(f"Expected CSV columns Time,Event; got {reader.fieldnames!r}")
        events = [
            LegacyEvent(
                effective_at=london_wall_clock_to_utc(_parse_csv_time(row["Time"])),
                description=row["Event"],
            )
            for row in reader
        ]
    if len(events) != EXPECTED_EVENT_COUNT:
        raise ValueError(
            f"Expected {EXPECTED_EVENT_COUNT} legacy events, found {len(events)} in {csv_path}"
        )
    return events


def _parse_csv_time(value: str) -> datetime:
    for time_format in CSV_TIME_FORMATS:
        try:
            return datetime.strptime(value, time_format)
        except ValueError:
            pass
    raise ValueError(f"Unsupported legacy event timestamp: {value!r}")


def _event_type_and_notes(description: str) -> tuple[EventType, str]:
    if description == TANK_FULL_TEXT:
        return EventType.dehumidifier_tank_full, ""
    if description == INSTALLED_TEXT:
        return EventType.dehumidifier_installed, description
    return EventType.custom, description


def build_migration_records(
    events: Sequence[LegacyEvent],
    *,
    recorded_at: datetime,
    new_id: Callable[[], uuid.UUID] = uuid.uuid7,
) -> list[EventRecord]:
    """Build one create record per row, all stamped with this migration's UTC instant."""
    if recorded_at.tzinfo is None or recorded_at.utcoffset() != UTC.utcoffset(recorded_at):
        raise ValueError("recorded_at must be a timezone-aware UTC instant")
    source = EventSource(workflow=MIGRATION_WORKFLOW)
    records: list[EventRecord] = []
    for event in events:
        event_type, notes = _event_type_and_notes(event.description)
        records.append(
            build_create_record(
                event_type=event_type,
                effective_at=event.effective_at,
                notes=notes,
                source=source,
                now=lambda: recorded_at,
                new_id=new_id,
            )
        )
    return records


def verify_migration_records(
    records: Sequence[EventRecord], events: Sequence[LegacyEvent]
) -> datetime:
    """Verify exact row semantics and return the single migration ``recorded_at`` instant."""
    if len(records) != EXPECTED_EVENT_COUNT:
        raise ValueError(
            f"Expected {EXPECTED_EVENT_COUNT} csv-migration records, found {len(records)}"
        )

    expected: Counter[MigrationSignature] = Counter(
        (
            event.effective_at,
            *_event_type_and_notes(event.description),
        )
        for event in events
    )
    actual: Counter[MigrationSignature] = Counter(
        (record.effective_at, record.event_type, record.data.notes or "") for record in records
    )
    if actual != expected:
        raise ValueError(f"R2 csv-migration records differ from the CSV: {actual - expected!r}")
    if any(record.operation.value != "create" for record in records):
        raise ValueError("Every csv-migration record must be a create operation")
    if any(record.source != EventSource(workflow=MIGRATION_WORKFLOW) for record in records):
        raise ValueError("Every csv-migration record must have only workflow provenance")
    if len({record.event_id for record in records}) != EXPECTED_EVENT_COUNT:
        raise ValueError("csv-migration event_id values are not unique")
    if len({record.revision_id for record in records}) != EXPECTED_EVENT_COUNT:
        raise ValueError("csv-migration revision_id values are not unique")

    recorded_at_values = {record.recorded_at for record in records}
    if len(recorded_at_values) != 1:
        raise ValueError("csv-migration records do not share one recorded_at instant")
    return next(iter(recorded_at_values))


def _r2_environment() -> tuple[str, str, dict[str, str]]:
    missing = [name for name in REQUIRED_R2_ENV if not os.getenv(name)]
    if missing:
        raise ValueError(f"Missing required R2 environment variables: {', '.join(missing)}")
    environment = os.environ.copy()
    environment["AWS_ACCESS_KEY_ID"] = os.environ["R2_ACCESS_KEY_ID"]
    environment["AWS_SECRET_ACCESS_KEY"] = os.environ["R2_SECRET_ACCESS_KEY"]
    return os.environ["R2_BUCKET"], os.environ["R2_ENDPOINT_URL"], environment


def _sync(source: str, destination: str) -> None:
    _, endpoint_url, environment = _r2_environment()
    subprocess.run(
        [
            "aws",
            "s3",
            "sync",
            source,
            destination,
            "--endpoint-url",
            endpoint_url,
            "--no-progress",
        ],
        check=True,
        env=environment,
    )


def _download_migration_records(download_dir: Path) -> list[EventRecord]:
    bucket, _, _ = _r2_environment()
    shutil.rmtree(download_dir, ignore_errors=True)
    download_dir.mkdir(parents=True)
    _sync(f"s3://{bucket}/events", str(download_dir))
    records = [
        EventRecord.model_validate_json(path.read_text(encoding="utf-8"))
        for path in download_dir.glob("year=*/*.json")
    ]
    return [record for record in records if record.source.workflow == MIGRATION_WORKFLOW]


def migrate(csv_path: Path = DEFAULT_CSV_PATH) -> tuple[list[EventRecord], bool]:
    """Run or verify the migration. Returns ``(records, uploaded_this_run)``."""
    events = load_legacy_events(csv_path)
    with tempfile.TemporaryDirectory(prefix="basement-event-migration-") as temporary:
        temporary_path = Path(temporary)
        existing = _download_migration_records(temporary_path / "existing")
        if existing:
            verify_migration_records(existing, events)
            return existing, False

        recorded_at = datetime.now(UTC)
        records = build_migration_records(events, recorded_at=recorded_at)
        upload_root = temporary_path / "upload"
        for record in records:
            write_record(record, upload_root)

        bucket, _, _ = _r2_environment()
        _sync(str(upload_root / "events"), f"s3://{bucket}/events")
        uploaded = _download_migration_records(temporary_path / "verified")
        verify_migration_records(uploaded, events)
        return uploaded, True


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--csv", type=Path, default=DEFAULT_CSV_PATH)
    args = parser.parse_args()
    records, uploaded = migrate(args.csv)
    recorded_at = verify_migration_records(records, load_legacy_events(args.csv))
    action = "uploaded and verified" if uploaded else "already present and verified; uploaded 0"
    print(f"{action}: {len(records)} csv-migration records, recorded_at={recorded_at.isoformat()}")


if __name__ == "__main__":
    main()
