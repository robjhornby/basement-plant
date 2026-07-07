from __future__ import annotations

import json
import time
from datetime import datetime
from pathlib import Path

import pytest

from basement_analysis import cli
from basement_analysis.observability import (
    CommandTimingRecord,
    PhaseRecorder,
    PhaseTiming,
    load_command_timing_records,
    parse_command_timing_record,
    render_timings_markdown,
    write_build_info,
    write_command_timing_record,
)


def test_phase_recorder_records_phases_in_order_with_positive_durations() -> None:
    recorder = PhaseRecorder()

    with recorder.phase("first"):
        time.sleep(0.001)
    with recorder.phase("second"):
        time.sleep(0.001)

    assert [timing.name for timing in recorder.timings] == ["first", "second"]
    assert all(timing.duration_seconds > 0.0 for timing in recorder.timings)


def test_phase_that_raises_still_records_timing_and_reraises() -> None:
    recorder = PhaseRecorder()

    with pytest.raises(RuntimeError, match="boom"), recorder.phase("failing"):
        raise RuntimeError("boom")

    assert [timing.name for timing in recorder.timings] == ["failing"]
    assert recorder.timings[0].duration_seconds >= 0.0


def test_write_and_load_command_timing_record_round_trips_phases_and_counts(
    tmp_path: Path,
) -> None:
    recorder = PhaseRecorder()
    with recorder.phase("ingest"):
        time.sleep(0.001)
    with recorder.phase("curate"):
        time.sleep(0.001)

    write_command_timing_record(
        tmp_path,
        "curate-ingested-r2",
        recorder,
        {"accepted_csv_count": 3, "merged_sensor_row_count": 42},
    )

    records = load_command_timing_records(tmp_path)

    assert len(records) == 1
    record = records[0]
    assert record.command == "curate-ingested-r2"
    assert [timing.name for timing in record.phases] == ["ingest", "curate"]
    assert all(timing.duration_seconds >= 0.0 for timing in record.phases)
    assert record.counts == {"accepted_csv_count": 3, "merged_sensor_row_count": 42}


def test_load_command_timing_records_returns_empty_list_for_missing_directory(
    tmp_path: Path,
) -> None:
    assert load_command_timing_records(tmp_path / "missing") == []


def test_parse_command_timing_record_rejects_payload_missing_command(tmp_path: Path) -> None:
    payload: dict[str, object] = {
        "recorded_at": "2026-07-08T00:00:00+00:00",
        "phases": [],
        "counts": {},
    }

    with pytest.raises(ValueError, match="command"):
        parse_command_timing_record(payload, source=tmp_path / "record.json")


def test_parse_command_timing_record_rejects_non_numeric_phase_duration(tmp_path: Path) -> None:
    payload: dict[str, object] = {
        "command": "build-site",
        "recorded_at": "2026-07-08T00:00:00+00:00",
        "phases": [{"name": "ingest", "duration_seconds": "fast"}],
        "counts": {},
    }

    with pytest.raises(ValueError, match="malformed phase"):
        parse_command_timing_record(payload, source=tmp_path / "record.json")


def test_parse_command_timing_record_rejects_non_int_count(tmp_path: Path) -> None:
    payload: dict[str, object] = {
        "command": "build-site",
        "recorded_at": "2026-07-08T00:00:00+00:00",
        "phases": [],
        "counts": {"accepted_csv_count": 3.5},
    }

    with pytest.raises(ValueError, match="malformed counts"):
        parse_command_timing_record(payload, source=tmp_path / "record.json")


def test_write_build_info_persists_generated_at_freshness_counts_and_command_records(
    tmp_path: Path,
) -> None:
    build_info_path = tmp_path / "build-info.json"
    command_records = [
        CommandTimingRecord(
            command="curate-ingested-r2",
            recorded_at="2026-07-08T00:00:00+00:00",
            phases=(PhaseTiming(name="ingest", duration_seconds=1.2345),),
            counts={"accepted_csv_count": 3},
        )
    ]

    write_build_info(
        build_info_path,
        newest_sensor_reading=datetime.fromisoformat("2026-07-08T09:41:12"),
        counts={"sensor_reading_count": 100},
        command_records=command_records,
    )

    payload = json.loads(build_info_path.read_text(encoding="utf-8"))
    assert isinstance(payload["generated_at"], str)
    assert payload["newest_sensor_reading"] == "2026-07-08T09:41"
    assert payload["counts"] == {"sensor_reading_count": 100}
    assert payload["commands"] == [
        {
            "command": "curate-ingested-r2",
            "recorded_at": "2026-07-08T00:00:00+00:00",
            "phases": [{"name": "ingest", "duration_seconds": 1.234}],
            "counts": {"accepted_csv_count": 3},
        }
    ]


def test_render_timings_markdown_includes_heading_table_row_and_counts() -> None:
    command_records = [
        CommandTimingRecord(
            command="curate-ingested-r2",
            recorded_at="2026-07-08T00:00:00+00:00",
            phases=(PhaseTiming(name="ingest", duration_seconds=1.5),),
            counts={"accepted_csv_count": 3},
        )
    ]

    markdown = render_timings_markdown(command_records)

    assert "### `curate-ingested-r2`" in markdown
    assert "| ingest | 1.500 |" in markdown
    assert "Counts: accepted_csv_count=3" in markdown


def test_render_timings_markdown_includes_build_info_lines_when_passed() -> None:
    command_records = [
        CommandTimingRecord(
            command="curate-ingested-r2",
            recorded_at="2026-07-08T00:00:00+00:00",
            phases=(PhaseTiming(name="ingest", duration_seconds=1.5),),
            counts={},
        )
    ]
    build_info = {
        "generated_at": "2026-07-08T10:00:00+00:00",
        "newest_sensor_reading": "2026-07-08T09:41",
        "counts": {"sensor_reading_count": 100},
    }

    markdown = render_timings_markdown(command_records, build_info)

    assert "## Build info" in markdown
    assert "- generated_at: 2026-07-08T10:00:00+00:00" in markdown
    assert "- newest_sensor_reading: 2026-07-08T09:41" in markdown
    assert "- sensor_reading_count: 100" in markdown


def test_render_timings_markdown_reports_no_records_found_for_empty_input() -> None:
    markdown = render_timings_markdown([])

    assert "No timing records found." in markdown


def test_cli_timings_summary_prints_rendered_markdown(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    recorder = PhaseRecorder()
    with recorder.phase("ingest"):
        time.sleep(0.001)
    write_command_timing_record(tmp_path, "curate-ingested-r2", recorder, {"accepted_csv_count": 3})

    cli.main(["timings-summary", "--timings-dir", str(tmp_path)])

    output = capsys.readouterr().out
    assert "### `curate-ingested-r2`" in output
    assert "Counts: accepted_csv_count=3" in output
