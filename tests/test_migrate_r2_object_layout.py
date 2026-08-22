from __future__ import annotations

import json
import sys
from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path
from types import ModuleType


def load_migration_script() -> ModuleType:
    script_path = Path(__file__).parents[1] / "scripts" / "migrate_r2_object_layout.py"
    spec = spec_from_file_location("migrate_r2_object_layout", script_path)
    assert spec is not None and spec.loader is not None
    module = module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


migrated_object = load_migration_script().migrated_object


def test_migrates_outcome_and_embedded_keys() -> None:
    sha = "a" * 64
    attachment_sha = "b" * 64
    legacy_key = f"manifests/ingest/source=x-sense/received_date=2026-08-22/raw_sha256={sha}.json"
    record = {
        "status": "accepted",
        "received_date": "2026-08-22",
        "raw_sha256": sha,
        "raw_object_key": "legacy-message",
        "attachments": [
            {
                "status": "extracted",
                "csv_object_key": (
                    "csv/source=x-sense/export_date=2026-08-21/"
                    f"attachment_sha256={attachment_sha}/sensor.csv"
                ),
            }
        ],
    }

    new_key, content = migrated_object(legacy_key, json.dumps(record).encode())
    migrated = json.loads(content)

    assert new_key == f"ingest/x-sense/outcomes/received_date=2026-08-22/sha256={sha}.json"
    assert migrated["message_sha256"] == sha
    assert migrated["message_object_key"] == (
        f"ingest/x-sense/messages/received_date=2026-08-22/sha256={sha}.eml"
    )
    assert "raw_sha256" not in migrated
    assert migrated["attachments"][0]["attachment_object_key"] == (
        f"ingest/x-sense/attachments/export_date=2026-08-21/sha256={attachment_sha}/sensor.csv"
    )
