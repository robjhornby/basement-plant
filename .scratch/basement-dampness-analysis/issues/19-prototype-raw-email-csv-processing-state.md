# Prototype raw email CSV processing state

Type: prototype
Status: claimed
Parent: ../map.md
Blocked by: 23

## Question

What is the smallest local-first parser/backfill loop that turns raw forwarded emails into deduplicated CSV inputs for the analysis pipeline?

This is later-phase ingestion work. Do not start it until [Assess local site usefulness before ingestion](23-assess-local-site-usefulness-before-ingestion.md) confirms that the local CSV-to-static-site analysis is useful enough to justify shifting attention to ingestion.

Prototype a `uv run` Python command that can read raw `.eml` files from a local folder and later S3, extract CSV attachments, validate content/headers, dedupe by S3 object key, email `Message-ID`, and attachment content hash, and persist processing state. Keep the parser tolerant of changing filenames, duplicate forwards, and irregular delivery time.
