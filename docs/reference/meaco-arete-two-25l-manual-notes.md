# MeacoDry Arete Two 25L Manual Notes

Source: official Meaco PDF, `Arete Two 20 / 25L`, downloaded from `https://www.meaco.de/atlantis-media/files/aretetwo-20l25l-manual-uk-150724.pdf`.

PDF metadata from local `pdfinfo` extraction:

- Created: `2024-07-15`
- Modified: `2024-08-29`
- Pages: 27
- Applies to: Arete Two 20L and 25L models

This is an analysis reference, not a full copy of the manual. Use the PDF as the source of truth for safety, maintenance, warranty, and app setup instructions.

## Confirmed Device

Project device:

- Model: MeacoDry Arete Two 25L Dehumidifier and Air Purifier
- Drainage mode in this basement project: internal tank, not continuous drainage
- Active user setting: Smart Humidity mode, `50% RH` target
- Timer: not used
- Laundry mode: not used
- Air purification: H13 HEPA purification occurs while the dehumidifier is running if the HEPA filter is installed; the unit is not being run in always-purify-only mode.

## Analysis-Relevant Controls

Smart Humidity mode:

- The default target is `55% RH`, but the variable humidistat can be cycled through `70`, `65`, `60`, `55`, `50`, `45`, `40`, and continuous mode.
- At a normal RH target, the dehumidifier stops after reaching roughly `target - 3% RH`.
- Every 30 minutes, the fan runs to check humidity.
- If humidity rises more than `3% RH` above the target, the compressor starts again.
- If humidity is within `3% RH` of the target, the unit returns to sleep and checks again after another 30 minutes.
- Fan speed is automatic in this mode:
  - within `15% RH` of target: low fan speed
  - `15% RH` or more above target: medium fan speed

Continuous target:

- Runs regardless of humidity target and stops only when the water tank is full.
- This project is not currently using continuous mode.

Smart Laundry mode:

- Uses `35% RH` target and high fan speed.
- Runs for 6 hours, then turns off.
- If humidity reaches about `32% RH`, the compressor stops but the fan continues; the compressor restarts around `38% RH`.
- This project is not currently using laundry mode.

Air Purification mode:

- Purifies without dehumidifying.
- Entered by holding the Smart Humidity button.
- This project is not currently using purifier-only mode.

Night mode:

- Reduces fan speed to low only if currently high.
- Turns off display lights and button beeps.
- Should be recorded if used, because it changes fan/control behaviour.

Timer:

- Supports on/off timer values from 1 to 24 hours.
- This project is not currently using a timer.

## Tank Behaviour

The 25L model has a `4.8 L` water tank.

When the tank becomes full:

- the unit continues fan-only operation for about 3 minutes to clear water from the coils;
- the tank-full indicator lights and the unit beeps five times, except in Night Mode;
- the dehumidifier stops until the tank is emptied and reinserted;
- after the tank is emptied and reinserted, the unit resumes the previous mode.

Analysis consequence:

- `dehumidifier_tank_full` and `dehumidifier_tank_emptied` are intervention events.
- Tank-full periods can look like real moisture rebound because water extraction has stopped.
- Tank-empty events can look like drying resuming.
- The project should record both timestamps when known.

## Drainage

The manual supports two water collection modes:

- internal tank
- continuous drainage through a standard garden hose using the supplied right-angle adaptor

Continuous drainage requires a gravity drain path with no kinks, bends, or blockages.

Project state:

- continuous drainage is not currently used.
- if continuous drainage is adopted later, record it as an event because tank-full shutdowns would no longer apply.

## Airflow And Filters

Manual-relevant airflow points:

- The louvre should be open during use.
- The H13 HEPA filter is optional.
- If a H13 HEPA filter is installed, the unit purifies while dehumidifying.
- Removing the HEPA filter reduces noise by roughly 4-5 dB according to the manual.
- Dirty dust or HEPA filters can reduce dehumidification by restricting airflow.
- The dust filter should be cleaned regularly; the manual says at least every two weeks under regular use.

Analysis consequence:

- Filter removal/replacement/cleaning can change airflow and apparent drying rate.
- H13 HEPA installed versus removed should be recorded if it changes during the project.
- Louvre position changes should be recorded if they are deliberate and persistent.

## 25L Specifications

Manual specification values for the 25L model:

| Property | Value |
| --- | --- |
| Dimensions | `618 x 366 x 272 mm` |
| Net weight | `16.1 kg` |
| Extraction at `27 C`, `60% RH` | `15 L/day` |
| Extraction at `30 C`, `80% RH` | `25 L/day` |
| Noise, low fan | `40 dB` |
| Noise, medium fan | `42 dB` |
| Noise, high fan | `50 dB` |
| Power consumption | `290 W` |
| Airflow, low fan | `150 m3/hour` |
| Airflow, medium fan | `175 m3/hour` |
| Airflow, high fan | `255 m3/hour` |
| Auto-restart | yes |
| Power supply | `220-240 V`, `50 Hz` |
| Operating temperature | `5 C` to `35 C` |
| Refrigerant | `R290 / 90 g` |
| Water tank size | `4.8 L` |

## Event Types To Support

Add or preserve these event types in the project event vocabulary:

- `dehumidifier_model_confirmed`
- `dehumidifier_mode_changed`
- `dehumidifier_target_rh_changed`
- `dehumidifier_timer_changed`
- `dehumidifier_tank_full`
- `dehumidifier_tank_emptied`
- `dehumidifier_drainage_changed`
- `dehumidifier_filter_changed`
- `dehumidifier_filter_cleaned`
- `dehumidifier_louvre_changed`
- `dehumidifier_night_mode_changed`

## Remaining Manual-Related Unknowns

- Whether the H13 HEPA filter is currently installed.
- Whether the louvre is open and whether its direction changed during the recorded period.
- Whether Night Mode has ever been used during the project period.
- Whether the Meaco app has useful event history or telemetry that could reduce manual logging.
