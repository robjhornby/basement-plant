# Build the moisture-drawdown tank gauge estimator

Type: task
Parent: ../PRD.md
Status: done

## Answer

`estimate_tank_gauge(sensor_readings, tank_full_events) -> TankGauge | TankEstimateFailure` in
`src/basement_analysis/tank_estimator.py`. Cycle detection was factored to
`detect_extremum_indices(smoothed, kind)` so the shipped spec-verbatim trough logic is reused for
peaks too. Drawdown uses absolute humidity (preceding peak within 120 min − trough, clamped ≥ 0);
`tank_emptied_after` detects the emptied time from resumed cycling; calibration + live formulas per
the PRD. `TankGauge` carries `state` ∈ {filling, full_or_overdue, not_running}; the forward fields
(`cycles_remaining`, `time_remaining_days`, `next_full`) are `None` when not running. 7 unit tests;
`CONTEXT.md` gained a **drawdown dose** entry.

Two notes for issues 02/03:

- **Snapshot validation:** production gives `DOSE_PER_TANK` 135.5 vs the workbench's 136.5, same
  per-tank profile, scatter 21% vs 27%. The gap is the detector — production reuses the shipped
  plateau-centre trough/peak finder (mandated here), the workbench uses a simpler one. Expected, not
  a bug. The workbench still reproduces the FINDINGS numbers (136.5, MAE 1.27 d).
- **Full-boundary constant:** `FULL_FRACTION_THRESHOLD = 1.0` in `tank_estimator.py`. On the snapshot
  the live tank sits at ≈0.998 → state `filling` (next_full +8 min), where the workbench read 103%.
  Issue 02 pins this threshold against real snapshot output.

The old `estimate_tank_history` / `footer_text` path and the live footer are deliberately left
untouched — issue 02 swaps the footer to the gauge (after Rob confirms wording), issue 03 gets the
events into the hosted feed. The gauge is not yet wired into the site build.

## Question

Implement the pure moisture-drawdown fuel-gauge estimator specified in `../PRD.md`
("Cycle detection", "Drawdown dose", "Fill intervals and calibration", "Live estimate"), replacing
the calendar-days model in `src/basement_analysis/tank_estimator.py`. Reference implementation of
the maths already exists and is validated in `scripts/tank_drawdown_gauge.py` — port it into
production shape (typed, tested, consuming the curated readings + logged tank-full events).

Resolve when:

- A pure function takes basement sensor readings **and the logged tank-full events** and returns a
  gauge state: completed-tank count, litres removed, `DOSE_PER_TANK`, uncertainty fraction `u`,
  and — for the open tank — `fraction_full`, `litres_so_far`, `cycles_remaining`,
  `time_remaining_days`, `next_full`, and a `state` enum (filling / full-or-overdue / not-running).
- Cycle detection reuses the existing spec-verbatim trough/peak logic (9-min median, ±10-min local
  extrema, 0.8 prominence / 90-min, 15-min collapse) — factor it out rather than duplicating.
- Per-cycle drawdown uses **absolute humidity** (preceding-peak within 120 min − trough, clamped
  ≥ 0); dose = sum over interval; calibration and live formulas exactly per the PRD.
- Tank-full events come from the logged source (`data/basement_events.csv` rows containing
  "tank full"); tank-emptied events are detected per the PRD resume rule. The function is given the
  events, not responsible for auto-detecting tank-full from RH.
- `CONTEXT.md` gains a **drawdown dose** glossary entry consistent with the PRD.
- Unit tests cover the PRD's fixtures (healthy mid-tank filling; near-full/overdue; not-running;
  dry-regime weak-rebound fill still calibrated from the logged event; failure/degradation on empty
  or malformed input), asserting the state fields — not intermediate signal artifacts.
- One-off validation: `uv run python scripts/tank_drawdown_gauge.py` still reproduces the FINDINGS
  numbers, and the new production function agrees with the script on the real snapshot
  (`DOSE_PER_TANK ≈ 136.5`, backtest MAE ≈ 1.27 d).

Note: footer rendering is issue 02; getting the events into the hosted build is issue 03. This
issue can land and be tested with events passed in directly.
