# Define dampness and leak hypotheses

Type: grilling
Status: resolved
Parent: ../map.md
Blocked by: 01, 02, 04

## Question

Which hypotheses should the analysis test, and what evidence would count for or against each one?

At minimum, distinguish basement drying after intervention, rain-correlated moisture ingress, constant low-rate moisture influx compatible with a pipe leak, whole-house humidity changes, sensor-placement artifacts, and dehumidifier control-cycle artifacts. Use `/domain-modeling` to capture any resolved domain vocabulary if the user confirms canonical terms.

Use [Intervention, Room, And Device Context](../research/04-intervention-room-and-device-context.md) as input. In particular, account for the extractor-fan shutdown, sensor move, fan addition, visible Northwest-corner floor water that dried and has not reappeared, North-wall wetness observations, tank-full/empty event semantics, and the decision not to manually log routine door or household-activity events.

## Answer

Use this canonical high-level hypothesis set for the first iterations:

- `Basement drying`
- `Dry baseline`
- `Weather-related leaking`
- `Steady-state leaking`
- `Whole-house humidity change`
- `Sensor-placement artifact`
- `Dehumidifier control-cycle artifact`

This ticket deliberately resolves the hypothesis vocabulary and first-pass evidence posture only. Later tickets should learn details iteratively from data, prototypes, and model failures rather than trying to exhaust every edge case up front.

Evidence thresholds:

- `Basement drying`: supported by event-bounded reductions in absolute humidity, relative humidity, rebound rate, and/or dehumidifier extraction demand after active drying begins. Current data may show progress toward dryness, not that the basement is already dry.
- `Dry baseline`: a future target state where basement absolute humidity and relative humidity are stable near an acceptable level, rebound after dehumidifier off-cycles is low, visible floor water is absent, and damp-patch observations are not worsening. The current dataset is not expected to prove this state has been reached.
- `Weather-related leaking`: supported by basement-specific moisture increase or slower drying after rainfall, with a plausible lag, stronger than changes in bedroom/living-room control sensors, and repeated across enough rain events to avoid one-off coincidence.
- `Steady-state leaking`: supported only provisionally when persistent rebound or extraction demand remains after accounting for intervention periods and dehumidifier cycles, is not mirrored by control-room sensors, and is not explained by rain timing. Call this "compatible with steady-state leaking", not "a pipe leak", without direct plumbing evidence.
- `Whole-house humidity change`: supported when basement, bedroom, and living-room sensors move in the same direction on a similar timescale, especially when local weather also explains the shift.
- `Sensor-placement artifact`: handle mainly by avoiding placement-sensitive measures across sensor moves. Prefer measures insensitive to sensor placement, or apply placement-sensitive measures only within windows where the sensor was not moved. Do not try to infer cause and effect across the `2026-07-02 14:40` move unless a later prototype shows that a specific measure is robust.
- `Dehumidifier control-cycle artifact`: treat short repeated post-dehumidifier RH/temperature cycles as operational/control behavior by default. Use them for operational insight, but do not interpret individual rebounds as new ingress unless they exceed normal cycle behavior within the same event-bounded period.

Working style decision surfaced while resolving this ticket: keep early wayfinding agile. Ask the user only for high-level facts that materially affect direction now; record obvious or reversible details as assumptions; defer depth until a later research, prototype, model, or dashboard ticket makes the detail consequential.
