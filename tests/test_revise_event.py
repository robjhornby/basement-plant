from __future__ import annotations

import json
import os
import subprocess
import sys
import uuid
from pathlib import Path

EVENT_ID = "01a0298f-83c8-7321-8efc-10e1d95c915e"
PROJECT_ROOT = Path(__file__).parents[1]
SCRIPT_PATH = PROJECT_ROOT / "scripts" / "revise_event.py"


def run_script(arguments: list[str], working_dir: Path) -> subprocess.CompletedProcess[str]:
    environment = os.environ.copy()
    environment["PYTHONPATH"] = str(PROJECT_ROOT / "src")
    return subprocess.run(
        [sys.executable, str(SCRIPT_PATH), *arguments],
        cwd=working_dir,
        env=environment,
        text=True,
        capture_output=True,
        check=False,
    )


def test_stages_update_record(tmp_path: Path) -> None:
    result = run_script(
        [
            "update",
            "--event-id",
            EVENT_ID,
            "--event-type",
            "custom",
            "--effective-at",
            "2026-08-22 14:30:45",
            "--notes",
            "Corrected observation",
            "--output-dir",
            str(tmp_path),
        ],
        tmp_path,
    )

    assert result.returncode == 0, result.stderr
    object_key = result.stdout.strip()
    payload = json.loads((tmp_path / object_key).read_text(encoding="utf-8"))
    assert payload["event_id"] == EVENT_ID
    assert uuid.UUID(payload["revision_id"]).version == 7
    assert payload["operation"] == "update"
    assert payload["effective_at"] == "2026-08-22T13:30:45Z"
    assert payload["source"] == {"workflow": "local-event-revision"}


def test_stages_delete_in_original_effective_year(tmp_path: Path) -> None:
    result = run_script(
        [
            "delete",
            "--event-id",
            EVENT_ID,
            "--event-type",
            "dehumidifier_tank_full",
            "--effective-year",
            "2026",
            "--output-dir",
            str(tmp_path),
        ],
        tmp_path,
    )

    assert result.returncode == 0, result.stderr
    object_key = result.stdout.strip()
    payload = json.loads((tmp_path / object_key).read_text(encoding="utf-8"))
    assert object_key.startswith("events/year=2026/")
    assert payload["operation"] == "delete"
    assert "effective_at" not in payload


def test_rejects_update_without_effective_time(tmp_path: Path) -> None:
    result = run_script(
        [
            "update",
            "--event-id",
            EVENT_ID,
            "--event-type",
            "dehumidifier_tank_full",
        ],
        tmp_path,
    )

    assert result.returncode == 2
    assert "--effective-at is required for updates" in result.stderr
