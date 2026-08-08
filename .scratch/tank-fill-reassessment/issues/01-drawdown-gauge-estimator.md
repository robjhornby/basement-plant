# Build the moisture-drawdown tank gauge estimator

Type: task
Parent: ../PRD.md
Status: ready-for-agent

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
