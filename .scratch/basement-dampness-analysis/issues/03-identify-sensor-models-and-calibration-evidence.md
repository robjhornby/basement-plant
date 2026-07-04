# Identify sensor models and calibration evidence

Type: grilling
Status: resolved
Parent: ../map.md

## Question

What exact X-Sense sensor models produced the CSVs, and what calibration or accuracy evidence is available for each sensor?

Resolve by asking the user for the model names, purchase/listing links, app/export details, and any certificates, manuals, datasheets, serial numbers, or calibration claims. If the user has no certificates, record that absence explicitly because it affects the uncertainty budget.

## Answer

The three CSV-producing thermohygrometers are all the same model: X-Sense `STH51` Smart Thermometer Hygrometer sensors, bought as a `3 Pack STH51 & 1 Base Station SBS50` kit.

Durable reference artifact:

- [X-Sense STH51 Manual Notes](../../../docs/reference/x-sense-sth51-manual-notes.md)

The local reference manual is now:

- [Manual_STH51_20240506.pdf](../../../docs/reference/Manual_STH51_20240506.pdf)

The decision for this map is that no sensor-specific calibration certificates are available for the three physical sensors. Later uncertainty work should therefore use manufacturer specifications from the maintained STH51 reference notes plus explicit estimated components for effects not covered by the manual.

Future ingestion note: daily CSV exports currently arrive in Gmail. The likely next ingestion design needs either Gmail auto-forwarding or another automated route from those emails into the eventual pipeline.
