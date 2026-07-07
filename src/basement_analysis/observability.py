from __future__ import annotations

import json
import logging
import time
from collections.abc import Generator, Mapping
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import cast

phase_logger = logging.getLogger("basement_analysis.phases")


@dataclass(frozen=True)
class PhaseTiming:
    name: str
    duration_seconds: float


@dataclass(frozen=True)
class CommandTimingRecord:
    """One CLI command's phase timings plus the counts it reported, as persisted JSON."""

    command: str
    recorded_at: str
    phases: tuple[PhaseTiming, ...]
    counts: Mapping[str, int]


class PhaseRecorder:
    """Record named wall-clock phase durations, logging each phase as it completes."""

    def __init__(self) -> None:
        self._timings: list[PhaseTiming] = []

    @contextmanager
    def phase(self, name: str) -> Generator[None]:
        started = time.perf_counter()
        phase_logger.info("phase=%s status=started", name)
        try:
            yield
        finally:
            duration_seconds = time.perf_counter() - started
            self._timings.append(PhaseTiming(name=name, duration_seconds=duration_seconds))
            phase_logger.info("phase=%s status=finished duration_s=%.3f", name, duration_seconds)

    @property
    def timings(self) -> tuple[PhaseTiming, ...]:
        return tuple(self._timings)


def configure_run_logging() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
    )


def utc_now_isoformat() -> str:
    return datetime.now(tz=UTC).isoformat(timespec="seconds")


def write_command_timing_record(
    timings_dir: Path,
    command: str,
    recorder: PhaseRecorder,
    counts: Mapping[str, int],
) -> Path:
    record_path = timings_dir / f"{command}.json"
    record_path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "command": command,
        "recorded_at": utc_now_isoformat(),
        "phases": [
            {"name": timing.name, "duration_seconds": round(timing.duration_seconds, 3)}
            for timing in recorder.timings
        ],
        "counts": dict(counts),
    }
    record_path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return record_path


def load_command_timing_records(timings_dir: Path) -> list[CommandTimingRecord]:
    if not timings_dir.is_dir():
        return []
    records: list[CommandTimingRecord] = []
    for record_path in sorted(timings_dir.glob("*.json")):
        raw_payload = cast(object, json.loads(record_path.read_text(encoding="utf-8")))
        if not isinstance(raw_payload, dict):
            raise ValueError(f"Timing record {record_path} is not a JSON object")
        payload = cast(dict[str, object], raw_payload)
        records.append(parse_command_timing_record(payload, source=record_path))
    return records


def parse_command_timing_record(payload: Mapping[str, object], source: Path) -> CommandTimingRecord:
    command = payload.get("command")
    recorded_at = payload.get("recorded_at")
    raw_phases = payload.get("phases")
    raw_counts = payload.get("counts")
    if not isinstance(command, str) or not isinstance(recorded_at, str):
        raise ValueError(f"Timing record {source} is missing command/recorded_at strings")
    if not isinstance(raw_phases, list) or not isinstance(raw_counts, dict):
        raise ValueError(f"Timing record {source} is missing phases/counts collections")

    phases: list[PhaseTiming] = []
    for raw_phase in cast(list[object], raw_phases):
        if not isinstance(raw_phase, dict):
            raise ValueError(f"Timing record {source} has a non-object phase entry")
        phase_values = cast(dict[str, object], raw_phase)
        name = phase_values.get("name")
        duration_seconds = phase_values.get("duration_seconds")
        if (
            not isinstance(name, str)
            or isinstance(duration_seconds, bool)
            or not isinstance(duration_seconds, int | float)
        ):
            raise ValueError(f"Timing record {source} has a malformed phase entry")
        phases.append(PhaseTiming(name=name, duration_seconds=float(duration_seconds)))

    counts: dict[str, int] = {}
    for key, value in cast(dict[object, object], raw_counts).items():
        if not isinstance(key, str) or isinstance(value, bool) or not isinstance(value, int):
            raise ValueError(f"Timing record {source} has a malformed counts entry")
        counts[key] = value

    return CommandTimingRecord(
        command=command,
        recorded_at=recorded_at,
        phases=tuple(phases),
        counts=counts,
    )


def write_build_info(
    build_info_path: Path,
    newest_sensor_reading: datetime,
    counts: Mapping[str, int],
    command_records: list[CommandTimingRecord],
) -> Path:
    """Persist the per-build freshness record the hosted pipeline publishes with the site."""
    payload = {
        "generated_at": utc_now_isoformat(),
        "newest_sensor_reading": newest_sensor_reading.isoformat(timespec="minutes"),
        "counts": dict(counts),
        "commands": [
            {
                "command": record.command,
                "recorded_at": record.recorded_at,
                "phases": [
                    {
                        "name": timing.name,
                        "duration_seconds": round(timing.duration_seconds, 3),
                    }
                    for timing in record.phases
                ],
                "counts": dict(record.counts),
            }
            for record in command_records
        ],
    }
    build_info_path.parent.mkdir(parents=True, exist_ok=True)
    build_info_path.write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    return build_info_path


def render_timings_markdown(
    command_records: list[CommandTimingRecord],
    build_info: Mapping[str, object] | None = None,
) -> str:
    """Render command timing records (and optional build info) as a markdown summary."""
    lines: list[str] = ["## Pipeline phase timings", ""]
    if not command_records:
        lines.append("No timing records found.")
    for record in command_records:
        total_seconds = sum(timing.duration_seconds for timing in record.phases)
        lines.extend(
            [
                f"### `{record.command}` ({total_seconds:.1f}s across timed phases)",
                "",
                "| Phase | Duration (s) |",
                "| --- | ---: |",
            ]
        )
        lines.extend(
            f"| {timing.name} | {timing.duration_seconds:.3f} |" for timing in record.phases
        )
        if record.counts:
            counts_text = ", ".join(
                f"{key}={value:,}" for key, value in sorted(record.counts.items())
            )
            lines.extend(["", f"Counts: {counts_text}"])
        lines.append("")

    if build_info is not None:
        lines.extend(["## Build info", ""])
        for key in ("generated_at", "newest_sensor_reading"):
            value = build_info.get(key)
            if isinstance(value, str):
                lines.append(f"- {key}: {value}")
        counts = build_info.get("counts")
        if isinstance(counts, dict):
            count_values = cast(dict[str, object], counts)
            lines.extend(
                f"- {key}: {value:,}"
                for key, value in sorted(count_values.items())
                if isinstance(value, int)
            )
        lines.append("")
    return "\n".join(lines)
