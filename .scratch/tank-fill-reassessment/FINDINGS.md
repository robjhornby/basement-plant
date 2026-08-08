# Tank-fill prediction — reassessment (2026-08-07)

Re-examines how to predict the dehumidifier tank filling, using a fresh pull of the full
curated dataset and all five logged tank-full events. Prompted by the observation that fills
have become slower and more erratic: the basement now often stays dry on its own, so the
dehumidifier idles instead of running non-stop despite having tank capacity left.

## Data

- Pulled the whole curated Parquet lake from R2 (`basement-pipeline/parquet/`) to
  `data/parquet-2026-08-07/` (gitignored). Basement / Bedroom / Living-room sensor readings at
  1-minute cadence, plus Open-Meteo weather and Environment-Agency rain. Basement coverage
  2026-02-13 → 2026-08-06, ~99.97% of minutes present.
- Ground-truth tank-full events from `data/basement_events.csv`: Jul 05, 11, 15, 23, 29
  (five completed fills since the dehumidifier went in on Jul 01 21:00).
- Scratch analysis: `.scratch/tank-fill-reassessment/` scripts (kept out of git via `data/`
  inputs); reproduce with `uv run python` against the snapshot.

## What the data shows

1. **The basement is drying, and fill rate is non-stationary.** Daily mean RH fell from ~64 in
   early July (with big rebounds) to ~60 pinned near the 54% floor from ~Jul 17 on; basement
   absolute humidity fell from ~11 to ~9.5 g/m³. Fill intervals: 3.2, 5.4, 3.7, 7.9, 5.7 days —
   noisy and trending longer. A single calendar-time mean is the wrong tool for a process whose
   rate is changing.

2. **Extraction is bursty at the day scale.** Cumulative moisture removed per day in the current
   open tank ranged from **2.3 (Aug 01, barely ran) to 33.7 (Aug 03)** in the same units. This is
   exactly the "stays dry by itself, then works hard" pattern — any predictor must integrate
   through idle days rather than assume a steady rate.

3. **A single extraction cycle is a clean ~40-min RH sawtooth**: RH plunges ~10 points while
   *temperature rises* (compressor waste heat), then rebounds slowly. Temperature is a
   moisture-independent "compressor on" signature; in the dry regime both the RH swing and the
   temp bump shrink toward the noise floor.

4. **In the dry regime a tank-full no longer produces a big RH rebound.** The old detector keys
   tank-full episodes off RH rising above the cycling band; it cleanly finds Jul 05/11/15/29 but
   **misses Jul 23** entirely — when the room is dry, the tank fills without the air rebounding
   much. Detecting *fills* from RH alone is getting less reliable over the campaign.

## The core idea: a moisture-drawdown fuel gauge

The tank holds a fixed **25 L of water**, not a fixed number of days or cycles. The right state
variable is *litres accumulated since the tank was emptied*; the right rate is *how fast water is
being condensed right now*. We have no flow meter, so we need a proxy for water condensed.

Tested which measurable quantity is most constant across the five tanks (each = 25 L). Lower
coefficient of variation = better "fuel gauge":

| Proxy for one tank of water | CoV across 5 tanks |
|---|---|
| **Σ per-cycle absolute-humidity drawdown** (peak→trough AH drop, summed over cycles) | **0.27** |
| Σ per-cycle RH amplitude | 0.24 |
| calendar days | 0.32 |
| compressor runtime hours | 0.42 |
| **raw cycle count** | **0.50** |

**Raw cycle-counting is the *worst* gauge.** Cycles/day actually *rose* over the campaign
(27→50) even as each fill took longer, because as the air dries **each cycle condenses less
water** (litres-per-cycle falls). Counting cycles double-counts shallow late cycles.

Weighting each cycle by its **absolute-humidity drawdown** — the moisture swing the machine
actually produces that cycle — corrects exactly this, and is physically "water condensed per
cycle." It is the tightest proxy and it unifies both of Rob's hints: it is cycle-based (gives
"cycles remaining") *and* it is the per-cycle humidity change (independent of how often the unit
chooses to cycle). AH is preferred over RH because it is the physical moisture quantity and less
sensitive to sensor placement/temperature.

### The model

- **Fuel gauge:** `dose(t)` = cumulative per-cycle AH drawdown since the last tank-emptied event.
- **Calibration:** `DOSE_PER_TANK` = mean per-tank dose over completed tanks (currently **136.5**,
  scatter **±27%**). `fraction_full = dose / DOSE_PER_TANK`; `litres = 25 × fraction_full`.
- **Cycles remaining** ≈ `(DOSE_PER_TANK − dose) / recent_median_drawdown_per_cycle`.
- **Time remaining** = `cycles_remaining × recent_mean_cycle_period`, equivalently
  `remaining_dose / recent_dose_per_day`. Using the *recent* rate is what makes it self-pace
  through idle days — during a dry spell the gauge simply stops advancing and the ETA stretches.
- **Uncertainty:** dominated by the ±27% calibration scatter (→ roughly ±1.5 d on a ~5-day tank);
  report time-remaining as a range, not a point.

### Honest accuracy (leave-one-out backtest)

At the midpoint of each interval, predicting the full-time causally (calibration excluding that
tank, rate = dose-so-far this tank):

- **Drawdown gauge MAE = 1.27 d**  vs  **calendar-days model MAE = 1.75 d**.

Better, and — unlike the days model — it produces a live within-interval readout and adapts when
a tank is running slow.

## Live estimate as of the snapshot (Aug 06 23:59)

- Current open tank emptied ≈ Jul 30; cumulative dose **140.1 / 136.5 → ~100% full (~25.7 L)**.
- **The tank should be full right now / imminently.** Most of this fill landed Aug 03–06 after a
  near-idle Aug 01. The calendar-days model likewise expected full ~Aug 04. Worth confirming
  against the real tank and logging the 6th event.

## Caveats

- Five tanks is a thin calibration; the ±27% is real and the CoV gap between proxies (0.27 vs
  0.32) is within small-sample noise — the drawdown gauge is chosen on physical grounds plus the
  backtest, not on the CoV alone.
- Cycle detection degrades as swings approach the noise floor; if the room dries further, shallow
  cycles will be missed and the gauge will under-count. Temperature-based compressor detection is
  a candidate backstop worth exploring before that happens.
- Tank-full *detection* from RH rebound is already unreliable in the dry regime (missed Jul 23);
  continue to rely on logged events for calibration, and treat auto-detected fills as advisory.

## Recommended next step

Rebuild the estimator around the drawdown fuel gauge, reporting **fraction full, cycles
remaining, and time remaining ± range** instead of a single next-full datetime — then surface it
in the site footer. (Build ticket, separate session.)
