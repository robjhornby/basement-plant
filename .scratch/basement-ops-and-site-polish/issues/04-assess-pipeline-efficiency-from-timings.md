# Assess pipeline efficiency from measured timings

Type: research
Parent: ../map.md
Blocked by: 03

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
