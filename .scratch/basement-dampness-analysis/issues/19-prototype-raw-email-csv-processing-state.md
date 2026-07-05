# Prototype raw email CSV processing state

Type: prototype
Status: resolved
Parent: ../map.md
Blocked by: 23

## Question

What is the smallest local-first parser/backfill loop that turns raw forwarded emails into deduplicated CSV inputs for the analysis pipeline?

This is later-phase ingestion work. Do not start it until [Assess local site usefulness before ingestion](23-assess-local-site-usefulness-before-ingestion.md) confirms that the local CSV-to-static-site analysis is useful enough to justify shifting attention to ingestion.

Prototype a `uv run` Python command that can read raw `.eml` files from a local folder and later S3, extract CSV attachments, validate content/headers, dedupe by S3 object key, email `Message-ID`, and attachment content hash, and persist processing state. Keep the parser tolerant of changing filenames, duplicate forwards, and irregular delivery time.

## Answer

Use a single idempotent batch command before provisioning SES/S3 automation, but treat this as a
prototype result pending user feedback rather than a settled infrastructure requirement:

`raw .eml objects -> email parser -> CSV attachment validator -> DuckDB ingest state -> first-seen valid CSV attachment files -> existing analysis input path`

Prototype artifact: [raw email CSV processing state](../prototypes/19-raw-email-csv-processing-state.py).

Decision notes: [Raw Email CSV Processing State Prototype Notes](../prototypes/19-raw-email-csv-processing-state-notes.md).

The smallest useful processing state appears to be a local DuckDB file with `raw_emails`,
`email_messages`, and `csv_attachments` tables. That should be enough to support manual backfill,
recoverable reruns, and later S3 listing without adding a queue, Lambda, or live service, but the
next ticket must confirm the conclusion with the user before infrastructure work proceeds.

Dedupe should use all three identities:

- object key: skip a raw local/S3 object already processed;
- `Message-ID`: skip duplicate forwarded emails before extraction, if the real forwarding path
  preserves a useful message identity;
- attachment SHA-256: skip duplicate payloads even when filenames or email metadata change.

The first CSV validation gate should inspect content, not filenames. The real sample attachments
arrive as `application/octet-stream`, not `text/csv`, so filename/content validation must remain
tolerant. For the current X-Sense CSV shape, require `Time`, `Temperature_Celsius`, and
`Relative Humidity_Percent`, reject missing required values, and record invalid attachments in
state. Production can later add timestamp parsing, numeric range checks, sensor identity mapping,
and event-window sanity checks.

Verified command:

```bash
uv run python .scratch/basement-dampness-analysis/prototypes/19-raw-email-csv-processing-state.py
```

The verified real-email run processed
`data/email/Your Temperature and Relative Humidity Data Export (Please Do Not Reply).eml`,
extracted three CSV attachments, and counted 1,440 sensor rows per attachment. The attachment
filenames were the three expected `Thermo-hygrometer...20260703.csv` variants, and all three used
the required headers. A second pass skipped the same raw email by object key from persisted DuckDB
state.

What remains unproven is duplicate-forward handling and duplicate-content handling with real
emails. Those should be treated as design assumptions until the user provides a duplicate/forwarded
sample or confirms the expected Gmail forwarding behaviour.
