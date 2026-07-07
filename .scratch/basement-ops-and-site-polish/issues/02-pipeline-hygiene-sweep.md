# Pipeline hygiene sweep

Type: task
Parent: ../map.md
Status: claimed

## Question

Clear the small operational debts found in the 2026-07-07 review, none of which need a decision:

- Delete the stale `site/basement-site/` and `site/prototypes/container-analysis/` objects from
  the private `basement-pipeline` bucket (leftovers from the interim publication path; the
  dedicated `basement-site` bucket owns publication now). Keep raw/csv/manifests/parquet intact.
- Remove the commented-out revoked `cfat_` token line from the local `.envrc` (gitignored, but no
  reason to keep a dead credential string around).
- Pin the GitHub Actions workflow's third-party actions (`actions/checkout`, `astral-sh/setup-uv`)
  to full commit SHAs — the repo is public and the workflow holds R2 write credentials.
- Mitigate GitHub's 60-days-of-inactivity cron auto-disable for `basement-plant`: pick the
  lightest mechanism (e.g. a scheduled keepalive step that pushes a trivial commit or uses the
  workflow-enable API) and document it in the workflow file.

Resolve when the bucket listing shows no `site/` prefix, the `.envrc` line is gone, actions are
SHA-pinned with a green dispatch run, and the keepalive mechanism is in place and documented.
