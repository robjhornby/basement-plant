# R2 object layout follow-on

Status: implemented and verified in production on 2026-08-22.

## Live inventory before cleanup on 2026-08-22

`basement-pipeline` contains 298 objects (18,582,667 bytes) under five roots:

| Root | Objects | Bytes | Current contents |
| --- | ---: | ---: | --- |
| `raw-emails/` | 53 | 9,050,051 | Immutable received X-Sense messages, 6 July–22 August |
| `csv/` | 147 | 6,104,952 | First-seen extracted X-Sense attachments, 3 July–21 August export dates |
| `manifests/` | 53 | 114,691 | 50 ingest outcomes and 3 rejection outcomes |
| `events/` | 12 | 4,745 | Canonical immutable event revisions, all in `year=2026/` |
| `parquet/` | 33 | 3,308,228 | Derived sensor, weather, rainfall, and current-event datasets |

The derived datasets comprise 21 sensor-reading objects, 7 weather-hour objects, 3
rain-reading objects, and 2 event objects. The event objects are:

```text
parquet/events/source=local_manual/year=2026/month=06/part-00000.parquet
parquet/events/source=local_manual/year=2026/month=07/part-00000.parquet
```

There is no August event object because the 12 migrated events end on 29 July. The JSON event
store replaced the CSV as the source of truth; it did not replace this derived current-event
dataset.

The completed cleanup replaced both objects with the single 2,244-byte object below. Its 12 rows
were checked record for record against current state derived from the canonical JSON revisions.

```text
parquet/events/year=2026/part-00000.parquet
```

## Creation and consumption map

| Objects | Writers | Readers |
| --- | --- | --- |
| Received email messages | Email Worker; Python batch-ingest path | Audit/backfill; outcome records refer to their keys |
| Extracted sensor attachments | Email Worker; Python batch-ingest path | Outcome records; hosted curation reads accepted keys |
| Ingest/rejection outcomes | Email Worker; Python batch-ingest path | Hosted curation reads accepted outcomes; operators inspect rejections |
| Canonical event revisions | `basement log-event` + GitHub Action; migration and local revision scripts | DuckDB event-store queries; hosted and local curation |
| Derived analytical datasets | `write_curated_dataset`; GitHub Action sync | Incremental curation merge; static-site build; local analysis scripts |

The current layout is repeated across the Python ingest/curation code, the TypeScript Email
Worker, tests, workflow shell, and operator documentation. Embedded attachment keys in outcome
JSON make `csv/` a data contract, not merely a prefix that can be renamed in isolation.

## Recommended semantic layout

```text
ingest/
  x-sense/
    messages/received_date=YYYY-MM-DD/sha256=<raw-sha>.eml
    attachments/export_date=YYYY-MM-DD/sha256=<attachment-sha>/<safe-filename>.csv
    outcomes/received_date=YYYY-MM-DD/sha256=<raw-sha>.json

events/
  year=YYYY/<revision-id>.json

datasets/
  sensor-readings/source=x-sense/location=<location>/year=YYYY/month=MM/part-00000.parquet
  weather-hours/source=open-meteo/year=YYYY/month=MM/part-00000.parquet
  rain-readings/source=environment-agency/station=<station>/year=YYYY/month=MM/part-00000.parquet
  events/year=YYYY/part-00000.parquet
```

The roots name lifecycle/domain roles: ingest evidence, canonical owner-entered events, and
reproducible analytical datasets. File formats remain visible at the leaves, where they are
useful, but no root is named after a serialization. A single outcome tree is sufficient because
acceptance or rejection is an attribute of an ingest outcome, not a different kind of artifact.
The tiny current-event dataset has no source or month partition because neither helps pruning.

A domain-first alternative would put X-Sense, weather, rainfall, and events at the root. That
makes source ownership conspicuous, but scatters pipeline stages and gives every domain its own
ad hoc raw/derived vocabulary. The lifecycle-first layout above better matches how this bucket is
operated. Its main weakness is that `datasets/` remains a broad technical collection, albeit a
semantic one rather than a file-format name.

## Safe migration sequence

1. Put the key templates in one Python layout module and keep the TypeScript worker literals
   aligned through key-for-key contract tests.
2. Teach curation to read both legacy outcomes and new outcomes. New outcomes must refer to new
   attachment keys; old outcomes continue to refer to old attachment keys during transition.
3. Deploy the Email Worker and workflow together so new messages and datasets use the new roots.
4. Copy historical messages and attachments, generate equivalent outcome records with updated
   embedded keys, and prove row/event equivalence through a full rebuild.
5. Switch readers to the new-only layout, then delete the four legacy roots only after a final
   inventory proves no live writer has recreated them.

This repository's current workflow commits are still local. Moving the bucket-wide roots before
that deployment would be temporary: the live Email Worker and daily GitHub Action would recreate
the legacy layout. The same warning applies to the event cleanup already performed: the deployed
daily workflow can recreate the legacy monthly event objects until the local commits are pushed.
