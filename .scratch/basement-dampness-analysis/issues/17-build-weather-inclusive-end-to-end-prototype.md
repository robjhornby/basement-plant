# Build weather-inclusive end-to-end prototype

Type: prototype
Status: open
Parent: ../map.md
Blocked by: 02, 09, 13, 14

## Question

What is the smallest local end-to-end prototype that loads the basement sensor CSVs, adds local weather/outdoor humidity data, runs the first useful calculations, and generates locally viewable static web pages quickly enough to support iterative modelling decisions?

Build this after the existing data/prototype assumptions are profiled, the Caversham weather source is chosen, the local static site views are defined, and the Python project baseline is in place. It should prioritize fast feedback from visible data and calculations over deep physical modelling. Use it to help decide later how much modelling sophistication is justified.

Use `data/basement_events.csv` as a first-class input. The prototype should overlay events on plots and calculate metrics within event-bounded periods rather than relying on the old inferred dehumidifier boundary or broad first/latest windows that cross fan, sensor-placement, and dehumidifier-orientation changes.

Use [Intervention, Room, And Device Context](../research/04-intervention-room-and-device-context.md) for sensor labels, room/device context, event-period definitions, and caveats to display or preserve in generated outputs.

Do not include SES, S3, Gmail forwarding, `robjhornby.com` publishing, Cloudflare Pages, AWS deployment, or server automation in this prototype. Those are later-phase work after the local CSV-to-static-site flow is useful.
