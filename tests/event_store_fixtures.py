from __future__ import annotations

import uuid
from collections.abc import Sequence
from datetime import UTC, datetime
from pathlib import Path

from basement_analysis.event_store import (
    EventData,
    EventRecord,
    EventSource,
    Operation,
    serialize_record,
)
from basement_analysis.summaries import Event


def write_event_store(root: Path, events: Sequence[Event]) -> str:
    """Write a minimal immutable-record corpus and return its DuckDB glob."""
    for index, event in enumerate(events, start=1):
        record = EventRecord(
            event_id=uuid.UUID(int=(index << 80) | (7 << 76) | (2 << 62)),
            revision_id=uuid.UUID(int=((index + 10_000) << 80) | (7 << 76) | (2 << 62)),
            operation=Operation.create,
            recorded_at=datetime(2026, 8, 22, tzinfo=UTC),
            effective_at=event.timestamp,
            event_type=event.event_type,
            data=EventData(notes=event.notes),
            source=EventSource(workflow="pytest-fixture"),
        )
        path = root / f"year={event.timestamp.year}" / f"{record.revision_id}.json"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(serialize_record(record), encoding="utf-8")
    return str(root / "year=*" / "*.json")
