# Confirm intervention and sensor placement timeline

Type: grilling
Status: resolved
Parent: ../map.md

## Question

What known household and measurement events need to be represented so the analysis does not mistake interventions for dampness physics?

Resolve by interviewing the user for exact or approximate timestamps for dehumidifier installation, dehumidifier moves, fan addition, sensor moves, door/window opening patterns, tank emptying or continuous drain behavior, target RH setting changes, unusual weather, and any plumbing or building work. Produce a proposed event vocabulary suitable for later CSV/database storage.

## Answer

The current intervention timeline is now represented in `data/basement_events.csv`. It has 7 rows, sorted by local timestamp, and includes two explicitly uncertain timestamps.

Known event timeline:

| Time | Certainty | Event interpretation |
| --- | --- | --- |
| `2026-06-28 12:40` | known | Basement clearing started. |
| `2026-06-28 16:20` | known | Carpet, underlay, and carpet grippers removed; room left bare, then a couple of boxes and a few other items were put back. |
| `2026-07-01 21:00` | known | Dehumidifier installed in the centre of the room; extractor fan turned off after having run continuously throughout the prior sensor-data history; dehumidifier set to `50% RH`. |
| `2026-07-02 14:35` | known | Small fan added to introduce airflow, pointing at the wall with the radiator. |
| `2026-07-02 14:40` | known | Temperature/humidity sensor moved from the wall with the radiator to a box near the extractor fan. |
| `2026-07-02 18:30` | uncertain | Dehumidifier rotated so the intake faced away from the wetter side of the room; a box was moved and may have affected airflow. |
| `2026-07-02 21:00` | uncertain | Dehumidifier rotated so the intake faced the wetter side of the room. |

Analytical consequence: the prototype's inferred `2026-07-01 18:25` boundary should no longer be used as the physical install time. Use `2026-07-01 21:00` as the human-confirmed dehumidifier intervention. The sensor-observed drying transition beginning around `2026-07-01 20:40` remains useful as a measured transition signature, but it should be described separately from the physical event timestamp.

The analysis should split data into event-bounded periods before comparing means, trends, rebound rates, or leak/rain signals:

| Period label | Start | End | Notes |
| --- | --- | --- | --- |
| `carpeted_baseline` | dataset start | `2026-06-28 12:40` | Baseline before clearing. |
| `clearing_in_progress` | `2026-06-28 12:40` | `2026-06-28 16:20` | Household disturbance period; avoid treating as steady-state dampness physics. |
| `bare_no_dehumidifier` | `2026-06-28 16:20` | `2026-07-01 21:00` | Best current pre-dehumidifier comparison period, though weather/outdoor humidity still matters. |
| `dehumidifier_centre_no_fan_sensor_original` | `2026-07-01 21:00` | `2026-07-02 14:35` | First active drying/control-cycle period. |
| `fan_added_sensor_move_transition` | `2026-07-02 14:35` | `2026-07-02 14:40` | Treat as an intervention transition, not an analyzable physical regime. |
| `fan_on_sensor_near_extractor_original_orientation` | `2026-07-02 14:40` | `2026-07-02 18:30` | Sensor placement has changed, so compare cautiously with earlier periods. |
| `fan_on_sensor_near_extractor_intake_away_uncertain` | `2026-07-02 18:30` | `2026-07-02 21:00` | Boundary times are approximate; metrics should be marked provisional or sensitivity-tested. |
| `fan_on_sensor_near_extractor_intake_toward_uncertain` | `2026-07-02 21:00` | dataset end | Boundary time is approximate; this is the latest known operating regime. |

For the next analysis implementation, `data/basement_events.csv` should be a first-class input. Event boundaries should be shown on plots, and period metrics should be calculated within homogeneous event periods. Do not compare "first 36 hours" against "latest 36 hours" as if those windows are equivalent; they cross fan, sensor-placement, and dehumidifier-orientation changes.

Proposed event vocabulary for later CSV/database storage:

- Event types: `room_clearance_started`, `floor_covering_removed`, `dehumidifier_installed`, `ventilation_changed`, `circulation_fan_added`, `sensor_moved`, `dehumidifier_orientation_changed`, `airflow_obstruction_changed`.
- Affected entities: `room_contents`, `floor_covering`, `dehumidifier`, `extractor_fan`, `circulation_fan`, `thermohygrometer`, `airflow_path`.
- Suggested fields: `event_time`, `event_type`, `event_label`, `description`, `timestamp_certainty`, `affected_entities`, `period_boundary`, `source_file`, `notes`.
- Timestamp certainty values: `known`, `approximate`, `uncertain`. The current CSV encodes uncertainty in text; a later normalized table should make it a structured field.

Still unknown and worth preserving as caveats: tank emptying or continuous-drain behavior, door/window opening patterns, exact dehumidifier model/settings beyond `50% RH`, unusual weather at the time, and whether any plumbing/building work occurred. These gaps should not block the next prototype, but they should remain caveats for leak/rain interpretation.

## Comments

Additional grilling produced a structured analysis context asset:

- [Intervention, Room, And Device Context](../research/04-intervention-room-and-device-context.md)

Use that asset for project-specific room geometry, sensor placement, dehumidifier operating state, ventilation assumptions, visible moisture observations, event-logging rules, and remaining caveats. Stable manufacturer/manual facts live separately in `docs/reference/meaco-arete-two-25l-manual-notes.md`, with the copied PDF at `docs/reference/aretetwo-20l25l-manual-uk-150724.pdf`.
