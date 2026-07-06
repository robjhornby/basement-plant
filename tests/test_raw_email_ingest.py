from __future__ import annotations

import json
from email.message import EmailMessage
from email.policy import default
from pathlib import Path
from typing import cast

from basement_analysis.raw_email_ingest import process_raw_email_batch, sha256_hex


def write_email(
    path: Path,
    message_id: str,
    attachment_bytes: bytes,
    filename: str = "Thermo-hygrometer_Export Data_20260703.csv",
) -> bytes:
    message = EmailMessage()
    message["From"] = "x-sense@example.test"
    message["To"] = "basement-ingest@example.test"
    message["Subject"] = "Your Temperature and Relative Humidity Data Export (Please Do Not Reply)"
    message["Message-ID"] = message_id
    message["Date"] = "Sat, 04 Jul 2026 11:25:35 +0000"
    message.set_content("Daily export attached.\n")
    message.add_attachment(
        attachment_bytes,
        maintype="application",
        subtype="octet-stream",
        filename=filename,
    )
    raw_bytes = message.as_bytes(policy=default)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(raw_bytes)
    return raw_bytes


def sensor_csv(raw_time: str = "2026/07/03 00:00") -> bytes:
    return "\n".join(
        [
            "Time,Temperature_Celsius,Relative Humidity_Percent",
            f"{raw_time},18.5,67.2",
            "2026/07/03 00:01,18.5,67.1",
        ]
    ).encode()


def test_ingest_emails_writes_r2_style_raw_csv_and_manifest_objects(tmp_path: Path) -> None:
    raw_email_dir = tmp_path / "downloaded-raw"
    source_path = raw_email_dir / "received_date=2026-07-04" / "sample.eml"
    attachment_bytes = sensor_csv()
    raw_bytes = write_email(source_path, "<xsense-20260704@example.test>", attachment_bytes)
    object_store_dir = tmp_path / "objects"

    results = process_raw_email_batch(
        raw_email_dir=raw_email_dir,
        object_store_dir=object_store_dir,
        raw_object_key_prefix="raw-emails/source=x-sense",
    )

    raw_sha256 = sha256_hex(raw_bytes)
    csv_sha256 = sha256_hex(attachment_bytes)
    assert [result.status for result in results] == ["accepted"]
    assert results[0].raw_object_key == (
        "raw-emails/source=x-sense/received_date=2026-07-04/sample.eml"
    )
    assert results[0].manifest_object_key == (
        f"manifests/ingest/source=x-sense/received_date=2026-07-04/raw_sha256={raw_sha256}.json"
    )

    assert (object_store_dir / results[0].raw_object_key).read_bytes() == raw_bytes
    csv_object_key = (
        "csv/source=x-sense/export_date=2026-07-03/"
        f"attachment_sha256={csv_sha256}/Thermo-hygrometer_Export_Data_20260703.csv"
    )
    assert (object_store_dir / csv_object_key).read_bytes() == attachment_bytes

    manifest = cast(
        dict[str, object],
        json.loads((object_store_dir / results[0].manifest_object_key).read_text(encoding="utf-8")),
    )
    assert manifest["status"] == "accepted"
    assert manifest["raw_object_key"] == results[0].raw_object_key
    attachments = cast(list[dict[str, object]], manifest["attachments"])
    assert attachments[0]["status"] == "extracted"
    assert attachments[0]["row_count"] == 2
    assert attachments[0]["csv_object_key"] == csv_object_key


def test_ingest_emails_uses_manifests_for_idempotence_and_content_dedupe(
    tmp_path: Path,
) -> None:
    raw_email_dir = tmp_path / "raw"
    first_csv = sensor_csv()
    write_email(raw_email_dir / "first.eml", "<xsense-first@example.test>", first_csv)
    object_store_dir = tmp_path / "objects"

    first_results = process_raw_email_batch(
        raw_email_dir=raw_email_dir,
        object_store_dir=object_store_dir,
    )
    second_results = process_raw_email_batch(
        raw_email_dir=raw_email_dir,
        object_store_dir=object_store_dir,
    )

    assert [result.status for result in first_results] == ["accepted"]
    assert [result.status for result in second_results] == ["duplicate_raw_sha256"]

    write_email(raw_email_dir / "second.eml", "<xsense-second@example.test>", first_csv)
    third_results = process_raw_email_batch(
        raw_email_dir=raw_email_dir,
        object_store_dir=object_store_dir,
    )

    assert [result.status for result in third_results] == [
        "duplicate_raw_sha256",
        "accepted",
    ]
    assert third_results[1].attachment_results[0].status == "duplicate_content_hash"
