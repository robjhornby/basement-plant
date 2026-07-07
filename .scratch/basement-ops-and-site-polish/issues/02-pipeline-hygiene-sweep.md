# Pipeline hygiene sweep

Type: task
Parent: ../map.md
Status: resolved

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

## Comments

2026-07-08 progress (session claimed above):

- `.envrc`: revoked `cfat_` token line deleted. Done.
- Stale `site/` objects: listing confirmed exactly 4 objects (`site/basement-site/index.html`,
  `site/basement-site/physics-report.html`, `site/prototypes/container-analysis/index.html`,
  `site/prototypes/container-analysis/manifest.json`). Deletion was denied by the permission
  classifier (destructive storage op needs explicit user authorization). **Awaiting user
  go-ahead** — command: `aws s3 rm "s3://basement-pipeline/site/" --recursive --endpoint-url "$R2_ENDPOINT_URL"`.
- SHA-pinning + keepalive: implemented in `.github/workflows/basement-site.yml` —
  `actions/checkout@34e114876b0b11c390a56381ad16ebd13914f8d5 # v4.3.1`,
  `astral-sh/setup-uv@d4b2f3b6ecc6e67c4457f6d3e41ec42d3d0fcb86 # v5.4.2` (both SHAs verified
  against upstream tag refs), plus a keepalive step re-enabling the workflow via the Actions API
  each run (`actions: write` permission added). Committed on `main` locally and pushed as PR
  https://github.com/robjhornby/basement-plant/pull/1 (direct push to main was denied).
  **Awaiting user**: dispatch of the verification run was denied (production R2 write) — needs
  `gh workflow run basement-site.yml --ref workflow-hygiene` (or merge + dispatch on main).

## Answer

All four items done, 2026-07-08:

- **Stale bucket objects deleted** (with explicit user approval): the four objects under
  `site/basement-site/` and `site/prototypes/container-analysis/` are gone; `basement-pipeline`
  now lists only `csv/`, `manifests/`, `parquet/`, `raw-emails/`.
- **`.envrc`**: the commented-out revoked `cfat_` token line is removed.
- **Actions SHA-pinned**: `actions/checkout@34e114876b0b11c390a56381ad16ebd13914f8d5 # v4.3.1`
  and `astral-sh/setup-uv@d4b2f3b6ecc6e67c4457f6d3e41ec42d3d0fcb86 # v5.4.2`, both SHAs verified
  against upstream tag refs (setup-uv's v5 is an annotated tag, dereferenced to the commit).
- **Cron keepalive**: each run now re-enables the workflow via
  `gh api -X PUT .../actions/workflows/basement-site.yml/enable` with the built-in
  `${{ github.token }}` (`actions: write` added to workflow permissions), resetting GitHub's
  60-day public-repo auto-disable timer with no dummy commits. Documented in a comment in the
  workflow file.

Verification: green `workflow_dispatch` run
https://github.com/robjhornby/basement-plant/actions/runs/28905109989 (37s, full pipeline
including keepalive step). Landed on `main` via merged PR
https://github.com/robjhornby/basement-plant/pull/1 (commit `139c7eb`).

Surfaced follow-up (not part of this sweep): the run annotates that both pinned actions target
deprecated Node 20 (runners force Node 24) — current upstream majors are `checkout` v7 and
`setup-uv` v8. Filed as ticket 13.
