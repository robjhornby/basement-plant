from __future__ import annotations

import json
import math
import statistics
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path

import polars as pl


ROOT = Path(__file__).resolve().parents[2]
DATA_DIR = ROOT / "data"
OUT = Path(__file__).with_name("report.html")


@dataclass(frozen=True)
class CycleSegment:
    kind: str
    start: datetime
    end: datetime
    minutes: float
    start_rh: float
    end_rh: float
    start_ah: float
    end_ah: float
    mean_temp: float

    @property
    def rh_rate_per_hour(self) -> float:
        return (self.end_rh - self.start_rh) / (self.minutes / 60)

    @property
    def ah_rate_per_hour(self) -> float:
        return (self.end_ah - self.start_ah) / (self.minutes / 60)


def absolute_humidity_expr(temp_col: str, rh_col: str) -> pl.Expr:
    temp = pl.col(temp_col)
    rh = pl.col(rh_col)
    saturation_hpa = 6.112 * ((17.67 * temp) / (temp + 243.5)).exp()
    actual_hpa = (rh / 100.0) * saturation_hpa
    return (216.7 * actual_hpa / (temp + 273.15)).alias("absolute_humidity_g_m3")


def sensor_label(path: Path) -> str:
    stem = path.name.split("_Export", 1)[0]
    if stem == "Thermo-hygrometer":
        return "Basement (inferred)"
    return stem.replace("Thermo-hygrometer ", "Location ")


def load_all() -> pl.DataFrame:
    frames: list[pl.DataFrame] = []
    for path in sorted(DATA_DIR.glob("*.csv")):
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
                absolute_humidity_expr("temperature_c", "relative_humidity_pct"),
            )
        )
    return pl.concat(frames).sort(["location", "Time"])


def infer_basement_location(df: pl.DataFrame) -> str:
    summary = (
        df.group_by("location")
        .agg(
            pl.col("relative_humidity_pct").median().alias("median_rh"),
            pl.col("temperature_c").median().alias("median_temp"),
        )
        .sort(["median_rh", "median_temp"], descending=[True, False])
    )
    return summary.item(0, "location")


def infer_dehumidifier_start(df: pl.DataFrame) -> datetime:
    daily = (
        df.group_by_dynamic("Time", every="1d")
        .agg(
            pl.col("relative_humidity_pct").mean().alias("mean_rh"),
            pl.col("relative_humidity_pct").min().alias("min_rh"),
            pl.col("relative_humidity_pct").max().alias("max_rh"),
            pl.len().alias("n"),
        )
        .with_columns((pl.col("max_rh") - pl.col("min_rh")).alias("rh_range"))
        .sort("Time")
    )
    candidates = daily.filter(
        (pl.col("n") > 1000)
        & (pl.col("rh_range") >= 20)
        & (pl.col("min_rh") <= 65)
        & (pl.col("max_rh") >= 80)
    )
    if candidates.height:
        day_start = candidates.item(0, "Time")
        day_end = day_start + timedelta(days=1)
        day = (
            df.filter(pl.col("Time").is_between(day_start, day_end, closed="left"))
            .group_by_dynamic("Time", every="5m")
            .agg(pl.col("relative_humidity_pct").mean().alias("rh"))
            .sort("Time")
            .to_dicts()
        )
        for i, start_row in enumerate(day):
            start_rh = float(start_row["rh"])
            if start_rh < 80:
                continue
            start_time = start_row["Time"]
            for end_row in day[i + 1 :]:
                minutes = (end_row["Time"] - start_time).total_seconds() / 60
                if minutes > 180:
                    break
                end_rh = float(end_row["rh"])
                if start_rh - end_rh >= 20 and end_rh <= 65:
                    return start_time
        return day_start

    # Fallback: first sustained move below 70% after the dataset has spent time above 80%.
    rolling = df.with_columns(
        pl.col("relative_humidity_pct").rolling_mean(window_size=60).alias("rh_60m")
    )
    candidates = rolling.filter((pl.col("Time") > df.item(0, "Time")) & (pl.col("rh_60m") < 70))
    if candidates.height:
        return candidates.item(0, "Time").replace(hour=0, minute=0, second=0, microsecond=0)
    return df.item(0, "Time")


def points_for_plot(df: pl.DataFrame, every: str = "15m") -> list[dict[str, object]]:
    return (
        df.group_by_dynamic("Time", every=every)
        .agg(
            pl.col("relative_humidity_pct").mean().round(2).alias("rh"),
            pl.col("temperature_c").mean().round(2).alias("temp"),
            pl.col("absolute_humidity_g_m3").mean().round(3).alias("ah"),
        )
        .drop_nulls()
        .sort("Time")
        .with_columns(pl.col("Time").dt.strftime("%Y-%m-%d %H:%M").alias("time"))
        .select(["time", "rh", "temp", "ah"])
        .to_dicts()
    )


def daily_summary(df: pl.DataFrame) -> list[dict[str, object]]:
    return (
        df.group_by_dynamic("Time", every="1d")
        .agg(
            pl.col("relative_humidity_pct").mean().round(2).alias("mean_rh"),
            pl.col("relative_humidity_pct").min().round(2).alias("min_rh"),
            pl.col("relative_humidity_pct").max().round(2).alias("max_rh"),
            pl.col("absolute_humidity_g_m3").mean().round(3).alias("mean_ah"),
            pl.col("temperature_c").mean().round(2).alias("mean_temp"),
            pl.len().alias("samples"),
        )
        .sort("Time")
        .with_columns(pl.col("Time").dt.strftime("%Y-%m-%d").alias("day"))
        .select(["day", "mean_rh", "min_rh", "max_rh", "mean_ah", "mean_temp", "samples"])
        .to_dicts()
    )


def detect_cycle_segments(df: pl.DataFrame) -> list[CycleSegment]:
    sampled = (
        df.group_by_dynamic("Time", every="5m")
        .agg(
            pl.col("relative_humidity_pct").mean().alias("rh"),
            pl.col("absolute_humidity_g_m3").mean().alias("ah"),
            pl.col("temperature_c").mean().alias("temp"),
        )
        .sort("Time")
        .with_columns(pl.col("rh").rolling_mean(window_size=3, center=True).alias("rh_smooth"))
        .drop_nulls()
    )

    rows = sampled.to_dicts()
    extrema: list[dict[str, object]] = []
    last_kind = None
    for prev, cur, nxt in zip(rows, rows[1:], rows[2:]):
        prev_rh = float(prev["rh_smooth"])
        cur_rh = float(cur["rh_smooth"])
        nxt_rh = float(nxt["rh_smooth"])
        if cur_rh >= prev_rh and cur_rh > nxt_rh:
            kind = "peak"
        elif cur_rh <= prev_rh and cur_rh < nxt_rh:
            kind = "trough"
        else:
            continue
        if kind == last_kind:
            extrema[-1] = cur
            extrema[-1]["kind"] = kind
        else:
            cur["kind"] = kind
            extrema.append(cur)
            last_kind = kind

    segments: list[CycleSegment] = []
    for a, b in zip(extrema, extrema[1:]):
        start = a["Time"]
        end = b["Time"]
        minutes = (end - start).total_seconds() / 60
        if minutes < 15 or minutes > 8 * 60:
            continue
        delta_rh = float(b["rh"]) - float(a["rh"])
        if abs(delta_rh) < 3:
            continue
        kind = "rebound" if a["kind"] == "trough" and b["kind"] == "peak" else "drying"
        if kind == "rebound" and delta_rh <= 0:
            continue
        if kind == "drying" and delta_rh >= 0:
            continue
        period = sampled.filter(pl.col("Time").is_between(start, end))
        segments.append(
            CycleSegment(
                kind=kind,
                start=start,
                end=end,
                minutes=minutes,
                start_rh=float(a["rh"]),
                end_rh=float(b["rh"]),
                start_ah=float(a["ah"]),
                end_ah=float(b["ah"]),
                mean_temp=float(period.select(pl.col("temp").mean()).item()),
            )
        )
    return segments


def median(values: list[float]) -> float | None:
    clean = [v for v in values if math.isfinite(v)]
    if not clean:
        return None
    return statistics.median(clean)


def period_metrics(segments: list[CycleSegment], start: datetime, end: datetime) -> dict[str, float | int | None]:
    rebounds = [s for s in segments if s.kind == "rebound" and start <= s.start < end]
    drying = [s for s in segments if s.kind == "drying" and start <= s.start < end]
    return {
        "rebound_count": len(rebounds),
        "drying_count": len(drying),
        "median_rebound_rh_pp_per_hour": median([s.rh_rate_per_hour for s in rebounds]),
        "median_rebound_ah_g_m3_per_hour": median([s.ah_rate_per_hour for s in rebounds]),
        "median_rebound_minutes": median([s.minutes for s in rebounds]),
        "median_drying_minutes": median([s.minutes for s in drying]),
    }


def metric_card(value: object, suffix: str = "") -> str:
    if value is None:
        return "n/a"
    if isinstance(value, float):
        return f"{value:.2f}{suffix}"
    return f"{value}{suffix}"


def render_html(payload: dict[str, object]) -> str:
    data = json.dumps(payload, default=str)
    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Basement Humidity Prototype</title>
  <link rel="icon" href="data:,">
  <script src="https://cdn.plot.ly/plotly-2.35.2.min.js"></script>
  <style>
    :root {{
      color-scheme: light;
      --ink: #17202a;
      --muted: #667085;
      --line: #d7dde5;
      --panel: #f6f8fa;
      --accent: #126b5f;
      --warn: #a14a12;
    }}
    body {{
      margin: 0;
      font: 15px/1.45 -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
      color: var(--ink);
      background: #ffffff;
    }}
    header {{
      padding: 24px 28px 14px;
      border-bottom: 1px solid var(--line);
    }}
    h1 {{
      margin: 0 0 6px;
      font-size: 24px;
      letter-spacing: 0;
    }}
    h2 {{
      margin: 28px 0 12px;
      font-size: 18px;
      letter-spacing: 0;
    }}
    main {{
      padding: 0 28px 36px;
      max-width: 1280px;
    }}
    .subtle {{ color: var(--muted); }}
    .grid {{
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(180px, 1fr));
      gap: 10px;
      margin: 18px 0;
    }}
    .card {{
      border: 1px solid var(--line);
      border-radius: 8px;
      padding: 12px;
      background: #fff;
      min-height: 74px;
    }}
    .label {{
      color: var(--muted);
      font-size: 12px;
      text-transform: uppercase;
      letter-spacing: .04em;
    }}
    .value {{
      margin-top: 6px;
      font-size: 22px;
      font-weight: 650;
      letter-spacing: 0;
    }}
    .chart {{
      width: 100%;
      height: 440px;
      border: 1px solid var(--line);
      border-radius: 8px;
    }}
    table {{
      border-collapse: collapse;
      width: 100%;
      margin-top: 8px;
      font-size: 13px;
    }}
    th, td {{
      border-bottom: 1px solid var(--line);
      padding: 7px 8px;
      text-align: right;
      white-space: nowrap;
    }}
    th:first-child, td:first-child {{ text-align: left; }}
    .note {{
      background: var(--panel);
      border-left: 4px solid var(--accent);
      padding: 12px 14px;
      margin: 18px 0;
      max-width: 900px;
    }}
    @media (max-width: 720px) {{
      header, main {{ padding-left: 14px; padding-right: 14px; }}
      .chart {{ height: 360px; }}
      table {{ display: block; overflow-x: auto; }}
    }}
  </style>
</head>
<body>
  <header>
    <h1>Basement humidity prototype</h1>
    <div class="subtle">Throwaway report generated from the three thermohygrometer CSV exports.</div>
  </header>
  <main>
    <section class="grid" id="cards"></section>
    <p class="note">
      The basement sensor is inferred as the unnumbered thermohygrometer because it has the highest humidity and lowest temperature.
      The dehumidifier period is inferred from the first large high-to-low RH transition on the first day with a large RH range.
      Rebound rate measures moisture returning after a drying trough, using absolute humidity to reduce temperature bias.
    </p>
    <h2>Basement period after inferred dehumidifier install</h2>
    <div id="basementChart" class="chart"></div>
    <h2>Off-cycle rebound rate</h2>
    <div id="reboundChart" class="chart"></div>
    <h2>Daily basement summary</h2>
    <div id="dailyChart" class="chart"></div>
    <h2>All sensor context</h2>
    <div id="allChart" class="chart"></div>
    <h2>Detected cycle segments</h2>
    <div id="cycles"></div>
  </main>
  <script>
    const payload = {data};
    const fmt = (v, digits = 2) => v === null || v === undefined ? "n/a" : Number(v).toFixed(digits);
    const cards = [
      ["Basement source", payload.basementLocation],
      ["Inferred install time", payload.installTime],
      ["Pre-install mean RH", fmt(payload.pre.mean_rh) + "%"],
      ["Post-install mean RH", fmt(payload.post.mean_rh) + "%"],
      ["Mean RH change", fmt(payload.improvement.mean_rh_delta_pp) + " pp"],
      ["Mean absolute humidity change", fmt(payload.improvement.mean_ah_delta_g_m3, 3) + " g/m³"],
      ["Latest rebound rate", fmt(payload.latest.median_rebound_ah_g_m3_per_hour, 3) + " g/m³/hr"],
      ["Latest rebound interval", fmt(payload.latest.median_rebound_minutes, 0) + " min"],
    ];
    document.getElementById("cards").innerHTML = cards.map(([label, value]) => `
      <div class="card"><div class="label">${{label}}</div><div class="value">${{value}}</div></div>
    `).join("");

    const basement = payload.basementPoints;
    const times = basement.map(d => d.time);
    Plotly.newPlot("basementChart", [
      {{ x: times, y: basement.map(d => d.rh), name: "RH %", type: "scatter", mode: "lines", line: {{ color: "#126b5f", width: 2 }} }},
      {{ x: times, y: basement.map(d => d.ah), name: "Absolute humidity g/m³", yaxis: "y2", type: "scatter", mode: "lines", line: {{ color: "#7c3aed", width: 2 }} }},
      {{ x: times, y: basement.map(d => d.temp), name: "Temp C", yaxis: "y3", type: "scatter", mode: "lines", line: {{ color: "#a14a12", width: 1.5 }} }}
    ], {{
      margin: {{ t: 24, r: 70, l: 52, b: 44 }},
      hovermode: "x unified",
      legend: {{ orientation: "h" }},
      yaxis: {{ title: "RH %", range: [45, 95] }},
      yaxis2: {{ title: "g/m³", overlaying: "y", side: "right" }},
      yaxis3: {{ title: "C", overlaying: "y", side: "right", position: 0.94, showgrid: false }},
      shapes: [
        {{ type: "line", x0: payload.installTime, x1: payload.installTime, y0: 0, y1: 1, xref: "x", yref: "paper", line: {{ color: "#111827", dash: "dot" }} }}
      ]
    }}, {{ responsive: true }});

    const rollingMedian = (values, windowSize) => values.map((_, index) => {{
      const start = Math.max(0, index - windowSize + 1);
      const window = values.slice(start, index + 1).filter(v => Number.isFinite(v)).sort((a, b) => a - b);
      if (!window.length) return null;
      const mid = Math.floor(window.length / 2);
      return window.length % 2 ? window[mid] : (window[mid - 1] + window[mid]) / 2;
    }});
    const rebounds = payload.cycles.filter(c => c.kind === "rebound");
    const reboundX = rebounds.map(c => c.end);
    const reboundAh = rebounds.map(c => c.ah_rate_per_hour);
    Plotly.newPlot("reboundChart", [
      {{
        x: reboundX,
        y: reboundAh,
        name: "Rebound AH rate",
        type: "scatter",
        mode: "lines+markers",
        line: {{ color: "#7c3aed", width: 1.5 }},
        marker: {{ size: 6 }}
      }},
      {{
        x: reboundX,
        y: rollingMedian(reboundAh, 8),
        name: "8-cycle rolling median",
        type: "scatter",
        mode: "lines",
        line: {{ color: "#111827", width: 3 }}
      }}
    ], {{
      margin: {{ t: 24, r: 24, l: 62, b: 44 }},
      hovermode: "x unified",
      legend: {{ orientation: "h" }},
      yaxis: {{ title: "g/m³ per hour" }},
      shapes: [
        {{ type: "line", x0: payload.installTime, x1: payload.installTime, y0: 0, y1: 1, xref: "x", yref: "paper", line: {{ color: "#111827", dash: "dot" }} }}
      ]
    }}, {{ responsive: true }});

    const daily = payload.daily;
    Plotly.newPlot("dailyChart", [
      {{ x: daily.map(d => d.day), y: daily.map(d => d.mean_rh), name: "Daily mean RH %", type: "bar", marker: {{ color: "#126b5f" }} }},
      {{ x: daily.map(d => d.day), y: daily.map(d => d.mean_ah), name: "Daily mean AH g/m³", yaxis: "y2", type: "scatter", mode: "lines+markers", line: {{ color: "#7c3aed" }} }}
    ], {{
      margin: {{ t: 24, r: 62, l: 52, b: 70 }},
      hovermode: "x unified",
      legend: {{ orientation: "h" }},
      yaxis: {{ title: "RH %" }},
      yaxis2: {{ title: "g/m³", overlaying: "y", side: "right" }}
    }}, {{ responsive: true }});

    const byLocation = Object.groupBy(payload.allPoints, d => d.location);
    Plotly.newPlot("allChart", Object.entries(byLocation).map(([location, rows]) => ({{
      x: rows.map(d => d.time),
      y: rows.map(d => d.rh),
      name: location,
      type: "scatter",
      mode: "lines"
    }})), {{
      margin: {{ t: 24, r: 24, l: 52, b: 44 }},
      hovermode: "x unified",
      legend: {{ orientation: "h" }},
      yaxis: {{ title: "RH %" }}
    }}, {{ responsive: true }});

    const cycleRows = payload.cycles.slice(-80).reverse();
    document.getElementById("cycles").innerHTML = `<table>
      <thead><tr><th>Kind</th><th>Start</th><th>End</th><th>Minutes</th><th>RH start</th><th>RH end</th><th>RH pp/hr</th><th>AH g/m³/hr</th><th>Temp C</th></tr></thead>
      <tbody>${{cycleRows.map(c => `<tr>
        <td>${{c.kind}}</td><td>${{c.start}}</td><td>${{c.end}}</td>
        <td>${{fmt(c.minutes, 0)}}</td><td>${{fmt(c.start_rh)}}</td><td>${{fmt(c.end_rh)}}</td>
        <td>${{fmt(c.rh_rate_per_hour)}}</td><td>${{fmt(c.ah_rate_per_hour, 3)}}</td><td>${{fmt(c.mean_temp)}}</td>
      </tr>`).join("")}}</tbody>
    </table>`;
  </script>
</body>
</html>
"""


def mean_metrics(df: pl.DataFrame) -> dict[str, float | int | None]:
    if df.is_empty():
        return {"mean_rh": None, "mean_ah": None, "mean_temp": None, "samples": 0}
    row = df.select(
        pl.col("relative_humidity_pct").mean().alias("mean_rh"),
        pl.col("absolute_humidity_g_m3").mean().alias("mean_ah"),
        pl.col("temperature_c").mean().alias("mean_temp"),
        pl.len().alias("samples"),
    ).row(0, named=True)
    return row


def main() -> None:
    all_data = load_all()
    basement_location = infer_basement_location(all_data)
    basement = all_data.filter(pl.col("location") == basement_location).sort("Time")
    install_start = infer_dehumidifier_start(basement)
    install_end = basement.select(pl.col("Time").max()).item()

    pre_start = install_start - timedelta(days=7)
    pre = basement.filter((pl.col("Time") >= pre_start) & (pl.col("Time") < install_start))
    post = basement.filter(pl.col("Time") >= install_start)
    latest_start = install_end - timedelta(hours=36)

    post_cycles = detect_cycle_segments(post)
    first_metrics = period_metrics(post_cycles, install_start, install_start + timedelta(hours=36))
    latest_metrics = period_metrics(post_cycles, latest_start, install_end + timedelta(minutes=1))
    pre_metrics = mean_metrics(pre)
    post_metrics = mean_metrics(post)

    cycles_payload = [
        {
            "kind": s.kind,
            "start": s.start.strftime("%Y-%m-%d %H:%M"),
            "end": s.end.strftime("%Y-%m-%d %H:%M"),
            "minutes": s.minutes,
            "start_rh": s.start_rh,
            "end_rh": s.end_rh,
            "rh_rate_per_hour": s.rh_rate_per_hour,
            "ah_rate_per_hour": s.ah_rate_per_hour,
            "mean_temp": s.mean_temp,
        }
        for s in post_cycles
    ]

    payload = {
        "basementLocation": basement_location,
        "installTime": install_start.strftime("%Y-%m-%d %H:%M"),
        "pre": pre_metrics,
        "post": post_metrics,
        "first": first_metrics,
        "latest": latest_metrics,
        "improvement": {
            "mean_rh_delta_pp": (
                None
                if pre_metrics["mean_rh"] is None or post_metrics["mean_rh"] is None
                else post_metrics["mean_rh"] - pre_metrics["mean_rh"]
            ),
            "mean_ah_delta_g_m3": (
                None
                if pre_metrics["mean_ah"] is None or post_metrics["mean_ah"] is None
                else post_metrics["mean_ah"] - pre_metrics["mean_ah"]
            ),
            "rebound_ah_delta_g_m3_per_hour": (
                None
                if first_metrics["median_rebound_ah_g_m3_per_hour"] is None
                or latest_metrics["median_rebound_ah_g_m3_per_hour"] is None
                else latest_metrics["median_rebound_ah_g_m3_per_hour"]
                - first_metrics["median_rebound_ah_g_m3_per_hour"]
            ),
        },
        "daily": daily_summary(basement),
        "basementPoints": points_for_plot(post, every="5m"),
        "allPoints": (
            all_data.group_by_dynamic("Time", every="1h", group_by="location")
            .agg(pl.col("relative_humidity_pct").mean().round(2).alias("rh"))
            .sort(["location", "Time"])
            .with_columns(pl.col("Time").dt.strftime("%Y-%m-%d %H:%M").alias("time"))
            .select(["location", "time", "rh"])
            .to_dicts()
        ),
        "cycles": cycles_payload,
    }

    OUT.write_text(render_html(payload), encoding="utf-8")
    print(f"Wrote {OUT}")
    print(f"Basement source: {basement_location}")
    print(f"Inferred dehumidifier install time: {payload['installTime']}")
    print(f"Pre-install mean RH: {metric_card(pre_metrics['mean_rh'], '%')}")
    print(f"Post-install mean RH: {metric_card(post_metrics['mean_rh'], '%')}")
    print(f"Post-install cycles detected: {len(post_cycles)}")
    print(
        "Latest median rebound rate: "
        f"{metric_card(latest_metrics['median_rebound_ah_g_m3_per_hour'], ' g/m3/hr')}"
    )


if __name__ == "__main__":
    main()
