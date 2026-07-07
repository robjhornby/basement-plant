# Assess pipeline efficiency from measured timings

Type: research
Parent: ../map.md
Blocked by: 03
Status: resolved

## Question

With real per-phase timings in hand (issue 03), decide whether any efficiency work is worth
doing, and specify it if so.

Context: the nightly run is a deliberate full rebuild — every accepted CSV is re-downloaded and
re-parsed, all existing parquet rows are re-read from R2, everything is merged in a Python dict,
and the whole parquet tree is rewritten and synced with `--delete`. That is simple and currently
takes ~1 minute end to end. The user's standing preference (map Notes) is measure-first: only fix
what timings show to be slow, and "loading minimum required data for each step" is the direction
if work is warranted. Natural seams if needed later: month-partition-level rewrites, skipping
CSV downloads already reflected in parquet, avoiding the full-history Open-Meteo refetch.

Resolve with a short written assessment (linked markdown or the answer itself): where the time
actually goes locally and hosted, which (if any) optimizations clear the bar at current and
projected data volumes (~180k rows now, +~3k/day), and either "no work warranted yet, revisit at
X" or new specified task tickets for the worthwhile fixes. Graduate the corresponding fog either
way.

## Answer

Resolved 2026-07-08. **No pipeline-efficiency implementation ticket is warranted yet.** Keep the
simple full-rebuild design until the hosted run has materially grown; revisit when either the
GitHub Actions wall clock exceeds 3 minutes for three consecutive scheduled runs, or the timed
Python phases exceed 90 seconds, or the sensor dataset reaches roughly 2 million rows (around
June 2027 at the current 4,320 rows/day three-sensor cadence).

The row-count assumption in the original ticket is stale: the verified hosted run already had
583,981 sensor rows on 2026-07-07, not ~180k. That does not change the decision, because the
measured full rebuild is still comfortably small.

### Measured timings

Hosted `workflow_dispatch` run
[`28905833847`](https://github.com/robjhornby/basement-plant/actions/runs/28905833847) completed
in 42s wall clock. Timed Python phases totaled 20.902s:

| Command | Phase | Duration (s) | Assessment |
| --- | --- | ---: | --- |
| `curate-ingested-r2` | load-existing-curated-parquet | 6.020 | R2/network full-history read; real cost but acceptable |
| `curate-ingested-r2` | fetch-environment-agency-rainfall | 5.155 | External API latency; required refresh window |
| `curate-ingested-r2` | write-curated-parquet | 0.864 | Not a bottleneck |
| `curate-ingested-r2` | merge-sensor-readings | 0.389 | Not a bottleneck |
| `build-site` | load-curated-parquet | 7.107 | Second R2 full-history read; largest single Python phase |
| `build-site` | build-summary | 0.478 | Not a bottleneck |
| `build-site` | render-site + write-site | 0.032 | Not a bottleneck |

The uninstrumented remainder of the 42s run is setup, `aws s3 sync`/`cp`, and workflow overhead.
That means Python-only optimization can save at most part of an already-short run.

Local timing records from `build/ticket-03-timings-fresh` show the same code path without the
hosted R2 tax:

| Command | Timed total | Largest phases |
| --- | ---: | --- |
| `curate-ingested-r2` | 7.343s | local Parquet load 3.560s, EA rainfall fetch 2.284s |
| `build-site --reuse-curated` | 0.917s | local Parquet load 0.615s, summary build 0.279s |

The local curated Parquet tree is only about 2.4 MiB across 28 files, and the mirrored accepted CSV
objects for the fresh run are about 376 KiB across 9 files. The data is not large enough yet for
partition-incremental machinery to pay for itself.

### Optimization candidates considered

**Month-partition-level Parquet rewrites:** reject for now. It would add correctness-sensitive
merge and delete behavior across partition boundaries to save less than a second of local write
time and only part of a 6s hosted full-history read. This becomes reasonable when full-history
loads dominate the run for consecutive days, not at 42s wall clock.

**Skipping accepted CSV downloads already reflected in Parquet:** reject. The current accepted
CSV mirror is tiny; staging and parsing cost 0.081s locally for 9 CSVs / 12,960 staged rows. The
workflow-level sync is uninstrumented, but the object set is too small to justify manifest
state-tracking complexity.

**Avoiding full-history Open-Meteo refetch:** reject. Open-Meteo took 0.308s locally and 0.740s in
the hosted timing sample, and the history merge from issue 01 preserves old rows. This is not a
meaningful cost.

**Narrowing the Environment Agency rainfall request:** defer. EA latency is visible and variable
(2.284s local fresh timing, 5.155s hosted sample, 7.645s in an earlier cached/local record), but
the API already returns only its retained recent window. A narrower request can be revisited if
EA fetch time repeatedly exceeds about 15s; it is not worth a separate ticket today.

**Building the site from the just-written local Parquet instead of re-reading R2:** reject for
now despite being the simplest potential 7s saving. The current workflow deliberately verifies
that the published R2 Parquet can be read before publishing the site, which is useful for a
"trustworthy hosted pipeline" destination. Seven seconds is not enough to trade away that
end-to-end check.

### Decision

No new optimization tickets. Keep watching the `build-info.json`/job-summary timings added by
issue 03. If the revisit thresholds are crossed, the first likely ticket should be narrowly scoped:
measure workflow `aws s3 sync` durations, then decide between building from local curated Parquet
or adding partition-level reads/writes based on the measured split at that future size.
