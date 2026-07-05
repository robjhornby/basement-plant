from __future__ import annotations

import json
import math
import statistics
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path

import polars as pl

from prototype import CycleSegment, detect_cycle_segments, infer_basement_location


ROOT = Path(__file__).resolve().parents[2]
DATA_DIR = ROOT / "data"
OUT = Path(__file__).with_name("uncertainty_report.html")

TEMP_ACCURACY_HALFWIDTH_C = 0.4
RH_ACCURACY_HALFWIDTH_PCT = 3.5
TEMP_QUANTIZATION_HALFWIDTH_C = 0.05
RH_QUANTIZATION_HALFWIDTH_PCT = 0.05
COVERAGE_FACTOR = 2.0

TEMP_ACCURACY_U_C = TEMP_ACCURACY_HALFWIDTH_C / math.sqrt(3)
RH_ACCURACY_U_PCT = RH_ACCURACY_HALFWIDTH_PCT / math.sqrt(3)
TEMP_QUANTIZATION_U_C = TEMP_QUANTIZATION_HALFWIDTH_C / math.sqrt(3)
RH_QUANTIZATION_U_PCT = RH_QUANTIZATION_HALFWIDTH_PCT / math.sqrt(3)


@dataclass(frozen=True)
class MeanUncertainty:
    label: str
    value: float
    u_standard: float
    u95: float
    samples: int
    temperature_c: float
    relative_humidity_pct: float
    temperature_sensitivity: float
    relative_humidity_sensitivity: float
    independent_u_standard: float


def sensor_label(path: Path) -> str:
    stem = path.name.split("_Export", 1)[0]
    if stem == "Thermo-hygrometer":
        return "Basement (inferred)"
    return stem.replace("Thermo-hygrometer ", "Location ")


def absolute_humidity_expr(temperature: pl.Expr, relative_humidity: pl.Expr) -> pl.Expr:
    saturation_pa = 611.2 * ((17.62 * temperature) / (243.12 + temperature)).exp()
    vapour_pressure_pa = (relative_humidity / 100.0) * saturation_pa
    return 1000.0 * vapour_pressure_pa / (461.5 * (temperature + 273.15))


def sensor_data() -> pl.DataFrame:
    frames: list[pl.DataFrame] = []
    for path in sorted(DATA_DIR.glob("Thermo-hygrometer*_Export Data_*.csv")):
        frames.append(
            pl.read_csv(path, try_parse_dates=True)
            .rename(
                {
                    "Temperature_Celsius": "temperature_c",
                    "Relative Humidity_Percent": "relative_humidity_pct",
                }
            )
            .with_columns(
                pl.lit(path.name).alias("source_file"),
                pl.lit(sensor_label(path)).alias("location"),
            )
        )
    if not frames:
        raise FileNotFoundError(f"No thermohygrometer CSV exports found in {DATA_DIR}")
    return pl.concat(frames).sort(["location", "Time"])


def with_absolute_humidity_uncertainty(df: pl.DataFrame) -> pl.DataFrame:
    temperature = pl.col("temperature_c")
    relative_humidity = pl.col("relative_humidity_pct")
    ah = absolute_humidity_expr(temperature, relative_humidity)
    ah_temp_plus = absolute_humidity_expr(temperature + 0.01, relative_humidity)
    ah_temp_minus = absolute_humidity_expr(temperature - 0.01, relative_humidity)
    ah_rh_plus = absolute_humidity_expr(temperature, relative_humidity + 0.01)
    ah_rh_minus = absolute_humidity_expr(temperature, relative_humidity - 0.01)

    with_sensitivities = df.with_columns(
        ah.alias("absolute_humidity_g_m3"),
        ((ah_temp_plus - ah_temp_minus) / 0.02).alias("ah_per_c"),
        ((ah_rh_plus - ah_rh_minus) / 0.02).alias("ah_per_rh_pct"),
    )
    with_components = with_sensitivities.with_columns(
        (
            (
                (pl.col("ah_per_c") * TEMP_ACCURACY_U_C) ** 2
                + (pl.col("ah_per_rh_pct") * RH_ACCURACY_U_PCT) ** 2
            )
            ** 0.5
        ).alias("ah_common_u"),
        (
            (
                (pl.col("ah_per_c") * TEMP_QUANTIZATION_U_C) ** 2
                + (pl.col("ah_per_rh_pct") * RH_QUANTIZATION_U_PCT) ** 2
            )
            ** 0.5
        ).alias("ah_independent_u"),
    )
    with_standard_uncertainty = with_components.with_columns(
        ((pl.col("ah_common_u") ** 2 + pl.col("ah_independent_u") ** 2) ** 0.5).alias(
            "ah_standard_u"
        )
    )
    return with_standard_uncertainty.with_columns(
        (COVERAGE_FACTOR * pl.col("ah_standard_u")).alias("ah_u95"),
        (pl.col("absolute_humidity_g_m3") - COVERAGE_FACTOR * pl.col("ah_standard_u")).alias(
            "ah_lower95"
        ),
        (pl.col("absolute_humidity_g_m3") + COVERAGE_FACTOR * pl.col("ah_standard_u")).alias(
            "ah_upper95"
        ),
    )


def dehumidifier_install_time() -> datetime:
    events_path = DATA_DIR / "basement_events.csv"
    events = pl.read_csv(events_path)
    row = events.filter(pl.col("Event").str.contains("dehumidifier installed")).row(0, named=True)
    return datetime.strptime(row["Time"], "%Y/%m/%d %H:%M")


def summarize_mean(label: str, df: pl.DataFrame) -> MeanUncertainty:
    if df.is_empty():
        raise ValueError(f"No rows for {label}")
    values = df.select(
        pl.col("absolute_humidity_g_m3").mean().alias("value"),
        pl.col("temperature_c").mean().alias("temperature_c"),
        pl.col("relative_humidity_pct").mean().alias("relative_humidity_pct"),
        pl.col("ah_per_c").mean().alias("temperature_sensitivity"),
        pl.col("ah_per_rh_pct").mean().alias("relative_humidity_sensitivity"),
        pl.col("ah_independent_u").pow(2).sum().alias("independent_variance_sum"),
        pl.len().alias("samples"),
    ).row(0, named=True)
    samples = int(values["samples"])
    independent_u = math.sqrt(float(values["independent_variance_sum"])) / samples
    common_u = math.sqrt(
        (float(values["temperature_sensitivity"]) * TEMP_ACCURACY_U_C) ** 2
        + (float(values["relative_humidity_sensitivity"]) * RH_ACCURACY_U_PCT) ** 2
    )
    u_standard = math.sqrt(common_u**2 + independent_u**2)
    return MeanUncertainty(
        label=label,
        value=float(values["value"]),
        u_standard=u_standard,
        u95=COVERAGE_FACTOR * u_standard,
        samples=samples,
        temperature_c=float(values["temperature_c"]),
        relative_humidity_pct=float(values["relative_humidity_pct"]),
        temperature_sensitivity=float(values["temperature_sensitivity"]),
        relative_humidity_sensitivity=float(values["relative_humidity_sensitivity"]),
        independent_u_standard=independent_u,
    )


def same_sensor_delta_u95(after: MeanUncertainty, before: MeanUncertainty) -> float:
    common_delta_u = math.sqrt(
        ((after.temperature_sensitivity - before.temperature_sensitivity) * TEMP_ACCURACY_U_C) ** 2
        + (
            (after.relative_humidity_sensitivity - before.relative_humidity_sensitivity)
            * RH_ACCURACY_U_PCT
        )
        ** 2
    )
    independent_delta_u = math.sqrt(
        after.independent_u_standard**2 + before.independent_u_standard**2
    )
    return COVERAGE_FACTOR * math.sqrt(common_delta_u**2 + independent_delta_u**2)


def grouped_means(df: pl.DataFrame, every: str) -> list[dict[str, object]]:
    rows = (
        df.group_by_dynamic("Time", every=every)
        .agg(
            pl.col("absolute_humidity_g_m3").mean().alias("value"),
            pl.col("relative_humidity_pct").mean().alias("relative_humidity_pct"),
            pl.col("temperature_c").mean().alias("temperature_c"),
            pl.col("ah_per_c").mean().alias("temperature_sensitivity"),
            pl.col("ah_per_rh_pct").mean().alias("relative_humidity_sensitivity"),
            pl.col("ah_independent_u").pow(2).sum().alias("independent_variance_sum"),
            pl.len().alias("samples"),
        )
        .drop_nulls()
        .sort("Time")
        .to_dicts()
    )
    output: list[dict[str, object]] = []
    for row in rows:
        samples = int(row["samples"])
        independent_u = math.sqrt(float(row["independent_variance_sum"])) / samples
        common_u = math.sqrt(
            (float(row["temperature_sensitivity"]) * TEMP_ACCURACY_U_C) ** 2
            + (float(row["relative_humidity_sensitivity"]) * RH_ACCURACY_U_PCT) ** 2
        )
        u95 = COVERAGE_FACTOR * math.sqrt(common_u**2 + independent_u**2)
        value = float(row["value"])
        time_value = row["Time"]
        time_label = (
            time_value.strftime("%Y-%m-%d")
            if every == "1d"
            else time_value.strftime("%Y-%m-%d %H:%M")
        )
        output.append(
            {
                "time": time_label,
                "value": round(value, 4),
                "lower95": round(value - u95, 4),
                "upper95": round(value + u95, 4),
                "u95": round(u95, 4),
                "relativeHumidityPct": round(float(row["relative_humidity_pct"]), 3),
                "temperatureC": round(float(row["temperature_c"]), 3),
                "samples": samples,
            }
        )
    return output


def nearest_group_row(rows: dict[datetime, dict[str, object]], timestamp: datetime) -> dict[str, object]:
    if timestamp in rows:
        return rows[timestamp]
    return rows[min(rows, key=lambda candidate: abs(candidate - timestamp))]


def rebound_payload(post: pl.DataFrame, cycles: list[CycleSegment]) -> list[dict[str, object]]:
    grouped = (
        post.group_by_dynamic("Time", every="5m")
        .agg(
            pl.col("absolute_humidity_g_m3").mean().alias("value"),
            pl.col("relative_humidity_pct").mean().alias("relative_humidity_pct"),
            pl.col("temperature_c").mean().alias("temperature_c"),
            pl.col("ah_per_c").mean().alias("temperature_sensitivity"),
            pl.col("ah_per_rh_pct").mean().alias("relative_humidity_sensitivity"),
            pl.col("ah_independent_u").pow(2).sum().alias("independent_variance_sum"),
            pl.len().alias("samples"),
        )
        .drop_nulls()
        .sort("Time")
        .to_dicts()
    )
    rows_by_time = {row["Time"]: row for row in grouped}
    payload: list[dict[str, object]] = []
    for segment in cycles:
        if segment.kind != "rebound":
            continue
        start = nearest_group_row(rows_by_time, segment.start)
        end = nearest_group_row(rows_by_time, segment.end)
        start_samples = int(start["samples"])
        end_samples = int(end["samples"])
        start_independent_u = math.sqrt(float(start["independent_variance_sum"])) / start_samples
        end_independent_u = math.sqrt(float(end["independent_variance_sum"])) / end_samples
        delta_u = math.sqrt(
            (
                (float(end["temperature_sensitivity"]) - float(start["temperature_sensitivity"]))
                * TEMP_ACCURACY_U_C
            )
            ** 2
            + (
                (
                    float(end["relative_humidity_sensitivity"])
                    - float(start["relative_humidity_sensitivity"])
                )
                * RH_ACCURACY_U_PCT
            )
            ** 2
            + start_independent_u**2
            + end_independent_u**2
        )
        hours = segment.minutes / 60.0
        rate = segment.ah_rate_per_hour
        u95 = COVERAGE_FACTOR * delta_u / hours
        payload.append(
            {
                "end": segment.end.strftime("%Y-%m-%d %H:%M"),
                "minutes": round(segment.minutes, 1),
                "rate": round(rate, 4),
                "lower95": round(rate - u95, 4),
                "upper95": round(rate + u95, 4),
                "u95": round(u95, 4),
            }
        )
    return payload


def median(values: list[float]) -> float | None:
    clean = [value for value in values if math.isfinite(value)]
    if not clean:
        return None
    return statistics.median(clean)


def median_rebound_summary(
    rebounds: list[dict[str, object]], start: datetime, end: datetime
) -> dict[str, float | int | None]:
    rows = [
        row
        for row in rebounds
        if start <= datetime.strptime(str(row["end"]), "%Y-%m-%d %H:%M") < end
    ]
    return {
        "count": len(rows),
        "rate": median([float(row["rate"]) for row in rows]),
        "typical_u95": median([float(row["u95"]) for row in rows]),
        "minutes": median([float(row["minutes"]) for row in rows]),
    }


def fmt_interval(value: float | None, u95: float | None, digits: int = 2) -> str:
    if value is None or u95 is None:
        return "n/a"
    return f"{value:.{digits}f} +/- {u95:.{digits}f}"


def render_html(payload: dict[str, object]) -> str:
    data = json.dumps(payload, default=str)
    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Basement Uncertainty Prototype</title>
  <link rel="icon" href="data:,">
  <script src="https://cdn.plot.ly/plotly-2.35.2.min.js"></script>
  <style>
    :root {{
      color-scheme: light;
      --ink: #18212f;
      --muted: #667085;
      --line: #d8dee8;
      --panel: #f6f8fb;
      --teal: #0f766e;
      --violet: #6d28d9;
      --amber: #b45309;
    }}
    body {{
      margin: 0;
      color: var(--ink);
      background: #fff;
      font: 15px/1.45 -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
    }}
    header {{
      padding: 22px 28px 14px;
      border-bottom: 1px solid var(--line);
    }}
    main {{
      max-width: 1240px;
      padding: 0 28px 34px;
    }}
    h1 {{
      margin: 0 0 5px;
      font-size: 24px;
      letter-spacing: 0;
    }}
    h2 {{
      margin: 28px 0 12px;
      font-size: 18px;
      letter-spacing: 0;
    }}
    .subtle {{ color: var(--muted); }}
    .grid {{
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(210px, 1fr));
      gap: 10px;
      margin: 18px 0;
    }}
    .card {{
      min-height: 82px;
      padding: 12px;
      border: 1px solid var(--line);
      border-radius: 8px;
      background: #fff;
    }}
    .label {{
      color: var(--muted);
      font-size: 12px;
      letter-spacing: .04em;
      text-transform: uppercase;
    }}
    .value {{
      margin-top: 6px;
      font-size: 20px;
      font-weight: 650;
      letter-spacing: 0;
    }}
    .chart {{
      width: 100%;
      height: 430px;
      border: 1px solid var(--line);
      border-radius: 8px;
    }}
    .note {{
      max-width: 940px;
      padding: 12px 14px;
      margin: 18px 0;
      background: var(--panel);
      border-left: 4px solid var(--teal);
    }}
    table {{
      width: 100%;
      border-collapse: collapse;
      margin-top: 8px;
      font-size: 13px;
    }}
    th, td {{
      padding: 7px 8px;
      border-bottom: 1px solid var(--line);
      text-align: right;
      white-space: nowrap;
    }}
    th:first-child, td:first-child {{ text-align: left; }}
    @media (max-width: 720px) {{
      header, main {{ padding-left: 14px; padding-right: 14px; }}
      .chart {{ height: 360px; }}
      table {{ display: block; overflow-x: auto; }}
    }}
  </style>
</head>
<body>
  <header>
    <h1>Basement uncertainty prototype</h1>
    <div class="subtle">Throwaway report for first-pass 95% coverage intervals on absolute humidity, daily means, and rebound rates.</div>
  </header>
  <main>
    <section class="grid" id="cards"></section>
    <p class="note">
      Intervals use the STH51 manufacturer accuracy as Type B rectangular components plus CSV quantization.
      Fixed sensor accuracy is treated as common within a same-sensor period, so daily means do not gain fake precision from thousands of one-minute samples.
      Placement, airflow, drift, weather, and model uncertainty are deliberately labelled as outside this first charting prototype.
    </p>
    <h2>Post-install absolute humidity band</h2>
    <div id="postBand" class="chart"></div>
    <h2>Daily mean absolute humidity with intervals</h2>
    <div id="dailyBars" class="chart"></div>
    <h2>Off-cycle rebound rates with intervals</h2>
    <div id="reboundRates" class="chart"></div>
    <h2>Budget used in this throwaway run</h2>
    <div id="budget"></div>
  </main>
  <script>
    const payload = {data};
    const fmt = (value, digits = 2) => value === null || value === undefined ? "n/a" : Number(value).toFixed(digits);
    const interval = (value, u95, digits = 2) => value === null || u95 === null ? "n/a" : `${{fmt(value, digits)}} +/- ${{fmt(u95, digits)}}`;
    const cards = [
      ["Basement source", payload.basementLocation],
      ["Physical install time", payload.installTime],
      ["Pre mean AH g/m3", interval(payload.pre.value, payload.pre.u95, 2)],
      ["Post mean AH g/m3", interval(payload.post.value, payload.post.u95, 2)],
      ["Post - pre AH g/m3", interval(payload.delta.value, payload.delta.u95, 2)],
      ["Latest rebound g/m3/hr", interval(payload.latestRebound.rate, payload.latestRebound.typical_u95, 2)]
    ];
    document.getElementById("cards").innerHTML = cards.map(([label, value]) => `
      <div class="card"><div class="label">${{label}}</div><div class="value">${{value}}</div></div>
    `).join("");

    const post = payload.postPoints;
    Plotly.newPlot("postBand", [
      {{
        x: post.map(d => d.time),
        y: post.map(d => d.upper95),
        name: "Upper 95%",
        type: "scatter",
        mode: "lines",
        line: {{ color: "rgba(109, 40, 217, 0.18)", width: 0 }},
        hoverinfo: "skip"
      }},
      {{
        x: post.map(d => d.time),
        y: post.map(d => d.lower95),
        name: "Approx 95% band",
        type: "scatter",
        mode: "lines",
        fill: "tonexty",
        fillcolor: "rgba(109, 40, 217, 0.18)",
        line: {{ color: "rgba(109, 40, 217, 0.18)", width: 0 }},
        hoverinfo: "skip"
      }},
      {{
        x: post.map(d => d.time),
        y: post.map(d => d.value),
        name: "Absolute humidity",
        type: "scatter",
        mode: "lines",
        line: {{ color: "#6d28d9", width: 2 }}
      }}
    ], {{
      margin: {{ t: 24, r: 24, l: 64, b: 44 }},
      hovermode: "x unified",
      legend: {{ orientation: "h" }},
      yaxis: {{ title: "g/m3" }}
    }}, {{ responsive: true }});

    const daily = payload.daily;
    Plotly.newPlot("dailyBars", [
      {{
        x: daily.map(d => d.time),
        y: daily.map(d => d.value),
        name: "Daily mean AH",
        type: "bar",
        marker: {{ color: "#0f766e" }},
        error_y: {{ type: "data", array: daily.map(d => d.u95), visible: true, color: "#18212f", thickness: 1.2 }}
      }}
    ], {{
      margin: {{ t: 24, r: 24, l: 64, b: 70 }},
      yaxis: {{ title: "g/m3" }}
    }}, {{ responsive: true }});

    const rebounds = payload.rebounds;
    Plotly.newPlot("reboundRates", [
      {{
        x: rebounds.map(d => d.end),
        y: rebounds.map(d => d.rate),
        name: "Rebound rate",
        type: "scatter",
        mode: "lines+markers",
        line: {{ color: "#b45309", width: 1.5 }},
        marker: {{ size: 6 }},
        error_y: {{ type: "data", array: rebounds.map(d => d.u95), visible: true, color: "#18212f", thickness: 1 }}
      }}
    ], {{
      margin: {{ t: 24, r: 24, l: 64, b: 44 }},
      hovermode: "x unified",
      yaxis: {{ title: "g/m3 per hour" }}
    }}, {{ responsive: true }});

    document.getElementById("budget").innerHTML = `<table>
      <thead><tr><th>Component</th><th>Half-width</th><th>Distribution</th><th>Treatment</th></tr></thead>
      <tbody>
        <tr><td>Temperature manufacturer accuracy</td><td>+/-${{payload.budget.tempAccuracyHalfwidthC}} C</td><td>Rectangular</td><td>Common within same sensor period</td></tr>
        <tr><td>RH manufacturer accuracy</td><td>+/-${{payload.budget.rhAccuracyHalfwidthPct}} %RH</td><td>Rectangular</td><td>Common within same sensor period</td></tr>
        <tr><td>Temperature CSV quantization</td><td>+/-${{payload.budget.tempQuantizationHalfwidthC}} C</td><td>Rectangular</td><td>Independent reading component</td></tr>
        <tr><td>RH CSV quantization</td><td>+/-${{payload.budget.rhQuantizationHalfwidthPct}} %RH</td><td>Rectangular</td><td>Independent reading component</td></tr>
        <tr><td>Coverage factor</td><td>k = ${{payload.budget.coverageFactor}}</td><td>Approx normal reporting</td><td>Labelled approximate 95% coverage interval</td></tr>
      </tbody>
    </table>`;
  </script>
</body>
</html>
"""


def mean_payload(summary: MeanUncertainty) -> dict[str, object]:
    return {
        "label": summary.label,
        "value": round(summary.value, 4),
        "u95": round(summary.u95, 4),
        "samples": summary.samples,
        "temperatureC": round(summary.temperature_c, 3),
        "relativeHumidityPct": round(summary.relative_humidity_pct, 3),
    }


def main() -> None:
    all_data = with_absolute_humidity_uncertainty(sensor_data())
    basement_location = infer_basement_location(all_data)
    basement = all_data.filter(pl.col("location") == basement_location).sort("Time")
    install_time = dehumidifier_install_time()
    pre = basement.filter(
        (pl.col("Time") >= install_time - timedelta(days=7)) & (pl.col("Time") < install_time)
    )
    post = basement.filter(pl.col("Time") >= install_time)
    pre_mean = summarize_mean("pre", pre)
    post_mean = summarize_mean("post", post)
    delta_value = post_mean.value - pre_mean.value
    delta_u95 = same_sensor_delta_u95(post_mean, pre_mean)
    cycles = detect_cycle_segments(post)
    rebounds = rebound_payload(post, cycles)
    first_rebound = median_rebound_summary(
        rebounds, install_time, install_time + timedelta(hours=36)
    )
    latest_start = basement.select(pl.col("Time").max()).item() - timedelta(hours=36)
    latest_rebound = median_rebound_summary(
        rebounds,
        latest_start,
        basement.select(pl.col("Time").max()).item() + timedelta(minutes=1),
    )

    payload = {
        "basementLocation": basement_location,
        "installTime": install_time.strftime("%Y-%m-%d %H:%M"),
        "pre": mean_payload(pre_mean),
        "post": mean_payload(post_mean),
        "delta": {"value": round(delta_value, 4), "u95": round(delta_u95, 4)},
        "firstRebound": first_rebound,
        "latestRebound": latest_rebound,
        "postPoints": grouped_means(post, every="15m"),
        "daily": grouped_means(basement, every="1d"),
        "rebounds": rebounds,
        "budget": {
            "tempAccuracyHalfwidthC": TEMP_ACCURACY_HALFWIDTH_C,
            "rhAccuracyHalfwidthPct": RH_ACCURACY_HALFWIDTH_PCT,
            "tempQuantizationHalfwidthC": TEMP_QUANTIZATION_HALFWIDTH_C,
            "rhQuantizationHalfwidthPct": RH_QUANTIZATION_HALFWIDTH_PCT,
            "coverageFactor": COVERAGE_FACTOR,
        },
    }

    OUT.write_text(render_html(payload), encoding="utf-8")
    print(f"Wrote {OUT}")
    print(f"Basement source: {basement_location}")
    print(f"Physical dehumidifier install time: {payload['installTime']}")
    print(f"Pre mean AH: {fmt_interval(pre_mean.value, pre_mean.u95)} g/m3")
    print(f"Post mean AH: {fmt_interval(post_mean.value, post_mean.u95)} g/m3")
    print(f"Post - pre AH: {fmt_interval(delta_value, delta_u95)} g/m3")
    print(
        "Latest rebound rate: "
        f"{fmt_interval(latest_rebound['rate'], latest_rebound['typical_u95'])} g/m3/hr"
    )


if __name__ == "__main__":
    main()
