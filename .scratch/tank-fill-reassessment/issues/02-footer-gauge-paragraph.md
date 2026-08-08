# Render the fuel-gauge footer paragraph

Type: task
Parent: ../PRD.md
Status: done (2026-08-08)
Blocked by: 01

## Answer

`gauge_footer_text(gauge) -> str` in `src/basement_analysis/tank_estimator.py` renders the state
from issue 01; `build_tank_footer_text` (summaries.py) now feeds it `estimate_tank_gauge` on the
sensor readings plus the logged tank-full events (`Event`s whose text contains "tank full"),
replacing the old `estimate_tank_history` next-full sentence. Fail-soft behaviour is unchanged
(omit the paragraph, warn, never block publication).

**Wording — confirmed with Rob 2026-08-08, frozen verbatim.** Lead always (N = completed tanks,
x = N × 25):

> The dehumidifier has filled {N} times so far, removing {x} litres of water.

Then exactly one state sentence:

1. Filling:
   > The current tank is about {P}% full (~{L} of 25 litres) — roughly {C} cycles left, likely
   > full {Tue 11 Aug 04:32} ± {1½ days}.
2. Full or overdue:
   > The current tank is estimated to be full — likely between {earliest} and {latest}.
3. Not running:
   > The dehumidifier is not running as of the latest data.

**Decisions Rob made** (were left PROPOSED):

- Kept the "roughly {C} cycles left" clause (C runs 74–174 on real data — Rob wanted it kept).
- Full/overdue reworded to "estimated to be full — likely between {earliest} and {latest}", where
  the window is `next_full ± full_window_days` and `full_window_days = uncertainty_fraction ×
  dose_per_tank ÷ recent_rate` — the calibration spread in days, which (unlike time_remaining × u)
  does not collapse to zero right at the full point. On the real snapshot that window is ≈ ± 1 day.
- **Percent rounds to the nearest whole integer** (Rob changed this from the PRD's nearest-5%).
  Litres nearest whole; day ranges in words via `uncertainty_words`, floored at half a day.
- Filling `±` kept as the PRD's `time_remaining_days × uncertainty_fraction`.
- **`FULL_FRACTION_THRESHOLD` pinned to 0.95** against the snapshot: the live tank sat at
  fraction_full 0.999 and percent renders to the nearest whole, so 0.95-up prints "100% full" and
  belongs in the "may be full" sentence, not "filling". `tank_estimator.py` gained a
  `full_window_days` field on `TankGauge`.

Tests: 5 renderer unit tests (each state verbatim + integer rounding + half-day floor) and the
site-render tests reworked to the three gauge states plus the no-events / exception fail-soft paths.

## Question

Render the gauge state from issue 01 as the site footer paragraph, per `../PRD.md`
("Footer rendering"), replacing the current next-full sentence.

Resolve when:

- The footer emits the cumulative lead ("filled N times … X litres") plus exactly one state
  sentence (filling / full-or-overdue / not-running) using the PROPOSED wording in the PRD —
  **confirm the exact wording with Rob first**, then pin it verbatim here before writing tests.
- Number formatting matches the PRD (percent to nearest 5%, litres to nearest whole, time to
  nearest half day; reuse `uncertainty_words`; local-time frame, 24-hour, weekday + day + abbr
  month).
- The "about full" state boundary (fraction threshold for switching filling → full-or-overdue) is
  chosen against real snapshot output and recorded in the Answer.
- Site-render tests assert the paragraph verbatim after the sources paragraph in each state and its
  absence on estimator failure; failure still omits the paragraph, warns in the build log, and
  never blocks publication.

## Comments

Wording is deliberately left PROPOSED in the PRD — do not ship copy Rob hasn't seen. Bring the
three real-state renderings (from the current snapshot) to him, adjust, then freeze.
