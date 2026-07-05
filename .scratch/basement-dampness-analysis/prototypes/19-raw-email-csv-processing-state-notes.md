# Raw Email CSV Processing State Prototype Notes

Prototype status: throwaway.

Question being clarified: what is the smallest local-first parser/backfill loop that turns raw
forwarded emails into deduplicated CSV inputs for the analysis pipeline?

This prototype has been rerun against the real sample email at
`data/email/Your Temperature and Relative Humidity Data Export (Please Do Not Reply).eml`.
Its conclusions are provisional until the feedback checkpoint decides whether this sample is
representative and whether the dedupe assumptions match the user's real Gmail/forwarding workflow.

One command:

```bash
uv run python .scratch/basement-dampness-analysis/prototypes/19-raw-email-csv-processing-state.py
```

## Prototype Decision To Review

Use a single idempotent batch command before provisioning SES/S3 automation:

```text
raw .eml objects -> email parser -> CSV attachment validator -> DuckDB ingest state
                 -> first-seen valid CSV attachment files -> existing analysis input path
```

The smallest useful state store is a local DuckDB file with three operational tables:

- `raw_emails`: one row per local file or later S3 object key.
- `email_messages`: one row per first-seen `Message-ID`.
- `csv_attachments`: one row per CSV attachment candidate, including content hash, validation
  status, row count, and extracted path when accepted.

This appears enough to support manual backfill, recoverable reruns, and later S3 listing without a
queue, Lambda, or live service. The next step is user review before infrastructure work treats this
as settled.

## Dedupe Rules

- S3/local object key is the idempotence boundary: if the same raw object is listed again, skip it.
- `Message-ID` should catch duplicate forwarded emails before attachments are extracted, but this
  still needs either a real duplicate/forwarded sample or explicit confirmation of the forwarding
  path.
- Attachment SHA-256 should catch renamed files or duplicate payloads even when the email has a new
  `Message-ID`; the real sample has not yet exercised that branch.
- Attachment filenames are only metadata. The extracted filename includes the content hash so
  changed names do not affect identity.

## CSV Validation

The first validation gate should inspect content, not naming. For the current X-Sense CSV shape,
the minimum required headers are:

- `Time`
- `Temperature_Celsius`
- `Relative Humidity_Percent`

Rows with missing required values should be rejected before becoming analysis inputs. The prototype
only validates shape and counts rows; production can later add timestamp parsing, numeric range
checks, sensor identity mapping, and event-window sanity checks.

## Verified Prototype Run

Command:

```bash
uv run python .scratch/basement-dampness-analysis/prototypes/19-raw-email-csv-processing-state.py
```

Observed real-email first pass:

- one real email dated `2026-07-04 11:25:35 +0000` was processed;
- the email contained three CSV attachments, all with content type `application/octet-stream`;
- the attachment filenames were:
  `Thermo-hygrometer_Export Data_20260703.csv`,
  `Thermo-hygrometer 2_Export Data_20260703.csv`, and
  `Thermo-hygrometer 3_Export Data_20260703.csv`;
- each attachment had the expected headers:
  `Time`, `Temperature_Celsius`, `Relative Humidity_Percent`;
- each attachment contained 1,440 sensor rows covering `2026-07-03 00:00` through
  `2026-07-03 23:59`;
- all three attachments were extracted.

Observed second pass:

- the same raw email was skipped by duplicate object key from persisted DuckDB state.

Persisted state summary from the verified run:

```text
raw_emails:
  processed: 1
csv_attachments:
  extracted: 3 attachments, 4320 sensor rows
```

## User Feedback Needed

- Is this sample representative: one daily email containing all three sensor CSV attachments?
- Are forwarded Gmail copies expected to preserve the original `Message-ID`, or should the parser
  assume forwarded copies may receive a new `Message-ID`?
- Do you want production ingestion to accept only this exact subject/attachment pattern, or should
  it stay tolerant of occasional filename and subject changes?

## Recommended Production Shape

1. Add a production `ingest` command only after the feedback checkpoint confirms or revises these
   assumptions.
2. Keep the first command manually runnable with local paths:
   `uv run basement ingest-emails --raw-email-dir ... --state-db ... --extracted-dir ...`.
3. Use the same state model for S3 by replacing local file discovery with an S3 object listing and
   preserving object keys as the raw-email identity.
4. Keep extracted raw CSV files private and treat the generated static site as the publication
   boundary.
5. Add production tests around object-key idempotence, duplicate `Message-ID`, duplicate content
   hash, missing headers, malformed rows, and multiple attachments per email.
