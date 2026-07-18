# 02 — Footer next-full paragraph with graceful degradation

**What to build:** the public dashboard footer gains one new plain-text paragraph, rendered
during the existing site build from the tank-history estimator's output, immediately after the
existing sources paragraph. No new styling or design; no workflow, pipeline, or schema changes.
Spec: [../PRD.md](../PRD.md) — quote it verbatim, do not paraphrase.

**Blocked by:** 01 — Tank-history estimator with validated inference.

**Status:** ready-for-agent

Footer text (spec-verbatim, from PRD "Footer rendering"). The paragraph always begins with
(N = completed tank-full episodes, x = N × 25):

> The dehumidifier has filled {N} times so far, removing {x} litres of water.

Followed by exactly one of, chosen by the state at the latest reading:

1. Filling, estimate at or after the latest reading:
   > Dehumidifier tank predicted next full {Sun 19 Jul 15:00} ± {half a day}.
2. In a tank-full episode at the latest reading:
   > The dehumidifier is not running as of the latest data.
3. Filling, but the latest reading is past the estimate:
   > Dehumidifier tank has been filling longer than expected, it may be full at any time.

Formatting rules: times in the dataset's local frame, 24-hour clock, weekday + day + abbreviated
month, no year, no timezone label; literal ± symbol; uncertainty in words rounded to half days
("half a day", "1 day", "1½ days").

Acceptance criteria:

- [ ] The paragraph renders after the sources paragraph with the verbatim sentences above in each
      of the three states.
- [ ] Any estimator failure (including zero detectable complete fill intervals) omits the entire
      paragraph, prints a warning to the build log, and the site build still completes and
      publishes.
- [ ] Render tests (extending the existing static-site summary suite's constructed-summary
      pattern) assert the verbatim paragraph in all three states, its position after the sources
      paragraph, and its absence on estimator failure.
- [ ] Demoable: build the site locally from `local/r2-parquet-snapshot` and see the prediction
      sentence in the footer of the generated page.
- [ ] `uv run pytest`, `uv run ruff check .`, `uv run pyright` all pass.
