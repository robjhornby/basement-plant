from __future__ import annotations

import json
import uuid
from pathlib import Path

import pytest

from basement_analysis import cli


def test_log_event_writes_create_record_and_prints_object_key(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("GITHUB_REPOSITORY", "owner/basement")
    monkeypatch.setenv("GITHUB_WORKFLOW", "Log basement event")
    monkeypatch.setenv("GITHUB_RUN_ID", "123456789")
    monkeypatch.setenv("GITHUB_SHA", "abcdef123456")

    cli.main(
        [
            "log-event",
            "--effective-at",
            "2026-08-22 14:30:45",
            "--event-type",
            "dehumidifier_tank_full",
            "--notes",
            "Tank light came on",
        ]
    )

    object_key = capsys.readouterr().out.strip()
    record_path = tmp_path / object_key
    payload = json.loads(record_path.read_text(encoding="utf-8"))

    assert record_path.parent.parent.name == "events"
    assert object_key == f"events/year=2026/{payload['revision_id']}.json"
    assert uuid.UUID(payload["event_id"]).version == 7
    assert uuid.UUID(payload["revision_id"]).version == 7
    assert payload["operation"] == "create"
    assert payload["effective_at"] == "2026-08-22T13:30:45Z"
    assert payload["event_type"] == "dehumidifier_tank_full"
    assert payload["data"] == {"notes": "Tank light came on"}
    assert payload["source"] == {
        "repository": "owner/basement",
        "workflow": "Log basement event",
        "run_id": "123456789",
        "git_sha": "abcdef123456",
    }


def test_log_event_omits_empty_optional_fields(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.chdir(tmp_path)
    for variable in ("GITHUB_REPOSITORY", "GITHUB_WORKFLOW", "GITHUB_RUN_ID", "GITHUB_SHA"):
        monkeypatch.delenv(variable, raising=False)

    cli.main(
        [
            "log-event",
            "--effective-at",
            "2026-12-22 14:30:45",
            "--event-type",
            "dehumidifier_tank_emptied",
        ]
    )

    object_key = capsys.readouterr().out.strip()
    payload = json.loads((tmp_path / object_key).read_text(encoding="utf-8"))
    assert payload["data"] == {}
    assert payload["source"] == {}


@pytest.mark.parametrize(
    ("arguments", "message"),
    [
        (
            [
                "--effective-at",
                "2026-08-22 14:30",
                "--event-type",
                "dehumidifier_tank_full",
            ],
            "invalid parse_event_effective_at value",
        ),
        (
            [
                "--effective-at",
                "2026-08-22 14:30:45",
                "--event-type",
                "tank_full",
            ],
            "invalid EventType value",
        ),
        (
            [
                "--effective-at",
                "2026-08-22 14:30:45",
                "--event-type",
                "custom",
                "--notes",
                "   ",
            ],
            "--notes is required and must be non-empty for custom events",
        ),
    ],
)
def test_log_event_rejects_invalid_input(
    arguments: list[str],
    message: str,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    monkeypatch.chdir(tmp_path)

    with pytest.raises(SystemExit, match="2"):
        cli.main(["log-event", *arguments])

    assert message in capsys.readouterr().err
    assert not (tmp_path / "events").exists()
