# Static Generator Dashboard/Report Boundary

This prototype resolves [Design static generator dashboard/report boundary](../issues/22-design-static-generator-dashboard-report-boundary.md). It is a concrete boundary proposal for the next production implementation pass, not production code.

## Prototype Decision

The local static generator should have one analysis summary contract that feeds both the dense dashboard and the explanatory physics/metrology report. Calculations should be performed once before rendering; dashboard and report generators should only choose layout, wording depth, and chart/table presentation.

Recommended shape:

- `build_site_analysis_summary(...)` is the only place that joins sensor data, events, weather, rain, uncertainty inputs, and hypothesis evidence into reusable outputs.
- Dashboard and report pages both render from `SiteAnalysisSummary`.
- Shared values are plain frozen dataclasses first, with JSON export added when publication or snapshot testing needs it.
- Chart series and table rows are summary data, not renderer-local calculations.
- SVG/HTML, colours, page navigation, explanatory prose order, and optional appendix expansion are presentation-only.

## Current Shape Observed

The current `uv run basement` command writes `build/basement-site/index.html` from `src/basement_analysis/static_site.py`.

Current production file responsibilities are mixed:

- source constants and sensor labels;
- CSV event and thermohygrometer parsing;
- Open-Meteo and Environment Agency fetch/cache logic;
- psychrometric calculation;
- hourly and daily aggregation;
- event period construction;
- period summary metrics;
- hypothesis text assembly;
- chart point extraction;
- SVG rendering;
- HTML/CSS rendering;
- output writing.

That is acceptable for the first local prototype, but it will duplicate logic as soon as the physics/metrology report is added. The immediate risk is not file size; it is that the dashboard and report could calculate different period means, caveats, uncertainty intervals, or hypothesis wording from the same inputs.

## Proposed Boundary

Use this module split as the next implementation target:

```text
src/basement_analysis/
  cli.py
  static_site.py             # orchestration and file output only
  sources.py                 # local CSV parsing plus weather/rain fetch/cache
  psychrometrics.py          # absolute humidity, dew point, named constants
  periods.py                 # event-bounded periods and comparability flags
  summaries.py               # SiteAnalysisSummary dataclasses and builder
  uncertainty.py             # value intervals and uncertainty budget rows
  hypotheses.py              # evidence states and caveat ids
  rendering/
    dashboard.py             # index.html from SiteAnalysisSummary
    report.py                # physics-report.html from SiteAnalysisSummary
    charts.py                # SVG from chart specs
```

This is a target boundary, not a requirement to split everything in one commit. The first implementation should extract `summaries.py`, `dashboard.py`, and `charts.py`, then move source/physics helpers only as needed to make the summary builder testable.

## Summary Contract Sketch

```python
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Literal


HypothesisName = Literal[
    "Basement drying",
    "Weather-related leaking",
    "Steady-state leaking",
    "Whole-house humidity change",
    "Sensor/dehumidifier artifact",
]


@dataclass(frozen=True)
class IntervalValue:
    value: float | None
    unit: str
    coverage: str | None
    lower: float | None = None
    upper: float | None = None
    method: str | None = None


@dataclass(frozen=True)
class SiteMetadata:
    generated_at: datetime
    data_window_start: datetime
    data_window_end: datetime
    analysis_version: str
    input_files: tuple[Path, ...]
    sensor_models: tuple[str, ...]
    weather_sources: tuple[str, ...]
    event_timeline_source: Path


@dataclass(frozen=True)
class MetricCard:
    label: str
    value: str
    caveat_ids: tuple[str, ...] = ()


@dataclass(frozen=True)
class PeriodSummary:
    label: str
    start: datetime
    end: datetime
    event_description: str
    comparability_flags: tuple[str, ...]
    sensor_samples: int
    mean_temperature_c: IntervalValue
    mean_relative_humidity_pct: IntervalValue
    mean_absolute_humidity_g_m3: IntervalValue
    outdoor_mean_absolute_humidity_g_m3: IntervalValue
    rain_mm: float


@dataclass(frozen=True)
class ChartSeries:
    name: str
    unit: str
    points: tuple[tuple[datetime, float], ...]
    interval_points: tuple[tuple[datetime, float, float], ...] = ()
    caveat_ids: tuple[str, ...] = ()


@dataclass(frozen=True)
class ChartSpec:
    title: str
    y_label: str
    series: tuple[ChartSeries, ...]
    event_markers: tuple[datetime, ...]
    caveat_ids: tuple[str, ...] = ()


@dataclass(frozen=True)
class HypothesisAssessment:
    name: HypothesisName
    evidence_state: str
    summary: str
    supports: tuple[str, ...]
    weakens: tuple[str, ...]
    next_observations: tuple[str, ...]
    caveat_ids: tuple[str, ...]


@dataclass(frozen=True)
class Caveat:
    id: str
    short_label: str
    dashboard_text: str
    report_text: str
    applies_to: tuple[str, ...]


@dataclass(frozen=True)
class UncertaintyBudgetRow:
    component: str
    applies_to: str
    treatment: str
    included_in_headline_interval: bool
    caveat_ids: tuple[str, ...] = ()


@dataclass(frozen=True)
class SiteAnalysisSummary:
    metadata: SiteMetadata
    metric_cards: tuple[MetricCard, ...]
    period_summaries: tuple[PeriodSummary, ...]
    dashboard_charts: tuple[ChartSpec, ...]
    report_charts: tuple[ChartSpec, ...]
    hypotheses: tuple[HypothesisAssessment, ...]
    caveats: tuple[Caveat, ...]
    uncertainty_budget: tuple[UncertaintyBudgetRow, ...]
    appendix_tables: dict[str, object]
```

## Calculate Once In The Analysis Layer

These values should be produced by `build_site_analysis_summary(...)` or pure helpers it owns:

- sensor readings with absolute humidity derived using named psychrometric constants;
- weather hours with outdoor absolute humidity;
- Environment Agency rainfall readings with validity/missingness flags when available;
- dataset window, source metadata, file list, and analysis version;
- event-bounded periods;
- period comparability flags for sensor moves, dehumidifier/fan/orientation changes, and uncertain event timestamps;
- latest sample metrics and indoor-minus-outdoor absolute humidity;
- hourly and daily chart series used by either page;
- event-bounded period metric rows;
- rainfall totals, rolling/lag features once added;
- uncertainty intervals for headline values, daily means, period means, and rebound rates when implemented;
- uncertainty budget rows and caveat ids;
- hypothesis assessments using the canonical hypothesis names;
- appendix tables for coverage, missingness, event timeline, source hashes, and uncertainty assumptions.

The analysis layer may generate short factual statements such as `summary` on `HypothesisAssessment`, but those statements should be tied to structured evidence fields. Avoid burying unique calculations inside prose.

## Presentation-Only Responsibilities

Dashboard and report renderers may decide:

- page ordering, headings, density, and navigation;
- chart colours, dimensions, axis tick formatting, and legends;
- which shared charts appear on each page;
- whether caveats are shown as short dashboard notes or long report explanations;
- how much of the appendix is expanded by default;
- HTML/CSS and static asset paths;
- links between `index.html`, `physics-report.html`, and downloadable/debug artifacts.

Renderers must not recompute period means, humidity deltas, hypothesis evidence states, uncertainty intervals, rain totals, or comparability flags.

## Page Outputs

First shared-output implementation should generate:

```text
build/basement-site/
  index.html                 # dense owner-analyst dashboard
  physics-report.html        # explanatory physics/metrology report
  analysis-summary.json      # optional debug/export artifact, can follow dataclasses later
  cache/                     # existing weather/rain API cache
```

The dashboard should link to the report near the existing scope note. The report should link back to the dashboard and reuse the same generated timestamp, data window, source metadata, event period summaries, hypothesis assessments, uncertainty budget rows, and caveat ids.

## Caveats And Uncertainty Text

Use structured caveat ids in the analysis summary. The analysis layer decides which caveats apply; renderers decide how long the text is.

Example caveat ids:

- `consumer_sensor_specification`
- `no_sensor_specific_calibration_certificate`
- `sensor_placement_artifact`
- `dehumidifier_control_cycle_artifact`
- `weather_source_mismatch`
- `short_post_dehumidifier_rain_exposure`
- `event_timestamp_uncertainty`

Measurement uncertainty should stay separate from caveats:

- `IntervalValue` carries numeric uncertainty where there is a stated basis.
- `UncertaintyBudgetRow` explains the included components.
- `Caveat` explains qualitative limits that are not in the numeric interval.

## Migration Plan

1. Add `summaries.py` with the shared dataclasses and `build_site_analysis_summary(...)`.
2. Move existing latest-card, daily aggregation, chart-series extraction, period summary, and hypothesis assembly into the summary builder without changing visible output.
3. Change `render_index_html(...)` to accept `SiteAnalysisSummary`.
4. Add `render_physics_report_html(summary)` using the report structure from [Physics And Metrology Report Mock](15-physics-and-metrology-report-mock.md).
5. Make `build_static_site(...)` write both `index.html` and `physics-report.html`.
6. Add focused tests around the summary builder: event-period splitting, period means, latest metrics, chart-series presence, and caveat/hypothesis propagation.

## Verification Used For This Prototype

```bash
uv run basement
```

Result observed:

```text
Wrote build/basement-site/index.html
Sensor rows: 571,021
Weather hours: 3,384
Rain readings: 2,680
```
