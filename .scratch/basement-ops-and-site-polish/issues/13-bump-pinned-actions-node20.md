# Bump SHA-pinned workflow actions off deprecated Node 20

Type: task
Parent: ../map.md

## Question

Surfaced by the [Pipeline hygiene sweep](02-pipeline-hygiene-sweep.md) verification run: both
SHA-pinned actions (`actions/checkout` v4.3.1, `astral-sh/setup-uv` v5.4.2) target Node 20, which
GitHub Actions runners now force to Node 24 with a deprecation annotation on every run
(https://github.blog/changelog/2025-09-19-deprecation-of-node-20-on-github-actions-runners/).
Current upstream majors are `checkout` v7.0.0 and `setup-uv` v8.3.1.

Bump each to the current major's release, re-pin to the full commit SHA (verify against upstream
tag refs, keeping the `# vX.Y.Z` trailing comment), check the majors' breaking-change notes for
anything affecting this workflow (checkout v5+ default behaviors, setup-uv cache options), and
verify with a green `workflow_dispatch` run.

Small and independent — no blockers.
