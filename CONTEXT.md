# Basement Dampness Analysis

This context defines the language for analysing basement dampness from thermohygrometer data, physical moisture models, and supporting explanatory material.

## Language

**Measurement uncertainty**:
Quantitative uncertainty associated with measurements and values derived from them, propagated through calculations such as averages, fits, and rate estimates using calibration data or explicit estimates.
_Avoid_: Caveats, error bars without a stated basis

**Caveat**:
Qualitative explanatory text that states limitations, tradeoffs, missing inputs, or interpretation risks in the chosen analysis approach.
_Avoid_: Measurement uncertainty

**Steady-state leaking**:
Ongoing moisture ingress that continues independently of short-term weather events and competes with the basement's drying process.
_Avoid_: Leak, dampness

**Weather-related leaking**:
Moisture ingress whose timing or rate is materially associated with rain or other outdoor weather conditions.
_Avoid_: Rain correlation

**Basement drying**:
Reduction over time in stored moisture in the basement walls, floor, air, and contents after active drying begins, separate from any additional moisture ingress.
_Avoid_: Dampness improvement

**Dry baseline**:
Future target condition where event-bounded basement absolute humidity and relative humidity are stable near an acceptable level, rebound after dehumidifier off-cycles is low, visible floor water is absent, and damp-patch observations are not worsening.
_Avoid_: Dry, solved, no leak

**Whole-house humidity change**:
Change in basement humidity that is best explained by broader indoor or outdoor air conditions affecting multiple rooms, rather than by basement-specific moisture storage or ingress.
_Avoid_: House effect, background humidity

**Sensor-placement artifact**:
Apparent change in measured temperature or relative humidity caused by moving a sensor, changing nearby airflow, changing local heat exposure, or otherwise altering the sensor's microenvironment rather than the basement condition itself.
Analysis should prefer measures that are not sensitive to sensor placement, or apply placement-sensitive measures only within time windows where the sensor was not moved. Avoid trying to infer cause and effect across sensor moves.
_Avoid_: Sensor error, bad reading, cross-placement correction

**Dehumidifier control-cycle artifact**:
Short-term humidity and temperature pattern caused by the dehumidifier cycling, tank state, fan airflow, target-relative-humidity control, or orientation, rather than by a change in moisture ingress or stored basement moisture.
_Avoid_: Dehumidifier effect, drying signal

**Tank-full event**:
Moment when the dehumidifier's internal tank becomes full enough that water extraction may stop or the control behaviour changes.
_Avoid_: Tank emptied, dehumidifier off

**Tank-emptied event**:
Moment when the dehumidifier's internal tank is emptied and normal water extraction can resume if the unit had stopped or throttled because the tank was full.
_Avoid_: Tank full, maintenance

**STH51 thermohygrometer**:
The X-Sense temperature and relative-humidity sensor model that produced all three current CSV sensor datasets.
_Avoid_: Thermometer, hygrometer, generic sensor

**SBS50 base station**:
The X-Sense communication hub used by the STH51 thermohygrometers to connect and export data; it is not a temperature or relative-humidity measurement source in this dataset.
_Avoid_: Sensor, measuring device

**Manufacturer specification**:
Published model-level accuracy or operating information from the STH51 manual, used as evidence when sensor-specific calibration certificates are unavailable.
_Avoid_: Calibration certificate, measured calibration

**Ingest mailbox**:
Dedicated email recipient that receives forwarded X-Sense CSV emails for automation. It is separate from the user's personal mailbox and exists to hand messages to the ingestion pipeline.
_Avoid_: Personal inbox, Gmail account

**Raw email store**:
Private immutable storage of the full forwarded email objects before parsing, used as the audit trail and backfill source for CSV extraction.
_Avoid_: Dashboard data, normalized sensor table

**Processing state**:
Record of which raw email objects and attachments have already been parsed, including dedupe identifiers such as S3 object key, email `Message-ID`, and attachment content hash.
_Avoid_: Processed folder

**Static publication artifact**:
Generated public files such as HTML, PNG, and JSON that can be published without a live application server.
_Avoid_: Live dashboard, API server
