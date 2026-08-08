# Dehumidifier tank — moisture-drawdown fuel gauge

Labels: ready-for-agent

Supersedes the model in `.scratch/dehumidifier-next-full-estimate/` (the calendar-days
"next-full estimate"). Grounded in `.scratch/tank-fill-reassessment/FINDINGS.md` and the
workbench script `scripts/tank_drawdown_gauge.py`, both from the 2026-08-07 reassessment.

## Problem Statement

The shipped estimator predicts the next tank-full time as *most-recent-emptied + mean fill
duration in days*. Since it shipped, the basement has been drying: the dehumidifier now idles for
long stretches when the room stays dry on its own, so fill intervals have grown long and erratic
(3.2 → 7.9 days) and daily water removed swings ~15× day to day. A single calendar-time mean
cannot track a non-stationary, bursty fill rate, and it gives no within-interval readout — the
owner-analyst cannot see mid-tank whether a fill is ahead of or behind schedule.

Separately, the old model auto-detects tank-full events from a relative-humidity rebound above
the cycling band. In the dry regime that rebound is disappearing: the reassessment's detector
**misses the 2026-07-23 fill entirely**, because a dry room barely rebounds when extraction stops.

## Solution

Replace the model with a **moisture-drawdown fuel gauge**. The tank holds a fixed 25 L, so track
*litres accumulated since the tank was last emptied* and estimate *time remaining* from the
recent fill rate:

- Each extraction cycle's **absolute-humidity drawdown** (preceding-peak AH − trough AH) is a
  proxy for the water condensed that cycle. Summing drawdowns since the tank was emptied is the
  fuel gauge. It is the tightest of the tested proxies (CoV 0.27 across the five tanks, vs 0.32
  for calendar days and 0.49 for raw cycle-count), and it degrades gracefully — see FINDINGS.
- Calibrate `DOSE_PER_TANK` = mean per-tank drawdown sum over completed tanks (currently 136.5,
  ±27%), where each completed tank = 25 L.
- Report, for the current open tank: **fraction full / litres so far / cycles remaining / time
  remaining ± range**, using the recent (trailing-3-day) rate so the estimate self-paces through
  idle spells.
- Calibrate from the **owner-logged tank-full events** (`data/basement_events.csv`), not from
  RH-rebound auto-detection, which is no longer reliable. Tank-*emptied* times are still detected
  from the signal (cycling clearly resumes — that transition stays crisp).

Honest accuracy: leave-one-out, predicting at each interval's midpoint, the gauge scores
**MAE 1.27 d vs 1.75 d** for the calendar-days model, and unlike it produces a live gauge.

## User Stories

1. As the owner-analyst, I want the footer to show how full the current tank is right now (percent
   and litres), so I can see progress mid-fill instead of only a predicted date.
2. As the owner-analyst, I want an estimate of the **cycles remaining** and the **time remaining**
   (cycles-remaining × recent cycle period), so the readout matches how the machine actually works.
3. As the owner-analyst, I want the time-remaining estimate driven by the **recent** fill rate, so
   that when the room stays dry and the unit idles, the estimate stretches automatically rather
   than reading falsely soon.
4. As the owner-analyst, I want the estimate calibrated from the tank-full events I log in
   `basement_events.csv`, so the model is anchored to ground truth even in the dry regime where the
   humidity rebound no longer reveals a fill.
5. As the owner-analyst, I want an honest uncertainty range from the observed spread of per-tank
   drawdown, so I am not misled by false precision.
6. As the owner-analyst, I want the "filled N times, removed X litres" cumulative line kept, so I
   keep the at-a-glance total.
7. As the owner-analyst, I want a plain "not running as of the latest data" message when no cycles
   are detected recently, cause-agnostic, so a stalled or unplugged unit is not shown as filling.
8. As the owner-analyst, I want an "may be full at any time" message once the gauge reaches ~full
   or the recent rate goes to zero mid-fill, so I check the tank instead of seeing a past estimate.
9. As the owner-analyst, I want the estimator to fail soft (omit the paragraph, warn in the build
   log, never block publication), exactly as today.
10. As the owner-analyst, I want the whole method reproducible from `scripts/tank_drawdown_gauge.py`
    against a local snapshot, so I can re-tune knobs and re-check before changing production code.

## Implementation Decisions

Domain terms from `CONTEXT.md`: **extraction cycle**, **tank-full event**, **tank-emptied event**,
**fill interval**. New term to add to the glossary: **drawdown dose** (see issue 01).

### Cycle detection (spec-verbatim, unchanged from the shipped estimator)

On Basement 1-minute readings from `2026-07-01 21:00` onward:

1. Smooth RH with a centred 9-minute rolling median.
2. Extraction-cycle troughs: local minima over a ±10-minute window with ≥ 0.8 RH points of
   prominence against the surrounding 90 minutes; troughs closer than 15 minutes collapse into one.
3. Extraction-cycle peaks: the same rule for local maxima.

### Drawdown dose

- For each trough, its **preceding peak** is the last peak within 120 minutes before it. A trough
  with no preceding peak in range contributes no cycle.
- **Per-cycle drawdown** = `max(0, absolute_humidity[peak] − absolute_humidity[trough])`. Absolute
  humidity (not RH) because it is the physical moisture quantity and least sensitive to sensor
  placement/temperature (`CONTEXT.md`: *sensor-placement artifact*).
- **Drawdown dose over an interval** = sum of per-cycle drawdowns for troughs whose time lies in
  the interval.

### Fill intervals and calibration

- A fill interval runs from a **tank-emptied event** (or the installation event, for the first) to
  the next **tank-full event**. Tank-full events are the timestamps logged in
  `data/basement_events.csv` (rows whose text contains "tank full"), sorted.
- A **tank-emptied event** is detected from the signal: the first trough at least 30 minutes after
  a tank-full event such that ≥ 3 troughs fall within the following 180 minutes (cycling resumed).
  Fallback if none: tank-full + 6 hours.
- `DOSE_PER_TANK` = equal-weighted mean of the drawdown dose of every **completed** fill interval.
- **Uncertainty fraction** `u` = standard deviation / mean of the completed-tank doses.

### Live estimate (current open tank)

Let the open tank run from the most recent tank-emptied event to the latest reading.

- `open_dose` = drawdown dose of the open interval.
- `fraction_full = open_dose / DOSE_PER_TANK`; `litres_so_far = 25 × fraction_full`.
- `remaining_dose = max(0, DOSE_PER_TANK − open_dose)`.
- `recent_rate` = drawdown dose over the trailing 3 days ÷ 3 (dose per day).
- `recent_drawdown_per_cycle` = median per-cycle drawdown over the trailing 3 days (fallback: the
  all-time median).
- `cycles_remaining = round(remaining_dose / recent_drawdown_per_cycle)`.
- `time_remaining_days = remaining_dose / recent_rate`; `next_full = latest_reading +
  time_remaining_days`.
- Displayed range = `time_remaining_days × (1 ± u)`.

Prefer the simplest form the data supports; add no robustness guards beyond those specified. Knobs
(trailing window = 3 days, resume thresholds) are revisited only on a predicted-vs-actual mismatch,
never tuned speculatively (matches the shipped estimator's discipline and the owner's stated
preference for simple-model-refined-with-data).

### Footer rendering — PROPOSED, confirm wording before building

One plain-text paragraph after the existing sources paragraph; no new styling. Times in the
dataset's local-time frame, 24-hour, weekday + day + abbreviated month (e.g. `Sun 19 Jul 15:00`).
Percent to the nearest 5%, litres to the nearest whole, time-remaining to the nearest half day.

Always begins (N = completed tanks, x = N × 25):

> The dehumidifier has filled {N} times so far, removing {x} litres of water.

Then exactly one of, by state at the latest reading:

1. Filling (recent cycles present, `fraction_full` below ~1 and `next_full` at/after latest
   reading):
   > The current tank is about {P}% full (~{L} of 25 litres) — roughly {C} cycles left, likely
   > full {Sun 19 Jul 15:00} ± {1 day}.
2. Full/overdue (`fraction_full` ≥ ~1, or `next_full` before the latest reading):
   > The current tank is about {P}% full and may be full at any time — worth checking.
3. Not running (no extraction cycles detected in the trailing 3 days):
   > The dehumidifier is not running as of the latest data.

`±` is the literal plus-minus symbol; the range renders in words rounded to half days ("half a
day", "1 day", "1½ days"), reusing the existing `uncertainty_words` helper. Exact thresholds for
"about full" (state boundary) to be pinned in issue 02 against real snapshot output.

### Placement and failure behaviour (unchanged from the shipped estimator)

- Pure `polars`/standard-library logic beside the existing summary computation, consuming the
  curated Parquet already loaded by the site build. No new workflow step, no new CLI command, no
  schema changes to sensor data.
- Any estimator failure (unexpected shape, zero completed tanks, any exception) omits the entire
  paragraph, prints a warning to the build log, and never blocks publication.

### Dependency: tank-full events must reach the hosted build

The hosted site build must see the logged tank-full events. Today the curated `events` dataset in
R2 (`source=local_manual`) stops at 2026-07-02; the tank-full rows live only in the local
`data/basement_events.csv`. Before the hosted footer can calibrate, those events must be in the
curated events feed the build reads. Issue 03 tracks closing that gap; the estimator itself
(issue 01) is written against whatever event source it is handed and is testable without it.

## Testing Decisions

- Test external behaviour only: given a synthetic basement AH/RH series **and a set of logged
  tank-full events**, assert the computed `fraction_full`, `cycles_remaining`,
  `time_remaining_days`, state, and the exact footer sentence — never intermediate signal
  artifacts.
- Primary seam: the pure gauge function (readings + tank-full events → gauge state + footer). Unit
  fixtures covering: healthy filling mid-tank; near-full/overdue; not-running (no recent cycles);
  the dry-regime case where a tank fills with a weak RH rebound (fill still calibrated from the
  logged event); and the failure/degradation path (empty or malformed input).
- Secondary seam: the existing site-render tests — extend to assert the new paragraph appears
  verbatim after the sources paragraph in each state and is absent on estimator failure.
- Validation (one-off, not CI): `scripts/tank_drawdown_gauge.py` against the real snapshot must
  reproduce the FINDINGS numbers (DOSE_PER_TANK ≈ 136.5 ±27%, backtest MAE ≈ 1.27 d, the per-tank
  table). This script is the living reference for the model.

## Out of Scope

- Auto-detecting tank-full events from the RH rebound (deprecated; unreliable in the dry regime).
- Weather/temperature-driven fill models (still rejected; revisit only on accumulating
  predicted-vs-actual mismatch).
- Temperature-based compressor-on detection as a cycle-count backstop (noted in FINDINGS as a
  future option once cycles approach the noise floor; not now).
- Any styling, layout, or chart changes beyond the single footer paragraph.
- Retiring the old estimator's code paths beyond what the footer swap requires.

## Further Notes

- `scripts/tank_drawdown_gauge.py` is the workbench and stays; the production gauge is written
  fresh against this spec (the script is not imported by production code).
- The reassessment data snapshot (`data/parquet-2026-08-07/`) is gitignored; refresh with the
  `aws s3 cp s3://$R2_BUCKET/parquet/ …` invocation noted in the script's error message.
- Repo is public: the footer text adds no location or personal detail beyond what the site already
  publishes.
