# Build weather-inclusive end-to-end prototype

Type: prototype
Status: open
Parent: ../map.md
Blocked by: 02, 09, 14

## Question

What is the smallest end-to-end prototype that loads the basement sensor data, adds local weather/outdoor humidity data, runs the first useful calculations, and shows the results in plots/tables quickly enough to support iterative modelling decisions?

Build this after the existing data/prototype assumptions are profiled, the Caversham weather source is chosen, and the Python project baseline is in place. It should prioritize fast feedback from visible data and calculations over deep physical modelling. Use it to help decide later how much modelling sophistication is justified.

Use `data/basement_events.csv` as a first-class input. The prototype should overlay events on plots and calculate metrics within event-bounded periods rather than relying on the old inferred dehumidifier boundary or broad first/latest windows that cross fan, sensor-placement, and dehumidifier-orientation changes.
