# Bump SHA-pinned workflow actions off deprecated Node 20

Type: task
Parent: ../map.md
Status: resolved

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

## Answer

Merged as [PR #3](https://github.com/robjhornby/basement-plant/pull/3)
(main commit `a5d5992`) on 2026-07-09. `actions/checkout` bumped v4.3.1 → v7.0.0
(`9c091bb21b7c1c1d1991bb908d89e4e9dddfe3e0`) and `astral-sh/setup-uv` v5.4.2 → v8.3.2
(`11f9893b081a58869d3b5fccaea48c9e9e46f990`, a patch newer than the v8.3.1 named in the
question); both SHAs verified against upstream `git/ref/tags` (both tags point straight at
commits). Breaking-change review found nothing affecting this schedule/dispatch-only workflow:
checkout v5 Node 24 (hosted runners fine), v6 creds-file change (no checkout options used),
v7 fork-PR blocking (no PR triggers); setup-uv v6 opt-in venv activation (workflow uses
`uv run`), v7 `server-url` removal (unused), v8 manifest/tag changes (unused, SHA-pinned).
Verified with a green `workflow_dispatch` run on the branch
([run 28982204175](https://github.com/robjhornby/basement-plant/actions/runs/28982204175),
1m1s, zero annotations — the Node 20 deprecation notice is gone).
