# Establish physics model scope and equations

Type: research
Status: resolved
Parent: ../map.md
Blocked by: 01, 02

## Question

What physics should the first defensible analysis model include, and what equations, units, and assumptions should be used?

Review the prototype absolute-humidity calculation and identify the minimum model needed for report values: relative humidity, temperature, saturation vapor pressure, absolute humidity or vapor density, dew point if useful, room air volume if useful, moisture mass balance, dehumidifier extraction, ventilation/air exchange, and wall/floor moisture storage. Produce a markdown asset that separates settled physics from assumptions that need user input.

Use [Intervention, Room, And Device Context](../research/04-intervention-room-and-device-context.md) for approximate room dimensions, effective air-volume caveats, dehumidifier/tank behaviour, ventilation paths, and qualitative moisture-reservoir observations.

## Answer

Research asset: [Physics Model Scope And Equations](../research/06-physics-model-scope-and-equations.md)

The first defensible model should be a small vapour-pressure-based psychrometric core: derive saturation vapour pressure, vapour pressure, absolute humidity / vapour density, and optional dew point from each temperature/RH reading, then compute event-bounded summaries and rates. Absolute humidity should remain the main cross-temperature moisture metric; RH should be retained for device-control, comfort, and mould-risk context.

The prototype's absolute-humidity calculation is physically sound for a first pass, but production code should use named units and documented Magnus constants from a primary source. Use room air volume only for scale checks, because the air itself contains tens to hundreds of grams of water while the dehumidifier/tank scale is litres. Keep ventilation, dehumidifier removal, steady-state leaking, weather-related leaking, and wall/floor reservoir release in the conceptual mass balance, but do not fit those physical rates until weather, ventilation, tank-volume, and event data can constrain them.

No new tickets were added from this resolution. The open weather, uncertainty, leak-strategy, and prototype tickets already cover the next sharp questions.
