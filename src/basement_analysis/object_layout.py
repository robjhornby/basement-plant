from __future__ import annotations

from datetime import date

INGEST_SOURCE = "x-sense"
INGEST_OUTCOME_GLOB = f"ingest/{INGEST_SOURCE}/outcomes/**/*.json"
DATASETS_PREFIX = "datasets"


def message_object_key(received_date: date, content_sha256: str) -> str:
    return (
        f"ingest/{INGEST_SOURCE}/messages/received_date={received_date.isoformat()}/"
        f"sha256={content_sha256}.eml"
    )


def attachment_object_key(export_date: date, content_sha256: str, filename: str) -> str:
    return (
        f"ingest/{INGEST_SOURCE}/attachments/export_date={export_date.isoformat()}/"
        f"sha256={content_sha256}/{filename}"
    )


def outcome_object_key(received_date: date, content_sha256: str) -> str:
    return (
        f"ingest/{INGEST_SOURCE}/outcomes/received_date={received_date.isoformat()}/"
        f"sha256={content_sha256}.json"
    )
