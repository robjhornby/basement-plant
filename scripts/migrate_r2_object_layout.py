from __future__ import annotations

import argparse
import json
import re
import shutil
from datetime import date
from pathlib import Path
from typing import cast

from basement_analysis.object_layout import (
    attachment_object_key,
    message_object_key,
    outcome_object_key,
)

MESSAGE_PATTERN = re.compile(
    r"raw-emails/source=x-sense/received_date=(\d{4}-\d{2}-\d{2})/raw_sha256=([0-9a-f]+)\.eml$"
)
ATTACHMENT_PATTERN = re.compile(
    r"csv/source=x-sense/export_date=(\d{4}-\d{2}-\d{2})/"
    r"attachment_sha256=([0-9a-f]+)/([^/]+)$"
)
OUTCOME_PATTERN = re.compile(
    r"manifests/(?:ingest|rejections)/source=x-sense/"
    r"received_date=(\d{4}-\d{2}-\d{2})/raw_sha256=([0-9a-f]+)\.json$"
)


def migrate_layout(source_root: Path, destination_root: Path) -> tuple[Path, ...]:
    """Copy a legacy local R2 mirror into the semantic ingest layout."""
    written: list[Path] = []
    for source_path in sorted(path for path in source_root.glob("**/*") if path.is_file()):
        legacy_key = source_path.relative_to(source_root).as_posix()
        destination_key, content = migrated_object(legacy_key, source_path.read_bytes())
        destination_path = destination_root / destination_key
        destination_path.parent.mkdir(parents=True, exist_ok=True)
        destination_path.write_bytes(content)
        written.append(destination_path)
    return tuple(written)


def migrated_object(legacy_key: str, content: bytes) -> tuple[str, bytes]:
    if match := MESSAGE_PATTERN.fullmatch(legacy_key):
        return message_object_key(_date(match[1]), match[2]), content
    if match := ATTACHMENT_PATTERN.fullmatch(legacy_key):
        return attachment_object_key(_date(match[1]), match[2], match[3]), content
    if match := OUTCOME_PATTERN.fullmatch(legacy_key):
        return (
            outcome_object_key(_date(match[1]), match[2]),
            migrated_outcome(content),
        )
    raise ValueError(f"Unsupported legacy object key: {legacy_key}")


def migrated_outcome(content: bytes) -> bytes:
    record = cast(dict[str, object], json.loads(content))
    received_date = _date(_required_string(record, "received_date"))
    message_sha256 = _required_string(record, "raw_sha256")
    record["message_object_key"] = message_object_key(received_date, message_sha256)
    record["message_sha256"] = record.pop("raw_sha256")
    record.pop("raw_object_key", None)

    attachments = record.get("attachments")
    if isinstance(attachments, list):
        for item in cast(list[object], attachments):
            if not isinstance(item, dict):
                continue
            attachment = cast(dict[str, object], item)
            legacy_attachment_key = attachment.pop("csv_object_key", None)
            attachment["attachment_object_key"] = (
                migrated_attachment_key(legacy_attachment_key)
                if isinstance(legacy_attachment_key, str)
                else None
            )
    return (json.dumps(record, indent=2, sort_keys=True) + "\n").encode()


def migrated_attachment_key(legacy_key: str) -> str:
    match = ATTACHMENT_PATTERN.fullmatch(legacy_key)
    if match is None:
        raise ValueError(f"Unsupported legacy attachment key: {legacy_key}")
    return attachment_object_key(_date(match[1]), match[2], match[3])


def _required_string(record: dict[str, object], field: str) -> str:
    value = record.get(field)
    if not isinstance(value, str) or not value:
        raise ValueError(f"Outcome needs a non-empty {field!r} field")
    return value


def _date(value: str) -> date:
    return date.fromisoformat(value)


def main() -> None:
    parser = argparse.ArgumentParser(description="Migrate a local legacy R2 mirror.")
    parser.add_argument("source_root", type=Path)
    parser.add_argument("destination_root", type=Path)
    args = parser.parse_args()
    if args.destination_root.exists():
        shutil.rmtree(args.destination_root)
    written = migrate_layout(args.source_root, args.destination_root)
    print(f"Wrote {len(written)} semantic ingest objects to {args.destination_root}")


if __name__ == "__main__":
    main()
