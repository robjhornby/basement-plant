"""R2-backed, append-only event store (Appendix A of the PRD, adapted to R2).

The store is one **immutable JSON file per mutation** under
``s3://$R2_BUCKET/events/year=YYYY/<revision_id>.json``. There are no in-place
edits: an :class:`EventRecord` with ``operation`` ``create`` / ``update`` /
``delete`` (tombstone) is appended for every change, and DuckDB derives the
current state from the full history (latest revision per ``event_id``).

Design notes worth keeping close to the code:

* IDs are stdlib **UUIDv7** (Python 3.14 ``uuid.uuid7()``) — globally unique and
  time-sortable, so a lexicographic revision-id sort is also a chronological one.
  ``event_id`` is the stable logical-event identity; ``revision_id`` names one
  immutable record.
* All canonical timestamps are **UTC instants** serialized ISO-8601 with a
  trailing ``Z``. ``Europe/London`` lives only at the input boundary, via
  :func:`basement_analysis.timezones.london_wall_clock_to_utc`.
* Year partitioning keys off **``effective_at``** (when the event occurred), not
  ``recorded_at`` (when it was written).

Reproducibility is achieved by **injection**, never monkeypatching: the clock
(:data:`Clock`) and the UUIDv7 id factory (:data:`IdFactory`) are parameters of
the builder functions, so a test can freeze both and emit byte-identical JSON.
"""

from __future__ import annotations

import uuid
from collections.abc import Callable, Iterable
from datetime import UTC, datetime, timedelta
from enum import StrEnum
from pathlib import Path
from typing import cast

import duckdb
from pydantic import BaseModel, ConfigDict, field_serializer, field_validator, model_validator

from basement_analysis.curated_dataset import configure_r2_access
from basement_analysis.timezones import london_wall_clock_to_utc

__all__ = [
    "Clock",
    "EventData",
    "EventRecord",
    "EventSource",
    "EventType",
    "IdFactory",
    "Operation",
    "build_create_record",
    "build_delete_record",
    "build_update_record",
    "connect_event_store",
    "current_events",
    "deleted_events",
    "event_history",
    "full_history",
    "load_records",
    "local_events_glob",
    "object_key",
    "parse_event_effective_at",
    "production_events_glob",
    "serialize_record",
    "utc_now",
    "write_record",
]

# Manual event entry format: space-separated, seconds required (Appendix B). Interpreted as
# `Europe/London` wall-clock, then converted to a canonical UTC instant.
EVENT_INPUT_FORMAT = "%Y-%m-%d %H:%M:%S"


class Operation(StrEnum):
    """The three append-only mutations. ``delete`` writes a tombstone, not a physical delete."""

    create = "create"
    update = "update"
    delete = "delete"


class EventType(StrEnum):
    """Application-level event category as a slug (consumers key off the enum, not English text)."""

    dehumidifier_tank_full = "dehumidifier_tank_full"
    dehumidifier_tank_emptied = "dehumidifier_tank_emptied"
    dehumidifier_installed = "dehumidifier_installed"
    custom = "custom"


class EventData(BaseModel):
    """Event payload. ``notes`` is omitted from the JSON when empty (serialized as ``{}``)."""

    model_config = ConfigDict(frozen=True)

    notes: str | None = None

    @field_validator("notes")
    @classmethod
    def _empty_notes_is_omitted(cls, value: str | None) -> str | None:
        # Treat empty / whitespace-only notes as "no notes" so `exclude_none` drops the key,
        # while preserving the exact text of any real note (no trimming of content).
        if value is not None and not value.strip():
            return None
        return value


class EventSource(BaseModel):
    """Provenance of the GitHub Actions run. All fields optional (migration supplies only workflow).

    ``run_id`` is a string, matching the Appendix A example (``"123456789"``).
    """

    model_config = ConfigDict(frozen=True)

    repository: str | None = None
    workflow: str | None = None
    run_id: str | None = None
    git_sha: str | None = None


class EventRecord(BaseModel):
    """One immutable event-store record — the unit written to a single JSON object in R2."""

    model_config = ConfigDict(frozen=True)

    event_id: uuid.UUID
    revision_id: uuid.UUID
    operation: Operation
    recorded_at: datetime
    effective_at: datetime | None = None
    event_type: EventType
    data: EventData = EventData()
    source: EventSource = EventSource()

    @field_validator("recorded_at", "effective_at")
    @classmethod
    def _require_utc_instant(cls, value: datetime | None) -> datetime | None:
        # Canonical timestamps must be UTC instants: reject naive and non-UTC-offset datetimes.
        if value is None:
            return None
        if value.tzinfo is None or value.utcoffset() != timedelta(0):
            raise ValueError("canonical timestamps must be timezone-aware UTC instants")
        return value.astimezone(UTC)

    @model_validator(mode="after")
    def _check_operation_invariants(self) -> EventRecord:
        # A tombstone has no effective_at; create/update always do (Appendix A delete example).
        if self.operation == Operation.delete:
            if self.effective_at is not None:
                raise ValueError("delete records (tombstones) must omit effective_at")
        elif self.effective_at is None:
            raise ValueError(f"{self.operation} records require effective_at")
        # A custom event *is* its notes text, so non-tombstone custom records require notes.
        if (
            self.operation != Operation.delete
            and self.event_type == EventType.custom
            and self.data.notes is None
        ):
            raise ValueError("custom events require non-empty notes")
        return self

    @field_serializer("recorded_at", "effective_at", when_used="json")
    def _serialize_utc_z(self, value: datetime | None) -> str | None:
        # ISO-8601 UTC with a trailing `Z` (not `+00:00`), per the canonical-timestamp rule.
        if value is None:
            return None
        return value.astimezone(UTC).isoformat().replace("+00:00", "Z")


# Injected reproducibility seams (defaults are the real clock / real UUIDv7 generator).
Clock = Callable[[], datetime]
IdFactory = Callable[[], uuid.UUID]


def utc_now() -> datetime:
    """Default clock: the current instant as a UTC-aware datetime."""
    return datetime.now(UTC)


def parse_event_effective_at(text: str) -> datetime:
    """Parse a ``YYYY-MM-DD HH:mm:ss`` entry (Europe/London wall-clock) into a UTC instant.

    Seconds are required. The naive wall-clock value is interpreted as ``Europe/London`` and
    converted to UTC via the shared :func:`london_wall_clock_to_utc` boundary helper (ticket 02).
    """
    naive = datetime.strptime(text.strip(), EVENT_INPUT_FORMAT)
    return london_wall_clock_to_utc(naive)


def build_create_record(
    *,
    event_type: EventType,
    effective_at: datetime,
    notes: str = "",
    source: EventSource | None = None,
    now: Clock = utc_now,
    new_id: IdFactory = uuid.uuid7,
) -> EventRecord:
    """Build a ``create`` record. Consumes two ids: ``event_id`` then ``revision_id``."""
    return EventRecord(
        event_id=new_id(),
        revision_id=new_id(),
        operation=Operation.create,
        recorded_at=now(),
        effective_at=effective_at,
        event_type=event_type,
        data=EventData(notes=notes),
        source=source or EventSource(),
    )


def build_update_record(
    *,
    event_id: uuid.UUID,
    event_type: EventType,
    effective_at: datetime,
    notes: str = "",
    source: EventSource | None = None,
    now: Clock = utc_now,
    new_id: IdFactory = uuid.uuid7,
) -> EventRecord:
    """Build an ``update``: a full snapshot of the logical event under the existing ``event_id``."""
    return EventRecord(
        event_id=event_id,
        revision_id=new_id(),
        operation=Operation.update,
        recorded_at=now(),
        effective_at=effective_at,
        event_type=event_type,
        data=EventData(notes=notes),
        source=source or EventSource(),
    )


def build_delete_record(
    *,
    event_id: uuid.UUID,
    event_type: EventType,
    source: EventSource | None = None,
    now: Clock = utc_now,
    new_id: IdFactory = uuid.uuid7,
) -> EventRecord:
    """Build a ``delete`` tombstone under the existing ``event_id`` (no ``effective_at``)."""
    return EventRecord(
        event_id=event_id,
        revision_id=new_id(),
        operation=Operation.delete,
        recorded_at=now(),
        effective_at=None,
        event_type=event_type,
        data=EventData(),
        source=source or EventSource(),
    )


def object_key(record: EventRecord, *, effective_year: int | None = None) -> str:
    """Object key ``events/year=YYYY/<revision_id>.json`` for a record.

    ``YYYY`` is the **UTC year of ``effective_at``**. A ``delete`` tombstone has no
    ``effective_at``, so its partition year cannot be read off the record itself.

    Delete-key-year policy: prefer the caller-supplied ``effective_year`` (the year of the
    target event's ``effective_at``) so a tombstone lands in the *same* partition as the event
    it deletes, keeping every revision of a logical event colocated for glob pruning. When the
    target event is not loaded and no year is supplied, fall back to the ``recorded_at`` year —
    the simplest defensible default (queries never depend on the partition, only DuckDB's
    ``read_json_auto`` glob does, which spans all years anyway).
    """
    if record.effective_at is not None:
        year = record.effective_at.year
    elif effective_year is not None:
        year = effective_year
    else:
        year = record.recorded_at.year
    return f"events/year={year}/{record.revision_id}.json"


def serialize_record(record: EventRecord) -> str:
    """Serialize a record to its canonical JSON text (2-space indent, trailing newline).

    ``exclude_none`` omits ``effective_at`` on tombstones and ``notes`` when empty, matching the
    Appendix A field-omission rules.
    """
    return record.model_dump_json(indent=2, exclude_none=True) + "\n"


def write_record(
    record: EventRecord, output_dir: Path, *, effective_year: int | None = None
) -> str:
    """Write a record's JSON to ``output_dir/<object_key>`` locally and return the object key.

    Upload to R2 is the caller's job (the Action runs ``aws s3 cp``; no boto3 here).
    """
    key = object_key(record, effective_year=effective_year)
    destination = output_dir / key
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(serialize_record(record), encoding="utf-8")
    return key


# --- Read path (DuckDB) ------------------------------------------------------------------------
#
# DuckDB reads the JSON corpus and derives which revisions are current/deleted (the windowing).
# Python then loads exactly those files back into typed `EventRecord`s, so the read path stays
# strongly typed without mapping DuckDB structs onto the model by hand.

# Both CTEs are always declared; a query may use only `history`. `filename = true` surfaces the
# source object path so we can re-load the chosen records with Pydantic. Ordering by
# `recorded_at DESC, revision_id DESC` matches Appendix A (UUIDv7 ids break ties chronologically).
_HISTORY_CTE = """
with history as (
    select *, filename as source_file
    from read_json_auto($1, union_by_name = true, filename = true)
),
latest as (
    select *, row_number() over (
        partition by event_id
        order by recorded_at desc, revision_id desc
    ) as rn
    from history
)
"""


def production_events_glob(bucket: str) -> str:
    """R2 glob over the full event corpus for a bucket (used with :func:`connect_event_store`)."""
    return f"s3://{bucket}/events/year=*/*.json"


def local_events_glob(corpus_dir: Path) -> str:
    """Local glob matching the checked-in ``year=YYYY/<revision_id>.json`` corpus layout."""
    return str(corpus_dir / "year=*" / "*.json")


def connect_event_store(glob: str) -> duckdb.DuckDBPyConnection:
    """Open a DuckDB connection, configuring R2/httpfs access for ``s3://`` globs (else local)."""
    connection = duckdb.connect(database=":memory:")
    if glob.startswith("s3://"):
        configure_r2_access(connection)
    return connection


def load_records(paths: Iterable[Path | str]) -> list[EventRecord]:
    """Load and validate event records from their JSON object paths."""
    return [
        EventRecord.model_validate_json(Path(path).read_text(encoding="utf-8")) for path in paths
    ]


def _query_source_files(
    connection: duckdb.DuckDBPyConnection, sql: str, params: list[object]
) -> list[str]:
    rows = connection.execute(sql, params).fetchall()
    return [cast(str, row[0]) for row in rows]


def current_events(connection: duckdb.DuckDBPyConnection, glob: str) -> list[EventRecord]:
    """Current non-deleted events: the latest revision per ``event_id`` that is not a tombstone."""
    sql = _HISTORY_CTE + (
        "select source_file from latest "
        "where rn = 1 and operation <> 'delete' "
        "order by effective_at, event_id"
    )
    return load_records(_query_source_files(connection, sql, [glob]))


def deleted_events(connection: duckdb.DuckDBPyConnection, glob: str) -> list[EventRecord]:
    """Logically deleted events: event_ids whose latest revision is a tombstone."""
    sql = _HISTORY_CTE + (
        "select source_file from latest "
        "where rn = 1 and operation = 'delete' "
        "order by recorded_at, event_id"
    )
    return load_records(_query_source_files(connection, sql, [glob]))


def full_history(connection: duckdb.DuckDBPyConnection, glob: str) -> list[EventRecord]:
    """Every stored revision, ordered by ``event_id`` then chronologically."""
    sql = _HISTORY_CTE + (
        "select source_file from history order by event_id, recorded_at, revision_id"
    )
    return load_records(_query_source_files(connection, sql, [glob]))


def event_history(
    connection: duckdb.DuckDBPyConnection, glob: str, event_id: uuid.UUID
) -> list[EventRecord]:
    """The full revision history for a single ``event_id``, oldest first."""
    sql = _HISTORY_CTE + (
        "select source_file from history "
        "where event_id = $2 "
        "order by recorded_at, revision_id"
    )
    return load_records(_query_source_files(connection, sql, [glob, str(event_id)]))
