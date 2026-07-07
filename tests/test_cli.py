from __future__ import annotations

import json
import sys
from datetime import datetime
from pathlib import Path

import pytest

from basement_analysis import cli
from basement_analysis.curated_dataset import CuratedDataRoot
from basement_analysis.observability import PhaseRecorder, write_command_timing_record
from basement_analysis.static_site import BuildResult


def test_main_dispatches_subcommands_from_console_script_argv(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    monkeypatch.setattr(sys, "argv", ["basement", "curate-ingested-r2", "--help"])

    with pytest.raises(SystemExit) as exit_info:
        cli.main()

    assert exit_info.value.code == 0
    assert "Merge accepted X-Sense CSV objects" in capsys.readouterr().out


def test_build_site_command_writes_timing_record_and_build_info(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    timings_dir = tmp_path / "timings"
    prior_recorder = PhaseRecorder()
    with prior_recorder.phase("curate"):
        pass
    write_command_timing_record(
        timings_dir=timings_dir,
        command="curate-ingested-r2",
        recorder=prior_recorder,
        counts={"merged_sensor_row_count": 42},
    )

    def fake_build_static_site(
        data_dir: Path,
        output_dir: Path,
        refresh_weather: bool = False,
        curated_dataset_dir: CuratedDataRoot | None = None,
        rebuild_curated_dataset: bool = True,
        phase_recorder: PhaseRecorder | None = None,
    ) -> BuildResult:
        assert data_dir == Path("data")
        assert refresh_weather is False
        assert curated_dataset_dir == tmp_path / "curated"
        assert rebuild_curated_dataset is False
        if phase_recorder is not None:
            with phase_recorder.phase("render-site"):
                pass
        return BuildResult(
            index_path=output_dir / "index.html",
            report_path=output_dir / "physics-report.html",
            curated_dataset_dir=tmp_path / "curated",
            sensor_row_count=100,
            weather_hour_count=24,
            rain_reading_count=12,
            newest_sensor_reading=datetime.fromisoformat("2026-07-08T09:41:00"),
        )

    monkeypatch.setattr(cli, "build_static_site", fake_build_static_site)

    cli.main(
        [
            "build-site",
            "--reuse-curated",
            "--output-dir",
            str(tmp_path / "site"),
            "--curated-data-dir",
            str(tmp_path / "curated"),
            "--timings-dir",
            str(timings_dir),
        ]
    )

    build_timing = json.loads((timings_dir / "build-site.json").read_text(encoding="utf-8"))
    build_info = json.loads((tmp_path / "site" / "build-info.json").read_text(encoding="utf-8"))

    assert [phase["name"] for phase in build_timing["phases"]] == ["render-site"]
    assert build_info["newest_sensor_reading"] == "2026-07-08T09:41"
    assert build_info["counts"] == {
        "rain_reading_count": 12,
        "sensor_row_count": 100,
        "weather_hour_count": 24,
    }
    assert [record["command"] for record in build_info["commands"]] == [
        "build-site",
        "curate-ingested-r2",
    ]
