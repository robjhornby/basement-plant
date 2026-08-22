from __future__ import annotations

import json
from datetime import UTC, date, datetime
from pathlib import Path

import pytest

from basement_analysis import hosted_curation
from basement_analysis.curated_dataset import load_curated_dataset, write_curated_dataset
from basement_analysis.event_store import EventType
from basement_analysis.hosted_curation import (
    accepted_csv_keys_from_manifest_texts,
    curate_accepted_email_csvs,
    merge_rain_readings,
    merge_weather_hours,
)
from basement_analysis.summaries import (
    Event as SummaryEvent,
)
from basement_analysis.summaries import (
    RainReading,
    SensorReading,
    WeatherHour,
    absolute_humidity_g_m3,
)
from basement_analysis.timezones import london_wall_clock_to_utc
from event_store_fixtures import write_event_store


def custom_event(*, timestamp: datetime, description: str) -> SummaryEvent:
    return SummaryEvent(timestamp=timestamp, event_type=EventType.custom, notes=description)


def _utc(raw_timestamp: str) -> datetime:
    """Canonical UTC instant from an ISO string — curated timestamps round-trip as UTC-aware."""
    return datetime.fromisoformat(raw_timestamp).replace(tzinfo=UTC)


def sensor_reading(
    raw_timestamp: str,
    location: str,
    temperature_c: float,
    relative_humidity_pct: float,
) -> SensorReading:
    return SensorReading(
        timestamp=_utc(raw_timestamp),
        location=location,
        temperature_c=temperature_c,
        relative_humidity_pct=relative_humidity_pct,
        absolute_humidity_g_m3=absolute_humidity_g_m3(temperature_c, relative_humidity_pct),
    )


def weather_hour(raw_timestamp: str, temperature_c: float = 16.0) -> WeatherHour:
    relative_humidity_pct = 70.0
    return WeatherHour(
        timestamp=_utc(raw_timestamp),
        temperature_c=temperature_c,
        relative_humidity_pct=relative_humidity_pct,
        dew_point_c=10.0,
        precipitation_mm=0.0,
        rain_mm=0.0,
        absolute_humidity_g_m3=absolute_humidity_g_m3(temperature_c, relative_humidity_pct),
    )


def manifest_json(status: str, attachment_status: str, attachment_object_key: str | None) -> str:
    return json.dumps(
        {
            "status": status,
            "attachments": [
                {"status": attachment_status, "attachment_object_key": attachment_object_key}
            ],
        }
    )


def write_manifest(
    object_store_dir: Path,
    *,
    received_date: str,
    name: str,
    status: str,
    attachment_status: str,
    attachment_object_key: str | None,
) -> None:
    manifest_path = (
        object_store_dir
        / "ingest"
        / "x-sense"
        / "outcomes"
        / f"received_date={received_date}"
        / f"{name}.json"
    )
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    manifest_path.write_text(
        manifest_json(status, attachment_status, attachment_object_key), encoding="utf-8"
    )


def csv_object_key(export_date: str, sha: str, filename: str) -> str:
    return f"ingest/x-sense/attachments/export_date={export_date}/sha256={sha}/{filename}"


def write_csv_object(object_store_dir: Path, object_key: str, rows: list[str]) -> None:
    csv_path = object_store_dir / object_key
    csv_path.parent.mkdir(parents=True, exist_ok=True)
    csv_path.write_text(
        "\n".join(["Time,Temperature_Celsius,Relative Humidity_Percent", *rows]),
        encoding="utf-8",
    )


def write_accepted_csv(
    object_store_dir: Path,
    *,
    export_date: str,
    received_date: str,
    sha: str,
    filename: str,
    rows: list[str],
) -> None:
    """Write one accepted CSV object and its accepting ingest manifest, R2-layout faithful."""
    object_key = csv_object_key(export_date, sha, filename)
    write_csv_object(object_store_dir, object_key, rows)
    write_manifest(
        object_store_dir,
        received_date=received_date,
        name=sha,
        status="accepted",
        attachment_status="extracted",
        attachment_object_key=object_key,
    )


def write_event_store_rows(root: Path, rows: list[str]) -> str:
    event_types = {
        "dehumidifier installed": EventType.dehumidifier_installed,
        "dehumidifer tank full": EventType.dehumidifier_tank_full,
    }
    events: list[SummaryEvent] = []
    for row in rows:
        raw_timestamp, description = row.split(",", maxsplit=1)
        event_type = event_types[description]
        events.append(
            SummaryEvent(
                timestamp=london_wall_clock_to_utc(
                    datetime.strptime(raw_timestamp, "%Y/%m/%d %H:%M:%S")
                ),
                event_type=event_type,
            )
        )
    return write_event_store(root, events)


def stub_weather(monkeypatch: pytest.MonkeyPatch) -> None:
    """Make the weather/rain fetches deterministic no-ops for sensor-focused tests."""

    def fake_weather(
        start_date: date, end_date: date, cache_dir: Path, refresh: bool
    ) -> list[WeatherHour]:
        return [weather_hour("2026-07-03T00:00:00")]

    def fake_rainfall(
        start_date: date, end_date: date, cache_dir: Path, refresh: bool
    ) -> list[RainReading]:
        return [RainReading(timestamp=_utc("2026-07-03T00:00:00"), rainfall_mm=0.0)]

    monkeypatch.setattr(hosted_curation, "fetch_open_meteo_weather", fake_weather)
    monkeypatch.setattr(hosted_curation, "fetch_environment_agency_rainfall", fake_rainfall)


def curated_sensor_rows(dataset_dir: Path) -> list[SensorReading]:
    return list(load_curated_dataset(dataset_dir).sensor_readings)


def test_weather_and_rain_fetch_from_their_own_recent_watermark(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # Sensor history reaches back to January, but the curated weather/rain only run to early
    # August. The fetches must start from each stream's own watermark minus OVERLAP_DAYS, not
    # from the January dataset start — otherwise the request re-scans the whole history every run.
    existing_dataset_dir = tmp_path / "existing-parquet"
    write_curated_dataset(
        dataset_dir=existing_dataset_dir,
        sensor_readings=[
            sensor_reading("2026-01-01T00:00:00", "Basement", 18.5, 67.2),
            sensor_reading("2026-08-08T00:00:00", "Basement", 18.5, 67.1),
        ],
        events=[],
        weather_hours=[
            weather_hour("2026-01-01T00:00:00"),
            weather_hour("2026-08-06T00:00:00"),
        ],
        rain_readings=[
            RainReading(timestamp=_utc("2026-01-01T00:00:00"), rainfall_mm=1.5),
            RainReading(timestamp=_utc("2026-08-07T00:00:00"), rainfall_mm=0.0),
        ],
    )

    events_glob = write_event_store_rows(
        tmp_path / "events", ["2026/07/01 21:00:00,dehumidifier installed"]
    )
    (tmp_path / "objects").mkdir()

    captured: dict[str, date] = {}

    def fake_open_meteo_weather(
        start_date: date, end_date: date, cache_dir: Path, refresh: bool
    ) -> list[WeatherHour]:
        captured["weather_start"] = start_date
        captured["weather_end"] = end_date
        return []

    def fake_environment_agency_rainfall(
        start_date: date, end_date: date, cache_dir: Path, refresh: bool
    ) -> list[RainReading]:
        captured["rain_start"] = start_date
        captured["rain_end"] = end_date
        return []

    monkeypatch.setattr(hosted_curation, "fetch_open_meteo_weather", fake_open_meteo_weather)
    monkeypatch.setattr(
        hosted_curation, "fetch_environment_agency_rainfall", fake_environment_agency_rainfall
    )

    curate_accepted_email_csvs(
        object_store_root=tmp_path / "objects",
        curated_dataset_dir=tmp_path / "curated",
        work_dir=tmp_path / "work",
        events_glob=events_glob,
        existing_curated_dataset_root=existing_dataset_dir,
        refresh_weather=False,
    )

    # weather watermark 2026-08-06 - OVERLAP_DAYS(2) = 2026-08-04; rain watermark 2026-08-07 - 2.
    assert captured["weather_start"] == date(2026, 8, 4)
    assert captured["rain_start"] == date(2026, 8, 5)
    assert captured["weather_end"] == date(2026, 8, 8)
    assert captured["rain_end"] == date(2026, 8, 8)


def test_accepted_csv_keys_from_manifest_texts_only_uses_extracted_accepted_attachments() -> None:
    manifest_texts = [
        manifest_json("accepted", "extracted", "ingest/x/attachments/a.csv"),
        manifest_json("rejected", "extracted", "ingest/x/attachments/b.csv"),
        manifest_json("accepted", "invalid_csv", None),
    ]

    assert accepted_csv_keys_from_manifest_texts(manifest_texts) == ("ingest/x/attachments/a.csv",)


def test_curate_accepted_email_csvs_merges_existing_parquet_and_staged_csvs(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    existing_dataset_dir = tmp_path / "existing-parquet"
    write_curated_dataset(
        dataset_dir=existing_dataset_dir,
        sensor_readings=[
            sensor_reading("2026-07-03T00:00:00", "Basement", 18.5, 67.2),
            sensor_reading("2026-07-03T00:01:00", "Basement", 18.5, 67.1),
            sensor_reading("2026-07-04T00:00:00", "Thermo-hygrometer_3", 20.0, 58.0),
        ],
        events=[
            custom_event(
                timestamp=_utc("2026-07-02T21:00:00"),
                description="Dehumidifier on",
            )
        ],
        weather_hours=[
            weather_hour("2026-06-01T00:00:00"),
            weather_hour("2026-07-03T00:00:00", temperature_c=16.0),
        ],
        rain_readings=[
            RainReading(timestamp=_utc("2026-06-01T00:00:00"), rainfall_mm=1.5),
            RainReading(timestamp=_utc("2026-07-03T00:00:00"), rainfall_mm=0.0),
        ],
    )

    events_glob = write_event_store_rows(
        tmp_path / "events",
        [
            "2026/07/01 21:00:00,dehumidifier installed",
            "2026/07/05 00:51:03,dehumidifer tank full",
        ],
    )

    object_store_dir = tmp_path / "objects"
    write_accepted_csv(
        object_store_dir,
        export_date="2026-07-04",
        received_date="2026-07-04",
        sha="abc123",
        filename="Thermo-hygrometer_2_Export_Data_20260704.csv",
        rows=[
            "2026/07/03 00:01,21.0,55.0",
            "2026/07/04 00:00,20.5,56.0",
        ],
    )

    def fake_open_meteo_weather(
        start_date: date,
        end_date: date,
        cache_dir: Path,
        refresh: bool,
    ) -> list[WeatherHour]:
        # The staged CSV rows are Europe/London wall-clock; "2026/07/03 00:01" is 2026-07-02
        # 23:01 UTC, so the merged UTC dataset now starts on 2026-07-02.
        assert start_date == date(2026, 7, 2)
        assert end_date == date(2026, 7, 4)
        assert cache_dir == tmp_path / "work" / "cache"
        assert refresh
        return [
            weather_hour("2026-07-03T00:00:00", temperature_c=17.5),
            weather_hour("2026-07-04T00:00:00"),
        ]

    def fake_environment_agency_rainfall(
        start_date: date,
        end_date: date,
        cache_dir: Path,
        refresh: bool,
    ) -> list[RainReading]:
        assert start_date == date(2026, 7, 2)
        assert end_date == date(2026, 7, 4)
        assert cache_dir == tmp_path / "work" / "cache"
        assert refresh
        return [
            RainReading(timestamp=_utc("2026-07-03T00:00:00"), rainfall_mm=0.4),
            RainReading(timestamp=_utc("2026-07-04T00:00:00"), rainfall_mm=0.2),
        ]

    monkeypatch.setattr(hosted_curation, "fetch_open_meteo_weather", fake_open_meteo_weather)
    monkeypatch.setattr(
        hosted_curation,
        "fetch_environment_agency_rainfall",
        fake_environment_agency_rainfall,
    )

    result = curate_accepted_email_csvs(
        object_store_root=object_store_dir,
        curated_dataset_dir=tmp_path / "curated",
        work_dir=tmp_path / "work",
        events_glob=events_glob,
        existing_curated_dataset_root=existing_dataset_dir,
        refresh_weather=True,
    )

    curated_dataset = load_curated_dataset(tmp_path / "curated")
    assert result.watermark == _utc("2026-07-04T00:00:00")
    assert result.accepted_csv_count == 1
    assert result.selected_csv_count == 1
    assert result.existing_sensor_row_count == 3
    assert result.staged_sensor_row_count == 2
    assert result.merged_sensor_row_count == 5
    assert result.event_count == 2
    # Events come from the JSON event store, not the stale carried-forward curated partition.
    assert [event.event_type for event in curated_dataset.events] == [
        EventType.dehumidifier_installed,
        EventType.dehumidifier_tank_full,
    ]
    assert {reading.location for reading in curated_dataset.sensor_readings} == {
        "Basement",
        "Bedroom",
        "Living room",
    }
    weather_by_timestamp = {hour.timestamp: hour for hour in curated_dataset.weather_hours}
    assert sorted(weather_by_timestamp) == [
        _utc("2026-06-01T00:00:00"),
        _utc("2026-07-03T00:00:00"),
        _utc("2026-07-04T00:00:00"),
    ]
    assert weather_by_timestamp[_utc("2026-07-03T00:00:00")].temperature_c == 17.5
    assert [
        (reading.timestamp, reading.rainfall_mm) for reading in curated_dataset.rain_readings
    ] == [
        (_utc("2026-06-01T00:00:00"), 1.5),
        (_utc("2026-07-03T00:00:00"), 0.4),
        (_utc("2026-07-04T00:00:00"), 0.2),
    ]


def test_curate_refreshes_curated_events_when_a_new_tank_full_line_is_logged(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    existing_dataset_dir = tmp_path / "existing-parquet"
    write_curated_dataset(
        dataset_dir=existing_dataset_dir,
        sensor_readings=[sensor_reading("2026-07-03T00:00:00", "Basement", 18.5, 67.2)],
        events=[
            custom_event(
                timestamp=_utc("2026-07-02T21:00:00"),
                description="stale seed event",
            )
        ],
        weather_hours=[weather_hour("2026-07-03T00:00:00")],
        rain_readings=[RainReading(timestamp=_utc("2026-07-03T00:00:00"), rainfall_mm=0.0)],
    )

    object_store_dir = tmp_path / "objects"
    write_accepted_csv(
        object_store_dir,
        export_date="2026-07-03",
        received_date="2026-07-03",
        sha="abc",
        filename="Thermo-hygrometer_Export_Data_20260703.csv",
        rows=["2026/07/03 00:01,18.5,67.1"],
    )
    stub_weather(monkeypatch)

    events_root = tmp_path / "events"
    events_glob = write_event_store_rows(events_root, ["2026/07/05 00:51:03,dehumidifer tank full"])

    def curate() -> list[str]:
        curate_accepted_email_csvs(
            object_store_root=object_store_dir,
            curated_dataset_dir=tmp_path / "curated",
            work_dir=tmp_path / "work",
            events_glob=events_glob,
            existing_curated_dataset_root=existing_dataset_dir,
            refresh_weather=False,
        )
        return [
            event.event_type.value for event in load_curated_dataset(tmp_path / "curated").events
        ]

    assert curate() == ["dehumidifier_tank_full"]

    # Appending a new tank-full line and re-running is the only manual step needed for the
    # hosted footer to see it.
    events_glob = write_event_store_rows(
        events_root,
        [
            "2026/07/05 00:51:03,dehumidifer tank full",
            "2026/07/11 01:46:29,dehumidifer tank full",
        ],
    )
    assert curate() == ["dehumidifier_tank_full", "dehumidifier_tank_full"]


def build_multi_day_object_store(object_store_dir: Path) -> None:
    """Five days of accepted Basement CSVs, one export per day, R2-layout faithful."""
    for day in range(1, 6):
        export_date = f"2026-07-0{day}"
        write_accepted_csv(
            object_store_dir,
            export_date=export_date,
            received_date=export_date,
            sha=f"sha{day}",
            filename=f"Thermo-hygrometer_Export_Data_2026070{day}.csv",
            rows=[f"2026/07/0{day} 00:00,18.{day},6{day}.0"],
        )


def test_incremental_run_matches_a_full_rebuild(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    stub_weather(monkeypatch)
    object_store_dir = tmp_path / "objects"
    build_multi_day_object_store(object_store_dir)
    empty_existing = tmp_path / "empty-existing"
    empty_existing.mkdir()

    # Full rebuild: cold-start (empty parquet) parses every accepted CSV.
    curate_accepted_email_csvs(
        object_store_root=object_store_dir,
        curated_dataset_dir=tmp_path / "full",
        work_dir=tmp_path / "work-full",
        events_glob=_events_glob(tmp_path),
        existing_curated_dataset_root=empty_existing,
        refresh_weather=False,
    )
    full_rows = curated_sensor_rows(tmp_path / "full")

    # Seed a parquet that already covers days 1-4 (itself a cold-start curation over a store that
    # only has those days), then run incrementally against the full store.
    partial_store = tmp_path / "partial-objects"
    for day in range(1, 5):
        export_date = f"2026-07-0{day}"
        write_accepted_csv(
            partial_store,
            export_date=export_date,
            received_date=export_date,
            sha=f"sha{day}",
            filename=f"Thermo-hygrometer_Export_Data_2026070{day}.csv",
            rows=[f"2026/07/0{day} 00:00,18.{day},6{day}.0"],
        )
    curate_accepted_email_csvs(
        object_store_root=partial_store,
        curated_dataset_dir=tmp_path / "seed",
        work_dir=tmp_path / "work-seed",
        events_glob=_events_glob(tmp_path),
        existing_curated_dataset_root=empty_existing,
        refresh_weather=False,
    )

    result = curate_accepted_email_csvs(
        object_store_root=object_store_dir,
        curated_dataset_dir=tmp_path / "incremental",
        work_dir=tmp_path / "work-incremental",
        events_glob=_events_glob(tmp_path),
        existing_curated_dataset_root=tmp_path / "seed",
        refresh_weather=False,
    )
    incremental_rows = curated_sensor_rows(tmp_path / "incremental")

    # The seed's newest CSV row "2026/07/04 00:00" (Europe/London) is 2026-07-03 23:00 UTC.
    assert result.watermark == _utc("2026-07-03T23:00:00")
    # cutoff = watermark.date()(2026-07-03) - OVERLAP_DAYS(2) = 2026-07-01, so all five days are
    # re-parsed (day 1 too, idempotently); the merge/dedup still matches a full rebuild.
    assert result.selected_csv_count == 5
    assert incremental_rows == full_rows


def test_selection_skips_csvs_older_than_the_cutoff(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    stub_weather(monkeypatch)
    object_store_dir = tmp_path / "objects"
    build_multi_day_object_store(object_store_dir)

    existing_dataset_dir = tmp_path / "existing"
    write_curated_dataset(
        dataset_dir=existing_dataset_dir,
        sensor_readings=[sensor_reading("2026-07-04T00:00:00", "Basement", 18.4, 64.0)],
        events=[],
        weather_hours=[],
        rain_readings=[],
    )

    result = curate_accepted_email_csvs(
        object_store_root=object_store_dir,
        curated_dataset_dir=tmp_path / "curated",
        work_dir=tmp_path / "work",
        events_glob=_events_glob(tmp_path),
        existing_curated_dataset_root=existing_dataset_dir,
        refresh_weather=False,
    )

    # watermark 2026-07-04 → cutoff 2026-07-02 → only days 2,3,4,5 parsed; day 1 skipped.
    assert result.watermark == _utc("2026-07-04T00:00:00")
    assert result.selected_csv_count == 4
    assert result.accepted_csv_count == 4


def test_second_incremental_run_with_no_new_csvs_is_a_no_op(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    stub_weather(monkeypatch)
    object_store_dir = tmp_path / "objects"
    build_multi_day_object_store(object_store_dir)
    empty_existing = tmp_path / "empty-existing"
    empty_existing.mkdir()

    curate_accepted_email_csvs(
        object_store_root=object_store_dir,
        curated_dataset_dir=tmp_path / "curated",
        work_dir=tmp_path / "work",
        events_glob=_events_glob(tmp_path),
        existing_curated_dataset_root=empty_existing,
        refresh_weather=False,
    )
    first_rows = curated_sensor_rows(tmp_path / "curated")

    curate_accepted_email_csvs(
        object_store_root=object_store_dir,
        curated_dataset_dir=tmp_path / "curated-2",
        work_dir=tmp_path / "work-2",
        events_glob=_events_glob(tmp_path),
        existing_curated_dataset_root=tmp_path / "curated",
        refresh_weather=False,
    )
    second_rows = curated_sensor_rows(tmp_path / "curated-2")

    assert second_rows == first_rows


def test_cold_start_empty_parquet_ingests_all_accepted_csvs(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    stub_weather(monkeypatch)
    object_store_dir = tmp_path / "objects"
    build_multi_day_object_store(object_store_dir)
    empty_existing = tmp_path / "empty-existing"
    empty_existing.mkdir()

    result = curate_accepted_email_csvs(
        object_store_root=object_store_dir,
        curated_dataset_dir=tmp_path / "curated",
        work_dir=tmp_path / "work",
        events_glob=_events_glob(tmp_path),
        existing_curated_dataset_root=empty_existing,
        refresh_weather=False,
    )

    assert result.watermark is None
    assert result.selected_csv_count == 5
    assert result.merged_sensor_row_count == 5


def test_rebuild_all_parses_every_accepted_csv_despite_a_watermark(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    stub_weather(monkeypatch)
    object_store_dir = tmp_path / "objects"
    build_multi_day_object_store(object_store_dir)

    existing_dataset_dir = tmp_path / "existing"
    write_curated_dataset(
        dataset_dir=existing_dataset_dir,
        sensor_readings=[sensor_reading("2026-07-05T00:00:00", "Basement", 18.5, 65.0)],
        events=[],
        weather_hours=[],
        rain_readings=[],
    )

    result = curate_accepted_email_csvs(
        object_store_root=object_store_dir,
        curated_dataset_dir=tmp_path / "curated",
        work_dir=tmp_path / "work",
        events_glob=_events_glob(tmp_path),
        existing_curated_dataset_root=existing_dataset_dir,
        refresh_weather=False,
        rebuild_all=True,
    )

    # A watermark exists (2026-07-05) but --rebuild-all ignores it: all five days re-parsed.
    assert result.watermark == _utc("2026-07-05T00:00:00")
    assert result.accepted_csv_count == 5
    assert result.selected_csv_count == 5


def test_non_accepted_manifest_excludes_its_csv(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    stub_weather(monkeypatch)
    object_store_dir = tmp_path / "objects"
    accepted_key = csv_object_key("2026-07-03", "good", "Thermo-hygrometer_Export_Data.csv")
    write_csv_object(object_store_dir, accepted_key, ["2026/07/03 00:00,18.0,60.0"])
    write_manifest(
        object_store_dir,
        received_date="2026-07-03",
        name="good",
        status="accepted",
        attachment_status="extracted",
        attachment_object_key=accepted_key,
    )
    rejected_key = csv_object_key("2026-07-03", "bad", "Thermo-hygrometer_Export_Data_2.csv")
    write_csv_object(object_store_dir, rejected_key, ["2026/07/03 00:00,99.0,99.0"])
    write_manifest(
        object_store_dir,
        received_date="2026-07-03",
        name="bad",
        status="rejected",
        attachment_status="extracted",
        attachment_object_key=rejected_key,
    )
    empty_existing = tmp_path / "empty-existing"
    empty_existing.mkdir()

    result = curate_accepted_email_csvs(
        object_store_root=object_store_dir,
        curated_dataset_dir=tmp_path / "curated",
        work_dir=tmp_path / "work",
        events_glob=_events_glob(tmp_path),
        existing_curated_dataset_root=empty_existing,
        refresh_weather=False,
    )

    assert result.accepted_csv_count == 1
    assert result.merged_sensor_row_count == 1


def _events_glob(tmp_path: Path) -> str:
    events_root = tmp_path / "events"
    if not events_root.exists():
        return write_event_store_rows(events_root, ["2026/07/01 21:00:00,dehumidifier installed"])
    return str(events_root / "year=*" / "*.json")


def test_merge_rain_readings_keeps_old_rows_and_prefers_fresh_on_conflict() -> None:
    existing = [
        RainReading(timestamp=_utc("2026-06-01T00:00:00"), rainfall_mm=1.5),
        RainReading(timestamp=_utc("2026-07-03T00:00:00"), rainfall_mm=0.0),
    ]
    fresh = [
        RainReading(timestamp=_utc("2026-07-03T00:00:00"), rainfall_mm=0.4),
        RainReading(timestamp=_utc("2026-07-04T00:00:00"), rainfall_mm=0.2),
    ]

    merged = merge_rain_readings([*existing, *fresh])

    assert merged == [
        RainReading(timestamp=_utc("2026-06-01T00:00:00"), rainfall_mm=1.5),
        RainReading(timestamp=_utc("2026-07-03T00:00:00"), rainfall_mm=0.4),
        RainReading(timestamp=_utc("2026-07-04T00:00:00"), rainfall_mm=0.2),
    ]


def test_merge_weather_hours_keeps_old_rows_and_prefers_fresh_on_conflict() -> None:
    existing = [
        weather_hour("2026-06-01T00:00:00"),
        weather_hour("2026-07-03T00:00:00", temperature_c=16.0),
    ]
    fresh = [
        weather_hour("2026-07-03T00:00:00", temperature_c=17.5),
        weather_hour("2026-07-04T00:00:00"),
    ]

    merged = merge_weather_hours([*existing, *fresh])

    assert [(hour.timestamp, hour.temperature_c) for hour in merged] == [
        (_utc("2026-06-01T00:00:00"), 16.0),
        (_utc("2026-07-03T00:00:00"), 17.5),
        (_utc("2026-07-04T00:00:00"), 16.0),
    ]
