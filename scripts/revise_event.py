"""Stage an update or tombstone for an existing basement event."""

from __future__ import annotations

import argparse
import uuid
from collections.abc import Sequence
from pathlib import Path

from basement_analysis.event_store import (
    EventSource,
    EventType,
    Operation,
    build_delete_record,
    build_update_record,
    parse_event_effective_at,
    write_record,
)


def main(argv: Sequence[str] | None = None) -> None:
    parser = argparse.ArgumentParser(
        description="Stage an immutable update or deletion record for upload to R2."
    )
    parser.add_argument("operation", type=Operation, choices=(Operation.update, Operation.delete))
    parser.add_argument("--event-id", required=True, type=uuid.UUID)
    parser.add_argument("--event-type", required=True, type=EventType, choices=list(EventType))
    parser.add_argument(
        "--effective-at",
        type=parse_event_effective_at,
        metavar="YYYY-MM-DD HH:mm:ss",
        help="Updated event time in Europe/London; required for updates.",
    )
    parser.add_argument("--notes", default="", help="Updated notes; required for custom events.")
    parser.add_argument(
        "--effective-year",
        type=int,
        help="Original event's UTC year; required for deletions so revisions remain colocated.",
    )
    parser.add_argument("--output-dir", type=Path, default=Path())
    args = parser.parse_args(argv)

    source = EventSource(workflow="local-event-revision")
    if args.operation == Operation.update:
        if args.effective_at is None:
            parser.error("--effective-at is required for updates")
        if args.effective_year is not None:
            parser.error("--effective-year applies only to deletions")
        record = build_update_record(
            event_id=args.event_id,
            event_type=args.event_type,
            effective_at=args.effective_at,
            notes=args.notes,
            source=source,
        )
        effective_year = None
    else:
        if args.effective_at is not None:
            parser.error("--effective-at applies only to updates")
        if args.notes.strip():
            parser.error("--notes applies only to updates")
        if args.effective_year is None:
            parser.error("--effective-year is required for deletions")
        record = build_delete_record(
            event_id=args.event_id,
            event_type=args.event_type,
            source=source,
        )
        effective_year = args.effective_year

    print(write_record(record, args.output_dir, effective_year=effective_year))


if __name__ == "__main__":
    main()
