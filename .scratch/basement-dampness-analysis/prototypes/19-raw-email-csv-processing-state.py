from __future__ import annotations

import argparse
import csv
import hashlib
import shutil
import textwrap
from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from email.message import EmailMessage, Message
from email.parser import BytesParser
from email.policy import default
from pathlib import Path

import duckdb


PROTOTYPE_BANNER = """PROTOTYPE: raw email CSV processing state.

Question: what is the smallest local-first parser/backfill loop that turns raw forwarded emails
into deduplicated CSV inputs for the analysis pipeline?

Default command against the checked-in real email sample:
    uv run python .scratch/basement-dampness-analysis/prototypes/19-raw-email-csv-processing-state.py

Folder command:
    uv run python .scratch/basement-dampness-analysis/prototypes/19-raw-email-csv-processing-state.py \\
        --raw-email-dir scratch/raw-emails \\
        --state-db scratch/ingest-state.duckdb \\
        --extracted-dir scratch/extracted-csv
"""

REQUIRED_SENSOR_COLUMNS = (
    "Time",
    "Temperature_Celsius",
    "Relative Humidity_Percent",
)
DEFAULT_DEMO_DIR = Path(".scratch/basement-dampness-analysis/prototypes/19-demo")
DEFAULT_REAL_RUN_DIR = Path(".scratch/basement-dampness-analysis/prototypes/19-real")


@dataclass(frozen=True)
class CsvValidationResult:
    status: str
    row_count: int
    reason: str


@dataclass(frozen=True)
class AttachmentResult:
    object_key: str
    message_id: str
    filename: str
    content_sha256: str
    status: str
    row_count: int
    reason: str
    extracted_path: Path | None


@dataclass(frozen=True)
class EmailResult:
    object_key: str
    message_id: str
    status: str
    reason: str
    attachment_results: tuple[AttachmentResult, ...]


def main(argv: Sequence[str] | None = None) -> None:
    parser = argparse.ArgumentParser(
        description="Prototype raw .eml CSV extraction and dedupe state."
    )
    parser.add_argument(
        "--raw-email-dir",
        type=Path,
        default=Path("data/email"),
        help="Directory of raw .eml files.",
    )
    parser.add_argument(
        "--state-db",
        type=Path,
        default=None,
        help="DuckDB file used as the prototype processing-state store.",
    )
    parser.add_argument(
        "--extracted-dir",
        type=Path,
        default=None,
        help="Directory where first-seen valid CSV attachments are written.",
    )
    parser.add_argument(
        "--object-key-prefix",
        default="local-eml",
        help="Prefix used to model the later S3 object key namespace.",
    )
    args = parser.parse_args(argv)

    print(PROTOTYPE_BANNER)

    raw_email_dir = args.raw_email_dir
    state_db = args.state_db or DEFAULT_REAL_RUN_DIR / "PROTOTYPE-real-email-state.duckdb"
    extracted_dir = args.extracted_dir or DEFAULT_REAL_RUN_DIR / "extracted-csv"

    state_db.parent.mkdir(parents=True, exist_ok=True)
    with duckdb.connect(str(state_db)) as connection:
        initialize_state(connection)
        first_pass_results = process_raw_email_dir(
            connection=connection,
            raw_email_dir=raw_email_dir,
            extracted_dir=extracted_dir,
            object_key_prefix=str(args.object_key_prefix).rstrip("/"),
        )
        print_results("First pass", first_pass_results)

        second_pass_results = process_raw_email_dir(
            connection=connection,
            raw_email_dir=raw_email_dir,
            extracted_dir=extracted_dir,
            object_key_prefix=str(args.object_key_prefix).rstrip("/"),
        )
        print_results("Second pass against same state", second_pass_results)
        print_state_summary(connection)


@dataclass(frozen=True)
class DemoPaths:
    raw_email_dir: Path
    state_db: Path
    extracted_dir: Path


def prepare_demo_inputs(keep_state: bool) -> DemoPaths:
    raw_email_dir = DEFAULT_DEMO_DIR / "raw-emails"
    state_db = DEFAULT_DEMO_DIR / "PROTOTYPE-ingest-state.duckdb"
    extracted_dir = DEFAULT_DEMO_DIR / "extracted-csv"

    if DEFAULT_DEMO_DIR.exists() and not keep_state:
        shutil.rmtree(DEFAULT_DEMO_DIR)

    raw_email_dir.mkdir(parents=True, exist_ok=True)
    extracted_dir.mkdir(parents=True, exist_ok=True)

    valid_csv = textwrap.dedent(
        """\
        Time,Temperature_Celsius,Relative Humidity_Percent
        2026/07/04 12:00,18.5,67.2
        2026/07/04 12:01,18.5,67.1
        """
    ).encode()
    changed_csv = textwrap.dedent(
        """\
        Time,Temperature_Celsius,Relative Humidity_Percent
        2026/07/05 12:00,18.2,66.8
        """
    ).encode()
    invalid_csv = textwrap.dedent(
        """\
        Time,Temperature_Celsius
        2026/07/06 12:00,18.0
        """
    ).encode()

    write_demo_email(
        raw_email_dir / "01-2026-07-04-original.eml",
        message_id="<xsense-20260704@example.test>",
        filename="Thermo-hygrometer_Export Data_202607041200.csv",
        attachment_bytes=valid_csv,
    )
    write_demo_email(
        raw_email_dir / "02-2026-07-04-forwarded-duplicate-message.eml",
        message_id="<xsense-20260704@example.test>",
        filename="renamed-by-forwarder.csv",
        attachment_bytes=changed_csv,
    )
    write_demo_email(
        raw_email_dir / "03-2026-07-05-same-content-new-message.eml",
        message_id="<xsense-20260705@example.test>",
        filename="another-name.csv",
        attachment_bytes=valid_csv,
    )
    write_demo_email(
        raw_email_dir / "04-2026-07-06-invalid-headers.eml",
        message_id="<xsense-20260706@example.test>",
        filename="bad-export.csv",
        attachment_bytes=invalid_csv,
    )
    return DemoPaths(raw_email_dir=raw_email_dir, state_db=state_db, extracted_dir=extracted_dir)


def write_demo_email(
    path: Path,
    message_id: str,
    filename: str,
    attachment_bytes: bytes,
) -> None:
    message = EmailMessage()
    message["From"] = "x-sense@example.test"
    message["To"] = "basement-ingest@example.test"
    message["Subject"] = "X-Sense daily CSV export"
    message["Message-ID"] = message_id
    message.set_content("Daily export attached.\n")
    message.add_attachment(
        attachment_bytes,
        maintype="text",
        subtype="csv",
        filename=filename,
    )
    path.write_bytes(message.as_bytes(policy=default))


def initialize_state(connection: duckdb.DuckDBPyConnection) -> None:
    connection.execute(
        """
        create table if not exists raw_emails (
            object_key varchar primary key,
            source_path varchar not null,
            content_sha256 varchar not null,
            message_id varchar not null,
            status varchar not null,
            reason varchar not null,
            first_seen_at timestamp not null
        )
        """
    )
    connection.execute(
        """
        create table if not exists email_messages (
            message_id varchar primary key,
            first_object_key varchar not null,
            first_seen_at timestamp not null
        )
        """
    )
    connection.execute(
        """
        create table if not exists csv_attachments (
            attachment_id varchar primary key,
            object_key varchar not null,
            message_id varchar not null,
            filename varchar not null,
            content_sha256 varchar not null,
            status varchar not null,
            row_count integer not null,
            reason varchar not null,
            extracted_path varchar,
            first_seen_at timestamp not null
        )
        """
    )


def process_raw_email_dir(
    connection: duckdb.DuckDBPyConnection,
    raw_email_dir: Path,
    extracted_dir: Path,
    object_key_prefix: str,
) -> tuple[EmailResult, ...]:
    results: list[EmailResult] = []
    extracted_dir.mkdir(parents=True, exist_ok=True)
    for email_path in sorted(raw_email_dir.glob("*.eml")):
        object_key = object_key_for(
            raw_email_dir=raw_email_dir,
            email_path=email_path,
            object_key_prefix=object_key_prefix,
        )
        results.append(
            process_raw_email(
                connection=connection,
                email_path=email_path,
                object_key=object_key,
                extracted_dir=extracted_dir,
            )
        )
    return tuple(results)


def object_key_for(raw_email_dir: Path, email_path: Path, object_key_prefix: str) -> str:
    relative_path = email_path.relative_to(raw_email_dir).as_posix()
    return f"{object_key_prefix}/{relative_path}"


def process_raw_email(
    connection: duckdb.DuckDBPyConnection,
    email_path: Path,
    object_key: str,
    extracted_dir: Path,
) -> EmailResult:
    now = datetime.now(UTC).replace(tzinfo=None)
    if scalar_exists(connection, "select true from raw_emails where object_key = ?", [object_key]):
        message_id = str(
            connection.execute(
                "select message_id from raw_emails where object_key = ?",
                [object_key],
            ).fetchone()[0]
        )
        return EmailResult(
            object_key=object_key,
            message_id=message_id,
            status="duplicate_object_key",
            reason="raw email object already processed",
            attachment_results=(),
        )

    raw_bytes = email_path.read_bytes()
    raw_sha256 = sha256_hex(raw_bytes)
    message = BytesParser(policy=default).parsebytes(raw_bytes)
    message_id = normalized_message_id(message, raw_sha256)

    if scalar_exists(connection, "select true from email_messages where message_id = ?", [message_id]):
        insert_raw_email(
            connection=connection,
            object_key=object_key,
            source_path=email_path,
            content_sha256=raw_sha256,
            message_id=message_id,
            status="duplicate_message_id",
            reason="Message-ID already seen; treat as duplicate forward",
            now=now,
        )
        return EmailResult(
            object_key=object_key,
            message_id=message_id,
            status="duplicate_message_id",
            reason="Message-ID already seen; treat as duplicate forward",
            attachment_results=(),
        )

    insert_raw_email(
        connection=connection,
        object_key=object_key,
        source_path=email_path,
        content_sha256=raw_sha256,
        message_id=message_id,
        status="processing",
        reason="new raw email object",
        now=now,
    )
    connection.execute(
        "insert into email_messages values (?, ?, ?)",
        [message_id, object_key, now],
    )

    attachment_results = tuple(
        process_csv_attachment(
            connection=connection,
            object_key=object_key,
            message_id=message_id,
            filename=filename,
            attachment_bytes=attachment_bytes,
            extracted_dir=extracted_dir,
            now=now,
        )
        for filename, attachment_bytes in csv_attachments(message)
    )
    final_status = "processed" if attachment_results else "no_csv_attachments"
    final_reason = (
        "processed CSV attachment candidates"
        if attachment_results
        else "message contained no CSV attachments"
    )
    connection.execute(
        "update raw_emails set status = ?, reason = ? where object_key = ?",
        [final_status, final_reason, object_key],
    )
    return EmailResult(
        object_key=object_key,
        message_id=message_id,
        status=final_status,
        reason=final_reason,
        attachment_results=attachment_results,
    )


def insert_raw_email(
    connection: duckdb.DuckDBPyConnection,
    object_key: str,
    source_path: Path,
    content_sha256: str,
    message_id: str,
    status: str,
    reason: str,
    now: datetime,
) -> None:
    connection.execute(
        "insert into raw_emails values (?, ?, ?, ?, ?, ?, ?)",
        [object_key, str(source_path), content_sha256, message_id, status, reason, now],
    )


def process_csv_attachment(
    connection: duckdb.DuckDBPyConnection,
    object_key: str,
    message_id: str,
    filename: str,
    attachment_bytes: bytes,
    extracted_dir: Path,
    now: datetime,
) -> AttachmentResult:
    content_sha256 = sha256_hex(attachment_bytes)
    attachment_id = f"{object_key}#{content_sha256[:16]}"

    validation = validate_sensor_csv(attachment_bytes)
    if validation.status != "valid":
        extracted_path = None
        status = validation.status
        reason = validation.reason
    elif scalar_exists(
        connection,
        "select true from csv_attachments where content_sha256 = ? and status = 'extracted'",
        [content_sha256],
    ):
        extracted_path = None
        status = "duplicate_content_hash"
        reason = "valid CSV bytes already extracted from another email"
    else:
        safe_name = safe_filename(filename)
        extracted_path = extracted_dir / f"{content_sha256[:16]}-{safe_name}"
        extracted_path.write_bytes(attachment_bytes)
        status = "extracted"
        reason = "first-seen valid CSV content"

    connection.execute(
        "insert into csv_attachments values (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        [
            attachment_id,
            object_key,
            message_id,
            filename,
            content_sha256,
            status,
            validation.row_count,
            reason,
            str(extracted_path) if extracted_path is not None else None,
            now,
        ],
    )
    return AttachmentResult(
        object_key=object_key,
        message_id=message_id,
        filename=filename,
        content_sha256=content_sha256,
        status=status,
        row_count=validation.row_count,
        reason=reason,
        extracted_path=extracted_path,
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
        if payload is None:
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
        )

    reader = csv.DictReader(decoded_text.splitlines())
    fieldnames = tuple(reader.fieldnames or ())
    missing_columns = [column for column in REQUIRED_SENSOR_COLUMNS if column not in fieldnames]
    if missing_columns:
        return CsvValidationResult(
            status="invalid_csv",
            row_count=0,
            reason=f"missing required columns: {', '.join(missing_columns)}",
        )

    row_count = 0
    for row in reader:
        row_count += 1
        for column in REQUIRED_SENSOR_COLUMNS:
            if row.get(column) in (None, ""):
                return CsvValidationResult(
                    status="invalid_csv",
                    row_count=row_count,
                    reason=f"row {row_count} has blank required column {column}",
                )
    return CsvValidationResult(status="valid", row_count=row_count, reason="valid sensor CSV")


def normalized_message_id(message: Message, raw_sha256: str) -> str:
    message_id = message.get("Message-ID")
    if message_id is None or not message_id.strip():
        return f"missing-message-id:{raw_sha256}"
    return message_id.strip()


def scalar_exists(
    connection: duckdb.DuckDBPyConnection,
    query: str,
    parameters: Sequence[object],
) -> bool:
    return connection.execute(query, parameters).fetchone() is not None


def sha256_hex(content: bytes) -> str:
    return hashlib.sha256(content).hexdigest()


def safe_filename(filename: str) -> str:
    cleaned = "".join(character if character.isalnum() or character in ".-_" else "_" for character in filename)
    return cleaned or "attachment.csv"


def print_results(title: str, results: Sequence[EmailResult]) -> None:
    print(f"== {title} ==")
    if not results:
        print("No .eml files found.\n")
        return
    for result in results:
        print(f"{result.status:24} {result.object_key} {result.message_id}")
        for attachment_result in result.attachment_results:
            output = attachment_result.extracted_path or "-"
            print(
                "  "
                f"{attachment_result.status:24} "
                f"rows={attachment_result.row_count:<3} "
                f"hash={attachment_result.content_sha256[:12]} "
                f"file={attachment_result.filename} "
                f"out={output}"
            )
            print(f"  reason: {attachment_result.reason}")
    print()


def print_state_summary(connection: duckdb.DuckDBPyConnection) -> None:
    print("== Persisted state summary ==")
    raw_rows = connection.execute(
        """
        select status, count(*) as rows
        from raw_emails
        group by status
        order by status
        """
    ).fetchall()
    attachment_rows = connection.execute(
        """
        select status, count(*) as rows, sum(row_count) as sensor_rows
        from csv_attachments
        group by status
        order by status
        """
    ).fetchall()
    print("raw_emails:")
    for status, rows in raw_rows:
        print(f"  {status}: {rows}")
    print("csv_attachments:")
    for status, rows, sensor_rows in attachment_rows:
        print(f"  {status}: {rows} attachments, {sensor_rows or 0} sensor rows")
    print()


if __name__ == "__main__":
    main()
