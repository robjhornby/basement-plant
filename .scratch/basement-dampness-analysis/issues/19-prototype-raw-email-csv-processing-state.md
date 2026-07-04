# Prototype raw email CSV processing state

Type: prototype
Status: open
Parent: ../map.md
Blocked by: 17

## Question

What is the smallest local-first parser/backfill loop that turns raw forwarded emails into deduplicated CSV inputs for the analysis pipeline?

This is later-phase ingestion work. Do not start it until the local CSV-to-static-site analysis is useful from existing local CSV files.

Prototype a `uv run` Python command that can read raw `.eml` files from a local folder and later S3, extract CSV attachments, validate content/headers, dedupe by S3 object key, email `Message-ID`, and attachment content hash, and persist processing state. Keep the parser tolerant of changing filenames, duplicate forwards, and irregular delivery time.
