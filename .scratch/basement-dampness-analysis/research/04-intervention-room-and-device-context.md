# Intervention, Room, And Device Context

This asset records user-confirmed context gathered while resolving [Confirm intervention and sensor placement timeline](../issues/04-confirm-intervention-and-sensor-placement-timeline.md). Use it as project-specific analysis context. Stable manufacturer/manual facts live separately in [MeacoDry Arete Two 20L/25L Manual Notes](../../../docs/reference/meaco-arete-two-25l-manual-notes.md), with the local PDF copy at [aretetwo-20l25l-manual-uk-150724.pdf](../../../docs/reference/aretetwo-20l25l-manual-uk-150724.pdf).

## Core Analytical Rules

- Use `data/basement_events.csv` as a first-class input.
- Treat `2026-07-01 21:00` as the confirmed physical dehumidifier setup time.
- Keep the sensor-observed drying transition around `2026-07-01 20:40` separate from the physical setup event.
- Split metrics by event-bounded periods before comparing averages, trends, rebound rates, or leak/rain signals.
- Do not compare broad "first 36 hours" and "latest 36 hours" windows as if they are equivalent; those windows cross sensor, fan, extractor, and dehumidifier-orientation changes.
- Manual visual observations are opportunistic. Absence of a visual event is not proof that no wet-floor or damp-patch condition occurred.
- Routine door opening, household activity, and indoor moisture generation will not be manually logged. Treat them as residual confounders unless the data clearly supports inference.

## Event-Bounded Periods

| Period label | Start | End | Notes |
| --- | --- | --- | --- |
| `carpeted_baseline` | dataset start | `2026-06-28 12:40` | Baseline before basement clearing. Extractor fan was running continuously. |
| `clearing_in_progress` | `2026-06-28 12:40` | `2026-06-28 16:20` | Household disturbance period. Avoid steady-state interpretation. |
| `bare_no_dehumidifier` | `2026-06-28 16:20` | `2026-07-01 21:00` | Best current pre-dehumidifier comparison period, but extractor fan remained on and weather still matters. |
| `dehumidifier_centre_no_fan_sensor_original` | `2026-07-01 21:00` | `2026-07-02 14:35` | First active drying/control-cycle period. Extractor turned off at the start. |
| `fan_added_sensor_move_transition` | `2026-07-02 14:35` | `2026-07-02 14:40` | Treat as intervention transition, not an analyzable regime. |
| `fan_on_sensor_near_extractor_original_orientation` | `2026-07-02 14:40` | `2026-07-02 18:30` | Sensor moved; compare cautiously with earlier periods. |
| `fan_on_sensor_near_extractor_intake_away_uncertain` | `2026-07-02 18:30` | `2026-07-02 21:00` | Approximate boundary; mark metrics provisional or sensitivity-test. |
| `fan_on_sensor_near_extractor_intake_toward_uncertain` | `2026-07-02 21:00` | dataset end | Latest known operating regime; boundary approximate. |

## Confirmed Timeline Events

| Time | Certainty | Event |
| --- | --- | --- |
| `2026-06-28 12:40` | known | Basement clearing started. |
| `2026-06-28 16:20` | known | Carpet, underlay, and carpet grippers removed; room left bare. Removed materials were taken outside over roughly an hour and did not linger indoors as a drying reservoir. |
| `2026-07-01 21:00` | known | Dehumidifier installed in centre of room; extractor fan turned off after continuous prior running; dehumidifier set to `50% RH`. |
| `2026-07-02 14:35` | known | Small circulation fan added. |
| `2026-07-02 14:40` | known | Basement thermohygrometer moved from East-wall radiator area to a box near the room centre/North side. |
| `2026-07-02 18:30` | uncertain | Dehumidifier rotated so the intake faced away from the wetter side; a box was moved and may have affected airflow. |
| `2026-07-02 21:00` | uncertain | Dehumidifier rotated so the intake faced the wetter side. |

## Dehumidifier Operating State

- Device: MeacoDry Arete Two 25L Dehumidifier and Air Purifier.
- Manual reference: [MeacoDry Arete Two 20L/25L Manual Notes](../../../docs/reference/meaco-arete-two-25l-manual-notes.md).
- Drainage mode: internal tank, not continuous drainage.
- Tank has not yet been emptied during the recorded period.
- Future tank-full observations and tank-empty actions should be recorded as separate timestamps when both are known.
- Tank-full time represents when extraction stopped.
- Tank-emptied time represents when extraction could resume.
- Future tank-empty events should include collected water volume when available; approximate litres are acceptable.
- Event logging should eventually support tank-full and tank-emptied events in the web interface.
- Current settings since setup: Smart Humidity mode, `50% RH` target, no timer, not Laundry mode, no Night Mode.
- Settings have not been changed since setup.
- Air purifier runs when the dehumidifier runs; it is not in always-purify-only mode.
- H13 HEPA filter has been installed since setup.
- Louvre has been open since setup; louvre openness has not changed.
- Whole-unit rotations are represented as dehumidifier-orientation events in `data/basement_events.csv`.

## Ventilation And Door State

- Before `2026-07-01 21:00`, the extractor fan was running continuously for the full sensor-data history.
- At `2026-07-01 21:00`, the extractor fan was turned off.
- The plan is to keep the extractor fan off for the duration of the project.
- If the extractor fan is turned on again, record it as an event.
- Extractor fan position: North wall, roughly `1.2 m` from the West wall.
- Extractor fan exhausts directly outdoors through its own duct path.
- Two passive vents connect directly outdoors through separate duct paths.
- The passive vents are always open and should be treated as fixed background ventilation, not events.
- Passive vent positions: one roughly `10 cm` west of the extractor fan, the other roughly `30 cm` east/right of the extractor fan.
- Basement door baseline: usually closed, with poor airflow around the door because it seals tightly against the carpet underneath.
- Door opening/closing will not be manually recorded.

## Geometry And Placement

- Room dimensions: approximately `3.12 m x 3.07 m` from a floorplan, including the stairwell.
- Ceiling height: approximately `1.83 m`.
- Approximate geometric air volume before correcting for stairwell/opening/contents: about `17.5 m3`.
- Placement measurements are approximate, updated using the known room size. More exact measurements may be added later if room modelling needs them.

Basement thermohygrometer:

- Before `2026-07-02 14:40`: sitting on top of a radiator on the East wall, right next to the wall, roughly `1 m` from the South wall and roughly `1 m` above the floor.
- After `2026-07-02 14:40`: sitting on a box near the middle of the room, closest to the North wall, roughly `1.2 m` from the North wall and roughly `1.3 m` from the West wall.
- The East-wall radiator used as the earlier sensor support is currently cold/off. It may be heated in winter, but that is not expected during this project.

Other thermohygrometers:

- `Thermo-hygrometer 2`: upstairs bedroom.
- `Thermo-hygrometer 3`: living room above the basement.
- Bedroom and living-room sensors are far from heat sources, windows, vents, and similar local confounders.
- Treat them as plausible indoor context/control sensors, but not perfect controls for all household activity.

Dehumidifier:

- Near the middle of the room, roughly `1.3 m` from the North wall and roughly `1.5 m` from the West wall.

Circulation fan:

- Added at `2026-07-02 14:35`.
- On continuously since addition.
- No speed change.
- No oscillation.
- Approximate position: `20 cm` from the East wall and `1.2 m` from the South wall.
- Direction: roughly `30 degrees` clockwise from North, meaning toward the East wall at a shallow angle.

## Room Contents And Moisture Reservoirs

- After carpet/underlay removal, room contents are two plastic boxes.
- No known wet items.
- No notable hygroscopic stored contents such as cardboard, fabric, timber, or soft materials.
- Removed carpet/underlay did not remain indoors as a drying reservoir.
- Main likely moisture reservoirs are walls, floor, air, and building fabric rather than stored contents.

## Moisture And Building-Fabric Observations

- Water was visible on the floor in the Northwest corner when the dehumidifier was added.
- That visible floor water has dried and has not reappeared.
- Walls are not obviously wet.
- There are a few very slightly damp areas near the floor.
- There are staining/light mould marks.
- Most previous damp/mould was in the carpet.
- Some salt/efflorescence is visible on the chimney breast halfway along the West wall.
- North wall appears to be the main wetness source, primarily in the East corner, with a smaller amount in the West corner.
- Low-confidence wall construction observation: North wall appears to be plasterboard with a waterproof membrane behind it, then a gap, then brick.
- East wall may be similar to the North wall.
- West and South walls may differ; the old non-functioning fireplace/chimney appears to have a thinner plaster layer, painted, with skirting around the bottom.
- These construction observations are useful qualitative context, not yet detailed model inputs.

## Known Non-Events And Caveats

- No plumbing work, visible leak, water-use anomaly, radiator/pipe work, appliance water issue, drain smell, puddle recurrence, damp-patch event, or building work is known between `2026-06-28` and the current analysis point.
- Historical building changes do not need to be backfilled now.
- Future building work should be loggable as an event.
- No unusual local weather or outdoor-condition event is known from memory for the current window.
- Weather should primarily come from public weather data.
- Manual weather events may be added only for notable local observations that public data might miss.
- Door state and household activity are intentionally not event-logged; treat them as residual confounders.
- Living-room and bedroom sensors are useful but imperfect indoor context sensors.

## Future Event Logging Guidance

Record state changes, not routine observations.

Short-term `data/basement_events.csv` events should support:

- `dehumidifier_tank_full`
- `dehumidifier_tank_emptied`
- `dehumidifier_target_rh_changed`
- `dehumidifier_mode_changed`
- `dehumidifier_timer_changed`
- `dehumidifier_drainage_changed`
- `dehumidifier_filter_changed`
- `dehumidifier_filter_cleaned`
- `dehumidifier_louvre_changed`
- `dehumidifier_orientation_changed`
- `extractor_fan_on`
- `extractor_fan_off`
- `circulation_fan_changed`
- `sensor_moved`
- `sensor_position_measured`
- `dehumidifier_position_measured`
- `building_work`
- `plumbing_work`
- `visible_leak_observed`
- `floor_water_observed`
- `floor_water_dried`
- `wall_damp_patch_observed`
- `mould_cleaned`
- `wetness_location_observed`
- `notable_local_weather_observed`

Suggested future fields:

- `event_time`
- `event_type`
- `event_label`
- `description`
- `timestamp_certainty`
- `affected_entities`
- `period_boundary`
- `source_file`
- `value`
- `unit`
- `notes`

Use `value` and `unit` for measurable event payloads such as collected tank water volume.
