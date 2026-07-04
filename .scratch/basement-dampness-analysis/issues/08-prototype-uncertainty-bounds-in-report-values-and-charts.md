# Prototype uncertainty bounds in report values and charts

Type: prototype
Status: resolved
Parent: ../map.md
Blocked by: 07

## Question

What would it look like to carry uncertainty through the key report values and show 95% confidence or coverage intervals on dashboard charts?

Build a low-fidelity prototype or notebook-style artifact using the current data and the uncertainty plan. Focus on whether uncertainty bars are legible and meaningful for absolute humidity, rebound rate, daily summaries, and any headline comparison metrics.

## Answer

Prototype assets:

- [Uncertainty prototype script](../../../prototypes/basement_dehumidifier/uncertainty_prototype.py)
- [Generated uncertainty report](../../../prototypes/basement_dehumidifier/uncertainty_report.html)
- [Basement Uncertainty Prototype Notes](../../../prototypes/basement_dehumidifier/UNCERTAINTY_PROTOTYPE_NOTES.md)

Use approximate 95% coverage intervals in the dashboard for headline absolute-humidity values, daily mean absolute humidity, and rebound-rate points. The intervals are legible and meaningful when they are shown as secondary visual context: daily bars with error bars work well, rebound-rate points with error bars work well, and the raw/post-install absolute-humidity band is readable at 15-minute grouping but should not dominate the chart.

The key UX/model distinction is absolute level versus same-sensor change. Absolute mean humidity keeps a visibly large interval from manufacturer RH accuracy (`13.77 +/- 0.74 g/m3` pre-install, `10.52 +/- 0.73 g/m3` post-install in this run), while the same-sensor post-minus-pre change is much tighter (`-3.25 +/- 0.09 g/m3`) when common sensor accuracy components are allowed to cancel. The dashboard must state that cancellation assumption explicitly and must not reuse it for cross-sensor comparisons.

Rebound-rate uncertainty is worth showing, because it prevents over-reading small cycle-to-cycle changes. In this run the latest median rebound rate is `2.41 +/- 0.10 g/m3/hr`; that supports using the metric directionally, but not as decisive leak/no-leak evidence.

The prototype was verified with `uv run python prototypes/basement_dehumidifier/uncertainty_prototype.py` and a Playwright browser check of the generated HTML. No new wayfinder tickets were added; the existing dashboard, report, and uncertainty-pipeline tickets already cover the next sharp questions.
