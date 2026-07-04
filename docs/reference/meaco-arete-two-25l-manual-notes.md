# MeacoDry Arete Two 20L/25L Manual Notes

Source: official Meaco PDF, `Arete Two 20 / 25L`, downloaded from `https://www.meaco.de/atlantis-media/files/aretetwo-20l25l-manual-uk-150724.pdf`.

Local PDF copy: [aretetwo-20l25l-manual-uk-150724.pdf](aretetwo-20l25l-manual-uk-150724.pdf)

PDF metadata from local `pdfinfo` extraction:

- Created: `2024-07-15`
- Modified: `2024-08-29`
- Pages: 27
- Applies to: Arete Two 20L and 25L models

These notes contain stable manual facts only. Project-specific operating state, event vocabulary, and basement observations belong in the wayfinder issue tracker.

## Smart Humidity Mode

- Smart Humidity mode defaults to a `55% RH` target.
- The variable humidistat can be cycled through `70`, `65`, `60`, `55`, `50`, `45`, `40`, and continuous mode.
- At a normal RH target, the dehumidifier stops after reaching roughly `target - 3% RH`.
- Every 30 minutes, the fan runs to check humidity.
- If humidity rises more than `3% RH` above the target, the compressor starts again.
- If humidity is within `3% RH` of the target, the unit returns to sleep and checks again after another 30 minutes.
- Fan speed is automatic in this mode:
  - within `15% RH` of target: low fan speed
  - `15% RH` or more above target: medium fan speed

## Continuous Target

- In continuous target mode, the dehumidifier continues to run regardless of humidity level.
- In continuous target mode, it turns off only when the water tank is full.

## Smart Laundry Mode

- Smart Laundry mode uses a `35% RH` target and high fan speed.
- Smart Laundry mode runs for 6 hours, then turns off.
- If humidity reaches about `32% RH`, the compressor stops but the fan continues.
- The compressor restarts around `38% RH` while Smart Laundry mode is still active.

## Air Purification Mode

- Air Purification mode purifies without dehumidifying.
- Air Purification mode is entered by holding the Smart Humidity button.
- If an H13 HEPA filter is installed, the unit purifies while dehumidifying; it does not need to be in Air Purification mode for filtration to occur.

## Night Mode

- Night Mode reduces fan speed to low only if the unit is currently in high fan speed.
- Night Mode turns off display lights and button beeps.
- In Night Mode, tank-full beeps are suppressed.

## Timer

- The timer supports on/off timer values from 1 to 24 hours.

## Display And Indicators

- The display shows current humidity and target humidity when the dehumidifier is on.
- The dehumidifying indicator lights when the compressor is running.
- The dehumidifying indicator turns off while the unit is checking humidity and while defrosting.
- The air purification indicator lights when the dehumidifier is in Air Purification mode only.
- In standby, the WET indicator lights if relative humidity measures above `70% RH`.

## Tank Behaviour

- The 25L model has a `4.8 L` water tank.
- When the tank becomes full, the unit continues fan-only operation for about 3 minutes to clear water from the coils.
- After that fan-only period, the tank-full indicator lights and the unit beeps five times, except in Night Mode.
- The dehumidifier stops until the tank is emptied and reinserted.
- After the tank is emptied and reinserted, the unit resumes the previous mode.
- The tank float triggers the tank-full shutoff. The manual says the float must not be removed.

## Drainage

- The manual supports two water collection modes:
  - internal tank
  - continuous drainage through a standard garden hose using the supplied right-angle adaptor
- Continuous drainage requires a gravity drain path with no kinks, bends, or blockages.

## Airflow And Filters

- The louvre must be open during use.
- The H13 HEPA filter is optional.
- The unit can dehumidify without the H13 HEPA filter.
- Removing the H13 HEPA filter reduces noise by roughly 4-5 dB according to the manual.
- Dirty dust or HEPA filters can restrict airflow and reduce dehumidification.
- The dust filter should be cleaned at least every two weeks under regular use.
- The H13 HEPA filter should be replaced when it changes from white to grey; the manual gives roughly every 3 months as environment-dependent guidance.

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
