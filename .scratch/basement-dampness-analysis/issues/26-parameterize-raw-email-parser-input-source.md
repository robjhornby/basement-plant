# Parameterize raw email parser input source

Type: task
Status: resolved
Parent: ../map.md
Blocked by: 29

## Question

How should the raw-email parser/backfill command be changed so it can process raw `.eml` objects
from a local folder or R2-style object prefix instead of only the checked-in prototype sample path?

Use the Cloudflare storage layout from [Adopt Cloudflare-only email/R2/static-site pipeline](27-adopt-cloudflare-only-email-r2-static-site-pipeline.md)
as the remote source shape. Keep the command local-first and batch-oriented: it should be possible
to download a landed R2 object to disk and verify parsing before wiring direct R2 listing into the
production parser.

## Answer

Promote the useful raw-email parsing behavior from the prototype into the production package as a
local-first batch command:

```bash
uv run basement ingest-emails \
  --raw-email-dir data/email \
  --object-store-dir build/basement-ingest-objects
```

The implemented shape is:

- `src/basement_analysis/raw_email_ingest.py` owns raw `.eml` discovery, MIME parsing, CSV
  attachment validation, content hashing, object-key derivation, manifest writing, and idempotence
  state loaded from existing manifests.
- `uv run basement ingest-emails` recursively scans a local folder for `.eml` files. By default it
  prepends `raw-emails/source=x-sense` to local relative paths so a downloaded R2 prefix such as
  `received_date=2026-07-04/raw_sha256=...eml` can be verified locally with matching object keys.
- Passing `--raw-object-key-prefix ""` preserves the local relative path exactly, which covers the
  case where the input directory is already an object-store-root mirror.
- The command writes a local R2-shaped tree: raw email objects under `raw-emails/source=x-sense/`,
  accepted CSV attachments under
  `csv/source=x-sense/export_date=YYYY-MM-DD/attachment_sha256=<csv_sha256>/<safe_filename>.csv`,
  and ingest manifests under
  `manifests/ingest/source=x-sense/received_date=YYYY-MM-DD/raw_sha256=<raw_sha256>.json`.
- Idempotence is manifest/object based rather than DuckDB based: existing ingest manifests seed
  seen raw SHA-256 values, Message-IDs, and extracted CSV hashes before each batch. Duplicate raw
  bytes are skipped, duplicate Message-IDs are recorded as duplicate forwards, and duplicate CSV
  content is not re-extracted.
- `README.md` now documents the local backfill command and the R2-prefix-preserving mode.

Validation added in `tests/test_raw_email_ingest.py` covers recursive local input, R2-style raw CSV
and manifest object paths, manifest contents, duplicate raw-email reruns, and duplicate CSV content
handling.

Verification:

```bash
uv run ruff format --check .
uv run ruff check .
uv run pyright
uv run pytest
```
