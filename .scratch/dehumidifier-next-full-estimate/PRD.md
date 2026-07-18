# Dehumidifier next-full estimate

Labels: ready-for-agent

## Problem Statement

The basement dehumidifier has a 25 L tank that stops extraction when full, and the owner-analyst
only discovers this after the fact by seeing basement humidity climb on the dashboard. There is no
way to know, ahead of time, when the tank will next need emptying — so the tank sits full for
hours (in one observed case 28 hours), losing drying time.

## Solution

On every daily static site rebuild, infer the dehumidifier's tank history (extraction cycles,
tank-full events, tank-emptied events) directly from the basement sensor's relative-humidity
signal — no manual logging — and publish a next-full estimate in the site footer as plain text.
The estimate uses the simplest model the data supports today: the mean duration of observed
complete fill intervals, anchored at the most recent tank-emptied event. The footer also reports
how many times the tank has filled so far and the total litres removed. When the data shows the
dehumidifier is not extracting at the latest reading, the footer says so instead of predicting,
without claiming to know why.

## User Stories

1. As the owner-analyst, I want the site to predict the date and time the dehumidifier tank will
   next be full, so that I can empty it promptly and lose minimal drying time.
2. As the owner-analyst, I want tank-full and tank-emptied events inferred automatically from the
   relative-humidity signal, so that I never have to log tank emptying manually.
3. As the owner-analyst, I want the prediction anchored at the most recent tank-emptied event, so
   that it reflects the tank actually in use rather than a rolling average of the past.
4. As the owner-analyst, I want the prediction to carry an honest uncertainty derived from the
   observed spread of fill intervals, so that I am not misled by false precision.
5. As the owner-analyst, I want the footer to tell me when the dehumidifier is not running as of
   the latest data, so that I know to go and empty (or check) it now rather than trust a stale
   prediction.
6. As the owner-analyst, I want the footer to avoid claiming a cause when cycling has stopped, so
   that the site stays scientifically correct about what the data can and cannot distinguish.
7. As the owner-analyst, I want an explicit "filling longer than expected" message when the
   current fill interval has outlasted the mean, so that I know the tank may be full at any time
   instead of seeing a prediction in the past.
8. As the owner-analyst, I want the footer to state how many times the tank has filled and the
   total litres of water removed, so that I can see the dehumidifier's cumulative effect at a
   glance.
9. As the owner-analyst, I want the estimate recomputed on every scheduled rebuild from the
   curated dataset, so that each completed fill interval automatically refines the model.
10. As the owner-analyst, I want the footer text rendered as plain text after the existing sources
    paragraph with no new styling, so that the dashboard design stays untouched.
11. As the owner-analyst, I want the site build to publish even when the estimator fails, so that
    a modelling bug can never take down the data dashboard.
12. As the owner-analyst, I want estimator failures visible in the build log, so that a silently
    missing footer sentence is still discoverable.
13. As the owner-analyst, I want the detection thresholds recorded verbatim in the spec and code,
    so that the inferred event history stays reproducible and reviewable.
14. As the owner-analyst, I want brief resumed-cycling blips inside a tank-full episode absorbed
    rather than treated as an empty-and-refill, so that physically impossible fill intervals never
    enter the model.
15. As the owner-analyst, I want times displayed in the same local-time frame as the rest of the
    footer, so that "Data to" and the prediction read consistently.

## Implementation Decisions

### Domain vocabulary

Use the `CONTEXT.md` glossary terms throughout: **extraction cycle**, **cycling band**,
**tank-full event**, **tank-emptied event**, **tank-full episode**, **fill interval**,
**next-full estimate**.

### Event inference (spec-verbatim, validated against the owner's one-off sanity check)

All inference runs on the basement-location sensor readings at 1-minute cadence, from the
dehumidifier installation event (2026-07-01 21:00) onward:

1. Smooth relative humidity with a centred 9-minute rolling median (removes the 0.8-point
   quantisation steps).
2. Detect extraction-cycle troughs: local minima over a ±10-minute window with at least 0.8 RH
   points of prominence against the surrounding 90 minutes; troughs closer than 15 minutes
   collapse into one.
3. Detect a tank-full episode: a trough-to-trough gap longer than **2 hours** in which smoothed RH
   exceeds the current fill interval's 90th-percentile trough RH (the cycling band reference) by
   more than **3 points**. The episode's bounding troughs are the tank-full event and the
   tank-emptied event. The percentile is computed per fill interval, not globally, because the
   cycling band drifts downward as the basement dries.
4. Resumed cycling shorter than **8 hours** between qualifying gaps does not split a tank-full
   episode (observed: a 6.1-hour cycling blip inside the 2026-07-09→11 episode; a 25 L tank
   cannot refill in hours).

No other guards. Manual/power interruptions are deliberately not detected. Thresholds are
revisited only if a predicted-vs-actual mismatch shows up, not tuned speculatively.

### Model

- A fill interval runs from a tank-emptied event (or the installation event, for the first) to the
  next tank-full event. Only complete fill intervals feed the model.
- Next-full estimate = most recent tank-emptied event + mean duration of all complete fill
  intervals, equal-weighted.
- Displayed uncertainty = half the range of observed complete fill durations, rounded to the
  nearest half day, with a floor of half a day (never "± 0").
- Rejected alternatives, from the 2026-07-18 exploration of 16 days of post-install data: cycles
  per fill (spread 46% of mean across the 3 complete fills — fails the owner's consistency
  criterion), absolute-humidity·hours (26%), and excess-AH·hours above the 50% RH target (23%) —
  neither humidity model beats plain elapsed days (26%) by more than noise at n=3.
- Known accepted bias: the basement is drying, so fill intervals should lengthen and the estimate
  will tend to run early. That failure direction (check the tank slightly too soon) is acceptable.
- Known accepted limitation: a tank emptied less than ~2 hours after going full is invisible to
  the signal; the two adjoining fill intervals would fuse. Accepted for now; refine with data.

### Footer rendering

One new plain-text paragraph after the existing sources paragraph. No new styling or design. All
times in the dataset's local-time frame, 24-hour clock, no year, no timezone label, weekday + day
+ abbreviated month (e.g. `Sun 19 Jul 15:00`).

The paragraph always begins with (N = count of completed tank-full episodes, x = N × 25):

> The dehumidifier has filled {N} times so far, removing {x} litres of water.

Followed by exactly one of, chosen by the state at the latest reading:

1. Filling, estimate at or after the latest reading:
   > Dehumidifier tank predicted next full {Sun 19 Jul 15:00} ± {half a day}.
2. In a tank-full episode at the latest reading (cause-agnostic by design):
   > The dehumidifier is not running as of the latest data.
3. Filling, but the latest reading is past the estimate:
   > Dehumidifier tank has been filling longer than expected, it may be full at any time.

The "±" is the literal plus-minus symbol. The uncertainty renders in words rounded to half days
("half a day", "1 day", "1½ days"). A cycling stop more recent than the 2-hour detection threshold
is indistinguishable from an ordinary between-cycle gap and deliberately falls into state 1 or 3.

### Placement and failure behaviour

- The estimator is pure polars/standard-library logic living beside the existing summary
  computation, consuming the curated Parquet dataset already loaded by the site build. No new
  workflow step, no new CLI command, no schema changes.
- The existing site renderer emits the footer paragraph from the estimator's output.
- Any estimator failure (unexpected data shape, zero detectable complete fill intervals, any
  exception) omits the entire new paragraph, prints a warning to the build log, and never blocks
  site publication.

### Reference ground truth (owner-confirmed, for validating the implementation)

| Fill interval | Emptied → full | Duration | Extraction cycles |
| --- | --- | --- | --- |
| A | install 07-01 21:04 → 07-05 00:40 | 3.15 d | 91 |
| B | 07-05 15:47 → 07-09 18:38 | 4.12 d | 135 |
| C | 07-11 14:20 → 07-15 07:41 | 3.72 d | 149 |
| D | 07-15 23:13 → in progress at 07-17 23:55 | 2.03 d so far | 98 so far |

Tank-full episodes end at 07-05 15:47 (15.1 h stopped), 07-10 → 07-11 14:20 (one episode
containing the cycling blip), and 07-15 23:13 (15.5 h stopped). Mean complete fill duration at
exploration time: 3.66 days; spread ±0.49 d → "± half a day".

The local dataset snapshot used for the exploration lives at `local/r2-parquet-snapshot`
(gitignored); refresh it with the same `aws s3 sync` invocation the site workflow uses.

## Testing Decisions

- Test external behaviour only: given a synthetic basement RH series, assert the inferred events,
  the estimate, and the exact footer sentence — never intermediate signal-processing artifacts.
- Primary seam (new, the only new one): the pure estimator function from basement sensor readings
  to tank history + footer state. Unit-test it on synthetic 1-minute RH fixtures covering: healthy
  cycling; a tank-full episode; the resumed-cycling blip inside an episode; the overdue state; a
  quick empty shortly after the 2-hour threshold; and the failure/degradation path (empty or
  malformed input series).
- Secondary seam (existing): the site render tests that build pages from constructed summary data
  — extend them to assert the footer paragraph appears verbatim after the sources paragraph in
  each of the three states, and is absent when the estimator reports failure.
- Prior art: the existing static-site summary test suite, which builds summaries from constructed
  readings and asserts on rendered HTML (including existing verbatim footer assertions).
- Validation (one-off, not CI): run the estimator against the real curated snapshot and confirm it
  reproduces the owner-confirmed ground-truth table above.

## Out of Scope

- Humidity/temperature-driven fill models (rejected at n=3; revisit only if predicted-vs-actual
  mismatches accumulate).
- Detecting manual or power interruptions, or distinguishing why cycling stopped.
- Detecting tank empties that occur within the ~2-hour detection blind spot.
- Manual tank-event logging of any kind.
- Any styling, layout, or chart changes; anything outside the single footer paragraph.
- Changes to the GitHub Actions workflow, the ingestion pipeline, or the curated schema.
- Estimating the partial volume of the in-progress fill (litres count completed fills only).

## Further Notes

- The exploration scripts from the 2026-07-18 session were scratch work and are deliberately not
  part of the deliverable; the shipped estimator is written fresh against this spec.
- Rounding of the uncertainty is to the *nearest* half day (owner's decision), with the half-day
  floor as the only exception.
- The repo is public: the footer text contains no location or personal details beyond what the
  site already publishes.
