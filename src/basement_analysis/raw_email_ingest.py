from __future__ import annotations

import csv
import hashlib
import json
import shutil
from collections.abc import Iterable, Sequence
from datetime import UTC, date, datetime
from email.message import Message
from email.parser import BytesParser
from email.policy import default
from email.utils import parsedate_to_datetime
from pathlib import Path
from typing import cast

from pydantic import BaseModel, ConfigDict

from basement_analysis.object_layout import (
    INGEST_SOURCE,
    attachment_object_key,
    message_object_key,
    outcome_object_key,
)

PARSER_VERSION = "basement_analysis.raw_email_ingest.v1"
REQUIRED_SENSOR_COLUMNS = (
    "Time",
    "Temperature_Celsius",
    "Relative Humidity_Percent",
)


class RawEmailInput(BaseModel):
    model_config = ConfigDict(frozen=True)

    path: Path


class CsvValidationResult(BaseModel):
    model_config = ConfigDict(frozen=True)

    status: str
    row_count: int
    reason: str
    export_date: date | None


class AttachmentResult(BaseModel):
    model_config = ConfigDict(frozen=True)

    filename: str
    content_sha256: str
    status: str
    row_count: int
    reason: str
    attachment_object_key: str | None


class EmailIngestResult(BaseModel):
    model_config = ConfigDict(frozen=True)

    message_object_key: str
    message_sha256: str
    message_id: str
    status: str
    reason: str
    outcome_object_key: str
    attachment_results: tuple[AttachmentResult, ...]


class IngestState(BaseModel):
    raw_sha256_values: set[str]
    message_ids: set[str]
    csv_sha256_values: set[str]


def process_raw_email_batch(
    raw_email_dir: Path,
    object_store_dir: Path,
) -> tuple[EmailIngestResult, ...]:
    """Process local raw emails into an R2-shaped object tree."""
    state = load_ingest_state(object_store_dir)
    results: list[EmailIngestResult] = []
    for raw_email_input in iter_raw_email_inputs(raw_email_dir):
        result = process_raw_email(
            raw_email_input=raw_email_input,
            object_store_dir=object_store_dir,
            state=state,
        )
        results.append(result)
        state.raw_sha256_values.add(result.message_sha256)
        if result.status not in {"duplicate_raw_sha256", "invalid_raw_email"}:
            state.message_ids.add(result.message_id)
        for attachment_result in result.attachment_results:
            if attachment_result.status == "extracted":
                state.csv_sha256_values.add(attachment_result.content_sha256)
    return tuple(results)


def iter_raw_email_inputs(raw_email_dir: Path) -> tuple[RawEmailInput, ...]:
    raw_email_paths = sorted(path for path in raw_email_dir.glob("**/*.eml") if path.is_file())
    return tuple(RawEmailInput(path=raw_email_path) for raw_email_path in raw_email_paths)


def load_ingest_state(object_store_dir: Path) -> IngestState:
    state = IngestState(raw_sha256_values=set(), message_ids=set(), csv_sha256_values=set())
    for manifest_path in sorted(
        (object_store_dir / "ingest" / INGEST_SOURCE / "outcomes").glob("**/*.json")
    ):
        manifest = cast(dict[str, object], json.loads(manifest_path.read_text(encoding="utf-8")))
        raw_sha256 = manifest.get("message_sha256")
        if isinstance(raw_sha256, str):
            state.raw_sha256_values.add(raw_sha256)
        headers = manifest.get("headers")
        if isinstance(headers, dict):
            header_values = cast(dict[object, object], headers)
            message_id = header_values.get("message_id")
            if isinstance(message_id, str) and message_id:
                state.message_ids.add(message_id)
        attachments = manifest.get("attachments")
        if isinstance(attachments, list):
            attachment_items = cast(list[object], attachments)
            for attachment in attachment_items:
                if not isinstance(attachment, dict):
                    continue
                attachment_values = cast(dict[object, object], attachment)
                csv_sha256 = attachment_values.get("content_sha256")
                if isinstance(csv_sha256, str) and attachment_values.get("status") == "extracted":
                    state.csv_sha256_values.add(csv_sha256)
    return state


def process_raw_email(
    raw_email_input: RawEmailInput,
    object_store_dir: Path,
    state: IngestState,
) -> EmailIngestResult:
    raw_bytes = raw_email_input.path.read_bytes()
    raw_sha256 = sha256_hex(raw_bytes)
    try:
        message = BytesParser(policy=default).parsebytes(raw_bytes)
    except ValueError as error:
        message_id = f"unparseable:{raw_sha256}"
        received_date = date.today()
        message_key = message_object_key(received_date, raw_sha256)
        copy_raw_email_object(raw_email_input.path, object_store_dir / message_key, raw_bytes)
        result = EmailIngestResult(
            message_object_key=message_key,
            message_sha256=raw_sha256,
            message_id=message_id,
            status="invalid_raw_email",
            reason=f"could not parse raw email: {error}",
            outcome_object_key=outcome_object_key(received_date, raw_sha256),
            attachment_results=(),
        )
        write_manifest(object_store_dir, result, headers={}, received_date=received_date)
        return result

    message_id = normalized_message_id(message, raw_sha256)
    received_date = received_date_for(message)
    message_key = message_object_key(received_date, raw_sha256)
    copy_raw_email_object(raw_email_input.path, object_store_dir / message_key, raw_bytes)
    outcome_key = outcome_object_key(received_date, raw_sha256)
    headers = selected_headers(message, message_id)

    if raw_sha256 in state.raw_sha256_values:
        return EmailIngestResult(
            message_object_key=message_key,
            message_sha256=raw_sha256,
            message_id=message_id,
            status="duplicate_raw_sha256",
            reason="raw email bytes already have an ingest manifest",
            outcome_object_key=outcome_key,
            attachment_results=(),
        )

    if message_id in state.message_ids:
        result = EmailIngestResult(
            message_object_key=message_key,
            message_sha256=raw_sha256,
            message_id=message_id,
            status="duplicate_message_id",
            reason="Message-ID already seen; treat as duplicate forward",
            outcome_object_key=outcome_key,
            attachment_results=(),
        )
        write_manifest(object_store_dir, result, headers=headers, received_date=received_date)
        return result

    attachment_results = tuple(
        process_csv_attachment(
            filename=filename,
            attachment_bytes=attachment_bytes,
            object_store_dir=object_store_dir,
            state=state,
        )
        for filename, attachment_bytes in csv_attachments(message)
    )
    status = "accepted" if attachment_results else "no_csv_attachments"
    reason = (
        "processed CSV attachment candidates"
        if attachment_results
        else "message contained no CSV attachments"
    )
    result = EmailIngestResult(
        message_object_key=message_key,
        message_sha256=raw_sha256,
        message_id=message_id,
        status=status,
        reason=reason,
        outcome_object_key=outcome_key,
        attachment_results=attachment_results,
    )
    write_manifest(object_store_dir, result, headers=headers, received_date=received_date)
    return result


def process_csv_attachment(
    filename: str,
    attachment_bytes: bytes,
    object_store_dir: Path,
    state: IngestState,
) -> AttachmentResult:
    content_sha256 = sha256_hex(attachment_bytes)
    validation = validate_sensor_csv(attachment_bytes)
    if validation.status != "valid":
        return AttachmentResult(
            filename=filename,
            content_sha256=content_sha256,
            status=validation.status,
            row_count=validation.row_count,
            reason=validation.reason,
            attachment_object_key=None,
        )
    if content_sha256 in state.csv_sha256_values:
        return AttachmentResult(
            filename=filename,
            content_sha256=content_sha256,
            status="duplicate_content_hash",
            row_count=validation.row_count,
            reason="valid CSV bytes already extracted from another email",
            attachment_object_key=None,
        )

    export_date = validation.export_date
    if export_date is None:
        return AttachmentResult(
            filename=filename,
            content_sha256=content_sha256,
            status="invalid_csv",
            row_count=validation.row_count,
            reason="could not derive export date from the first Time value",
            attachment_object_key=None,
        )

    attachment_key = attachment_object_key(export_date, content_sha256, safe_filename(filename))
    write_object_if_absent(object_store_dir / attachment_key, attachment_bytes)
    return AttachmentResult(
        filename=filename,
        content_sha256=content_sha256,
        status="extracted",
        row_count=validation.row_count,
        reason="first-seen valid CSV content",
        attachment_object_key=attachment_key,
    )


def csv_attachments(message: Message) -> Iterable[tuple[str, bytes]]:
    for part in message.walk():
        filename = part.get_filename()
        content_type = part.get_content_type()
        if not filename and content_type != "text/csv":
            continue
        if filename and not filename.lower().endswith(".csv") and content_type != "text/csv":
            continue
        payload = part.get_payload(decode=True)
        if not isinstance(payload, bytes):
            continue
        yield filename or "attachment.csv", payload


def validate_sensor_csv(attachment_bytes: bytes) -> CsvValidationResult:
    try:
        decoded_text = attachment_bytes.decode("utf-8-sig")
    except UnicodeDecodeError as error:
        return CsvValidationResult(
            status="invalid_csv",
            row_count=0,
            reason=f"cannot decode as utf-8-sig: {error}",
            export_date=None,
        )

    reader = csv.DictReader(decoded_text.splitlines())
    fieldnames = tuple(reader.fieldnames or ())
    missing_columns = [column for column in REQUIRED_SENSOR_COLUMNS if column not in fieldnames]
    if missing_columns:
        return CsvValidationResult(
            status="invalid_csv",
            row_count=0,
            reason=f"missing required columns: {', '.join(missing_columns)}",
            export_date=None,
        )

    row_count = 0
    export_date: date | None = None
    for row in reader:
        row_count += 1
        if export_date is None:
            export_date = parse_export_date(row.get("Time"))
        for column in REQUIRED_SENSOR_COLUMNS:
            if row.get(column) in (None, ""):
                return CsvValidationResult(
                    status="invalid_csv",
                    row_count=row_count,
                    reason=f"row {row_count} has blank required column {column}",
                    export_date=export_date,
                )
    return CsvValidationResult(
        status="valid",
        row_count=row_count,
        reason="valid sensor CSV",
        export_date=export_date,
    )


def parse_export_date(raw_time: str | None) -> date | None:
    if raw_time is None:
        return None
    for date_format in ("%Y/%m/%d %H:%M", "%Y-%m-%d %H:%M:%S", "%Y-%m-%dT%H:%M:%S"):
        try:
            return datetime.strptime(raw_time, date_format).date()
        except ValueError:
            continue
    return None


def received_date_for(message: Message) -> date:
    date_header = message.get("Date")
    if date_header is None:
        return date.today()
    parsed_date = parsedate_to_datetime(str(date_header))
    if parsed_date.tzinfo is None:
        parsed_date = parsed_date.replace(tzinfo=UTC)
    return parsed_date.astimezone(UTC).date()


def normalized_message_id(message: Message, raw_sha256: str) -> str:
    message_id = message.get("Message-ID")
    if message_id is None or not str(message_id).strip():
        return f"missing-message-id:{raw_sha256}"
    return str(message_id).strip()


def selected_headers(message: Message, message_id: str) -> dict[str, str]:
    headers: dict[str, str] = {"message_id": message_id}
    for header_name in ("Date", "From", "To", "Subject"):
        value = message.get(header_name)
        headers[header_name.lower().replace("-", "_")] = str(value) if value is not None else ""
    return headers


def write_manifest(
    object_store_dir: Path,
    result: EmailIngestResult,
    headers: dict[str, str],
    received_date: date,
) -> None:
    manifest = {
        "parser_version": PARSER_VERSION,
        "status": result.status,
        "reason": result.reason,
        "source": "x-sense",
        "received_date": received_date.isoformat(),
        "message_object_key": result.message_object_key,
        "message_sha256": result.message_sha256,
        "headers": headers,
        "attachments": [
            {
                "filename": attachment.filename,
                "content_sha256": attachment.content_sha256,
                "status": attachment.status,
                "row_count": attachment.row_count,
                "reason": attachment.reason,
                "attachment_object_key": attachment.attachment_object_key,
            }
            for attachment in result.attachment_results
        ],
    }
    write_object_if_absent(
        object_store_dir / result.outcome_object_key,
        json.dumps(manifest, indent=2, sort_keys=True).encode(),
    )


def copy_raw_email_object(source_path: Path, destination_path: Path, raw_bytes: bytes) -> None:
    if destination_path.exists() and source_path.resolve() == destination_path.resolve():
        return
    if source_path.exists() and destination_path.exists():
        try:
            if source_path.samefile(destination_path):
                return
        except OSError:
            pass
    if destination_path.exists():
        return
    destination_path.parent.mkdir(parents=True, exist_ok=True)
    try:
        shutil.copyfile(source_path, destination_path)
    except shutil.SameFileError:
        return
    if not destination_path.exists():
        destination_path.write_bytes(raw_bytes)


def write_object_if_absent(path: Path, content: bytes) -> None:
    if path.exists():
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(content)


def sha256_hex(content: bytes) -> str:
    return hashlib.sha256(content).hexdigest()


def safe_filename(filename: str) -> str:
    cleaned = "".join(
        character if character.isalnum() or character in ".-_" else "_" for character in filename
    )
    return cleaned or "attachment.csv"


def print_ingest_results(results: Sequence[EmailIngestResult]) -> None:
    if not results:
        print("No .eml files found.")
        return
    for result in results:
        print(f"{result.status:22} {result.message_object_key}")
        print(f"  outcome: {result.outcome_object_key}")
        print(f"  reason: {result.reason}")
        for attachment in result.attachment_results:
            output = attachment.attachment_object_key or "-"
            print(
                "  "
                f"{attachment.status:22} rows={attachment.row_count:<5} "
                f"hash={attachment.content_sha256[:12]} out={output}"
            )
