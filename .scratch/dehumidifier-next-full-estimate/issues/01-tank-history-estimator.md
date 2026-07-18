# 01 — Tank-history estimator with validated inference

**What to build:** a pure estimator that turns the basement sensor's 1-minute readings (from the
dehumidifier installation, 2026-07-01 21:00, onward) into the tank history — extraction cycles,
tank-full events, tank-emptied events, fill intervals — and the footer state the site will
render: completed-fill count, litres removed (count × 25), and one of three states (predicted
next full with datetime and uncertainty / not running at latest data / filling longer than
expected). Spec: [../PRD.md](../PRD.md) — quote it verbatim, do not paraphrase.

**Blocked by:** None — can start immediately.

**Status:** ready-for-agent

Detection rules (spec-verbatim, from PRD "Event inference"):

1. Smooth relative humidity with a centred 9-minute rolling median.
2. Extraction-cycle troughs: local minima over a ±10-minute window with at least 0.8 RH points of
   prominence against the surrounding 90 minutes; troughs closer than 15 minutes collapse into
   one.
3. Tank-full episode: a trough-to-trough gap longer than **2 hours** in which smoothed RH exceeds
   the current fill interval's 90th-percentile trough RH by more than **3 points**; bounding
   troughs are the tank-full and tank-emptied events. Percentile computed per fill interval, not
   globally.
4. Resumed cycling shorter than **8 hours** between qualifying gaps does not split a tank-full
   episode.

Model (spec-verbatim, from PRD "Model"): next-full estimate = most recent tank-emptied event +
equal-weighted mean duration of all complete fill intervals; uncertainty = half the range of
observed complete fill durations, rounded to the nearest half day, floored at half a day.

Acceptance criteria:

- [ ] Pure polars/standard-library estimator beside the existing summary computation; no new
      workflow step, CLI command, or schema change.
- [ ] Unit tests on synthetic 1-minute RH fixtures cover: healthy cycling; a tank-full episode;
      the resumed-cycling blip inside an episode; the overdue state; a quick empty shortly after
      the 2-hour threshold; and empty/malformed input reporting failure instead of raising.
- [ ] Run against the real curated snapshot (`local/r2-parquet-snapshot`, refresh with the same
      `aws s3 sync` the site workflow uses) the estimator reproduces the owner-confirmed ground
      truth from the PRD's "Reference ground truth" table: complete fill intervals of 3.15 d /
      4.12 d / 3.72 d ending 07-05 00:40, 07-09 18:38, 07-15 07:41; tank-emptied events at
      07-05 15:47, 07-11 14:20, 07-15 23:13; the 07-09→11 stretch as one tank-full episode; and
      approximately 91/135/149 cycles (±2) per complete fill.
- [ ] Demoable: a test or small harness prints the inferred timeline and footer state from the
      real snapshot.
- [ ] `uv run pytest`, `uv run ruff check .`, `uv run pyright` all pass.
