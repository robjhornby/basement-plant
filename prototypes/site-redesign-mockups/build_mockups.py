# pyright: basic
"""PROTOTYPE — throwaway. Generate the themed redesign mockup HTML pages.

Reads payloads.json (build_payloads.py output) plus the vendored uPlot assets and
writes instrument-panel.html and frutiger-aero.html next to this script (the
spring/wet-moss candidate was dropped after the 2026-07-09 reaction round).
Run from the repo root:

    uv run python prototypes/site-redesign-mockups/build_mockups.py
"""

from __future__ import annotations

import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO_ROOT = HERE.parents[1]
VENDOR = REPO_ROOT / "src" / "basement_analysis" / "vendor" / "uplot"

PAGE_TEMPLATE = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>%%TITLE%%</title>
<style>
%%UPLOT_CSS%%
</style>
<style>
/* ---------- shared skeleton ---------- */
* { box-sizing: border-box; }
html, body { margin: 0; padding: 0; }
body {
  min-height: 100vh;
  background: var(--bg);
  color: var(--ink);
  font-family: var(--body-font);
}
.page { position: relative; z-index: 2; max-width: 1060px; margin: 0 auto; padding: 28px 20px 96px; }
header.site-header { margin: 18px 0 26px; }
h1.site-title { margin: 0; }
.readouts { display: flex; flex-wrap: wrap; gap: 18px; margin-bottom: 22px; }
.readout { flex: 1 1 220px; }
.readout-value { line-height: 1; }
.chart-card { margin-bottom: 26px; }
.chart-head { display: flex; align-items: center; justify-content: space-between; gap: 12px; margin-bottom: 6px; }
.chart-head h2 { margin: 0; }
.chart-actions { display: flex; gap: 8px; }
.chart-actions button { cursor: pointer; }
.chart-host { width: 100%; }
footer.site-footer { margin-top: 34px; }
footer.site-footer p { margin: 4px 0; }
.u-legend { color: var(--ink); }
.u-legend .u-value { font-variant-numeric: tabular-nums; }

/* ---------- prototype switcher (not part of the design) ---------- */
.proto-switcher {
  position: fixed; left: 50%; bottom: 14px; transform: translateX(-50%);
  z-index: 999; display: flex; align-items: center; gap: 12px;
  background: #16161a; color: #fff; border: 1px solid #3a3a42;
  border-radius: 999px; padding: 8px 16px; box-shadow: 0 4px 18px rgba(0,0,0,.45);
  font: 13px/1 -apple-system, "Segoe UI", sans-serif; white-space: nowrap;
}
.proto-switcher a { color: #9ecbff; text-decoration: none; font-size: 16px; padding: 2px 6px; }
.proto-switcher a:hover { color: #fff; }
</style>
<style>
/* ---------- theme ---------- */
%%THEME_CSS%%
</style>
</head>
<body class="%%THEME_CLASS%%">
%%BODY_ART%%
<div class="page">
  <header class="site-header"><h1 class="site-title">%%TITLE_MARKUP%%</h1></header>

  <section class="readouts" aria-label="Current basement conditions">
    <div class="readout">
      <div class="readout-value">%%READOUT_RH%%<span class="readout-unit">%</span></div>
      <div class="readout-label">Basement relative humidity</div>
    </div>
    <div class="readout">
      <div class="readout-value">%%READOUT_TEMP%%<span class="readout-unit">°C</span></div>
      <div class="readout-label">Basement temperature</div>
    </div>
  </section>

  <div id="chart-sections"></div>

  <footer class="site-footer">
    <p class="freshness">Data to %%LATEST_TIME%%</p>
    <p class="sources">Indoor readings come from thermometer–hygrometer sensors in the basement,
    bedroom, and living room. Outdoor humidity comes from the Open-Meteo weather archive.
    Rainfall comes from a nearby Environment Agency rain gauge.</p>
  </footer>
</div>

<nav class="proto-switcher" aria-label="Mockup switcher">
  <a href="%%PREV_FILE%%" aria-label="Previous mockup">&#8592;</a>
  <span>%%SWITCH_LABEL%%</span>
  <a href="%%NEXT_FILE%%" aria-label="Next mockup">&#8594;</a>
</nav>

<script>
%%UPLOT_JS%%
</script>
<script id="chart-payloads" type="application/json">%%PAYLOADS_JSON%%</script>
<script>
window.MOCKUP_THEME = %%THEME_JSON%%;
</script>
<script>
%%RUNTIME_JS%%
</script>
<script>
(function () {
  document.addEventListener("keydown", function (event) {
    if (event.key === "ArrowLeft") { window.location.href = "%%PREV_FILE%%"; }
    if (event.key === "ArrowRight") { window.location.href = "%%NEXT_FILE%%"; }
  });
})();
</script>
</body>
</html>
"""

RUNTIME_JS = r"""
(function () {
  "use strict";

  var THEME = window.MOCKUP_THEME;
  var BUNDLE = JSON.parse(document.getElementById("chart-payloads").textContent);

  function formatTimestamp(epochSeconds) {
    if (epochSeconds == null) { return ""; }
    return new Date(epochSeconds * 1000).toLocaleString("en-GB", {
      day: "2-digit", month: "short", hour: "2-digit", minute: "2-digit"
    });
  }

  function formatValue(value, digits, unit) {
    if (value == null || !Number.isFinite(value)) { return "–"; }
    var text = value.toFixed(digits);
    if (!unit) { return text; }
    return unit === "%" ? text + "%" : text + " " + unit;
  }

  function hexToRgba(color, alpha) {
    var match = /^#?([a-f\d]{2})([a-f\d]{2})([a-f\d]{2})$/i.exec(color);
    if (match == null) { return color; }
    return "rgba(" + [
      parseInt(match[1], 16), parseInt(match[2], 16), parseInt(match[3], 16), alpha
    ].join(",") + ")";
  }

  function normalizeGaps(payload) {
    payload.series.forEach(function (series, index) {
      payload.data[index + 1] = payload.data[index + 1].map(function (value) {
        return value === null ? undefined : value;
      });
    });
    (payload.bands || []).forEach(function (band) {
      band.lower = band.lower.map(function (v) { return v === null ? undefined : v; });
      band.upper = band.upper.map(function (v) { return v === null ? undefined : v; });
    });
  }

  function eventMarkerPlugin(events) {
    return { hooks: { draw: [function (plot) {
      if (!events.length) { return; }
      var ctx = plot.ctx;
      ctx.save();
      ctx.strokeStyle = THEME.event;
      ctx.lineWidth = 1;
      ctx.setLineDash([4, 4]);
      events.forEach(function (event) {
        var x = plot.valToPos(event.timestamp, "x", true);
        if (x >= plot.bbox.left && x <= plot.bbox.left + plot.bbox.width) {
          ctx.beginPath();
          ctx.moveTo(Math.round(x) + 0.5, plot.bbox.top);
          ctx.lineTo(Math.round(x) + 0.5, plot.bbox.top + plot.bbox.height);
          ctx.stroke();
        }
      });
      ctx.restore();
    }] } };
  }

  function bandPlugin(bands, timestamps) {
    return { hooks: { draw: [function (plot) {
      if (!bands.length) { return; }
      var ctx = plot.ctx;
      var left = plot.bbox.left;
      var right = plot.bbox.left + plot.bbox.width;
      ctx.save();
      ctx.beginPath();
      ctx.rect(plot.bbox.left, plot.bbox.top, plot.bbox.width, plot.bbox.height);
      ctx.clip();
      ctx.globalCompositeOperation = "destination-over";
      bands.forEach(function (band) {
        var lowerSegment = [];
        var drawing = false;
        ctx.fillStyle = hexToRgba(THEME.roles[band.role], THEME.bandAlpha);

        function finishSegment() {
          if (!drawing || lowerSegment.length < 2) { lowerSegment = []; drawing = false; return; }
          for (var i = lowerSegment.length - 1; i >= 0; i -= 1) {
            ctx.lineTo(lowerSegment[i][0], lowerSegment[i][1]);
          }
          ctx.closePath();
          ctx.fill();
          lowerSegment = [];
          drawing = false;
        }

        timestamps.forEach(function (ts, index) {
          var lower = band.lower[index];
          var upper = band.upper[index];
          if (lower === undefined || upper === undefined) { return; }
          if (!Number.isFinite(lower) || !Number.isFinite(upper)) { finishSegment(); return; }
          var x = plot.valToPos(ts, "x", true);
          if (x < left - 4 || x > right + 4) { finishSegment(); return; }
          var upperY = plot.valToPos(upper, band.scale, true);
          var lowerY = plot.valToPos(lower, band.scale, true);
          if (!drawing) { ctx.beginPath(); ctx.moveTo(x, upperY); drawing = true; }
          else { ctx.lineTo(x, upperY); }
          lowerSegment.push([x, lowerY]);
        });
        finishSegment();
      });
      ctx.restore();
    }] } };
  }

  function rainBarPlugin(payload) {
    var barIndex = -1;
    payload.series.forEach(function (series, index) {
      if (series.kind === "bar") { barIndex = index; }
    });
    if (barIndex === -1) { return { hooks: {} }; }
    var series = payload.series[barIndex];
    var color = THEME.roles[series.role];
    return { hooks: { draw: [function (plot) {
      var ctx = plot.ctx;
      var values = payload.data[barIndex + 1];
      var timestamps = payload.data[0];
      var zeroY = plot.valToPos(0, series.scale, true);
      ctx.save();
      ctx.beginPath();
      ctx.rect(plot.bbox.left, plot.bbox.top, plot.bbox.width, plot.bbox.height);
      ctx.clip();
      ctx.globalCompositeOperation = "destination-over";
      ctx.fillStyle = hexToRgba(color, 0.9);
      var minX = plot.bbox.left - 40;
      var maxX = plot.bbox.left + plot.bbox.width + 40;
      timestamps.forEach(function (ts, index) {
        var value = values[index];
        if (value == null || !Number.isFinite(value) || value <= 0) { return; }
        var xLeft = plot.valToPos(ts - 1700, "x", true);
        var xRight = plot.valToPos(ts + 1700, "x", true);
        if (xRight < minX || xLeft > maxX) { return; }
        var y = plot.valToPos(value, series.scale, true);
        var width = Math.max(1, xRight - xLeft - 1);
        ctx.fillRect(xLeft, y, width, Math.max(1, zeroY - y));
      });
      ctx.restore();
    }] } };
  }

  function scaleBounds(payload) {
    var byScale = {};
    payload.series.forEach(function (series, index) {
      byScale[series.scale] = (byScale[series.scale] || []).concat(payload.data[index + 1]);
    });
    (payload.bands || []).forEach(function (band) {
      byScale[band.scale] = (byScale[band.scale] || []).concat(band.lower, band.upper);
    });
    var bounds = {};
    Object.keys(byScale).forEach(function (scaleKey) {
      var finite = byScale[scaleKey].filter(function (v) {
        return v != null && Number.isFinite(v);
      });
      if (!finite.length) { bounds[scaleKey] = [0, 1]; return; }
      var minimum = Math.min.apply(null, finite);
      var maximum = Math.max.apply(null, finite);
      if (scaleKey === "rain") { bounds[scaleKey] = [0, Math.max(1, maximum * 1.15)]; return; }
      if (minimum === maximum) { bounds[scaleKey] = [minimum - 1, maximum + 1]; return; }
      var pad = (maximum - minimum) * 0.08;
      bounds[scaleKey] = [minimum - pad, maximum + pad];
    });
    return bounds;
  }

  function dataBounds(payload) {
    var timestamps = payload.data[0];
    var minimum = timestamps[0];
    var maximum = timestamps[timestamps.length - 1];
    return {
      minimum: minimum,
      maximum: maximum,
      latestMinimum: Math.max(minimum, maximum - payload.initialWindowSeconds)
    };
  }

  function clampRange(minimum, maximum, bounds) {
    var span = maximum - minimum;
    var fullSpan = bounds.maximum - bounds.minimum;
    if (span >= fullSpan) { return [bounds.minimum, bounds.maximum]; }
    if (minimum < bounds.minimum) { maximum += bounds.minimum - minimum; minimum = bounds.minimum; }
    if (maximum > bounds.maximum) { minimum -= maximum - bounds.maximum; maximum = bounds.maximum; }
    return [Math.max(bounds.minimum, minimum), Math.min(bounds.maximum, maximum)];
  }

  function setRange(plot, minimum, maximum, bounds) {
    var clamped = clampRange(minimum, maximum, bounds);
    plot.setScale("x", { min: clamped[0], max: clamped[1] });
  }

  function addRangeControls(card, plot, bounds) {
    var actions = card.querySelector(".chart-actions");
    var weekButton = document.createElement("button");
    var allButton = document.createElement("button");
    weekButton.type = "button";
    weekButton.textContent = "Week";
    weekButton.setAttribute("aria-pressed", "true");
    allButton.type = "button";
    allButton.textContent = "All";
    allButton.setAttribute("aria-pressed", "false");
    weekButton.addEventListener("click", function () {
      setRange(plot, bounds.latestMinimum, bounds.maximum, bounds);
      weekButton.setAttribute("aria-pressed", "true");
      allButton.setAttribute("aria-pressed", "false");
    });
    allButton.addEventListener("click", function () {
      setRange(plot, bounds.minimum, bounds.maximum, bounds);
      weekButton.setAttribute("aria-pressed", "false");
      allButton.setAttribute("aria-pressed", "true");
    });
    actions.append(weekButton, allButton);
  }

  function addWheelNavigation(card, plot, bounds) {
    var overlay = card.querySelector(".u-over");
    if (overlay == null) { return; }
    overlay.addEventListener("wheel", function (event) {
      if (!event.shiftKey && !event.ctrlKey && !event.metaKey) { return; }
      event.preventDefault();
      var scale = plot.scales.x;
      var span = scale.max - scale.min;
      if (event.shiftKey) {
        var shift = event.deltaY * span * 0.0015;
        setRange(plot, scale.min + shift, scale.max + shift, bounds);
        return;
      }
      var rect = overlay.getBoundingClientRect();
      var ratio = Math.min(Math.max((event.clientX - rect.left) / rect.width, 0), 1);
      var anchor = scale.min + span * ratio;
      var factor = event.deltaY > 0 ? 1.2 : 0.82;
      setRange(plot, anchor - (anchor - scale.min) * factor, anchor + (scale.max - anchor) * factor, bounds);
    }, { passive: false });
  }

  function renderChart(payload) {
    var card = document.createElement("section");
    card.className = "chart-card";
    var head = document.createElement("div");
    head.className = "chart-head";
    var heading = document.createElement("h2");
    heading.textContent = payload.title;
    var actions = document.createElement("div");
    actions.className = "chart-actions";
    head.append(heading, actions);
    var host = document.createElement("div");
    host.className = "chart-host";
    card.append(head, host);
    document.getElementById("chart-sections").append(card);
    normalizeGaps(payload);
    var bounds = dataBounds(payload);
    var perScale = scaleBounds(payload);

    var scales = { x: { time: true, min: bounds.latestMinimum, max: bounds.maximum } };
    Object.keys(perScale).forEach(function (scaleKey) {
      (function (fixed) {
        scales[scaleKey] = { range: function () { return fixed; } };
      })(perScale[scaleKey]);
    });

    var axes = [{
      stroke: THEME.inkMuted,
      grid: { stroke: THEME.grid, width: 1 },
      ticks: { stroke: THEME.grid, width: 1 },
      font: THEME.axisFont
    }];
    payload.axes.forEach(function (axis, index) {
      axes.push({
        scale: axis.scale,
        side: axis.side === "right" ? 1 : 3,
        label: axis.label,
        labelFont: THEME.axisLabelFont,
        labelGap: 4,
        stroke: THEME.inkMuted,
        font: THEME.axisFont,
        grid: index === 0 ? { stroke: THEME.grid, width: 1 } : { show: false },
        ticks: { stroke: THEME.grid, width: 1 },
        size: 56
      });
    });

    var seriesOptions = [{
      label: "Time",
      value: function (_plot, value) { return formatTimestamp(value); }
    }].concat(payload.series.map(function (series) {
      var options = {
        label: series.name,
        scale: series.scale,
        stroke: THEME.roles[series.role],
        width: 2,
        points: { show: false },
        value: function (_plot, value) { return formatValue(value, series.digits, series.unit); }
      };
      if (series.kind === "bar") {
        options.paths = function () { return null; };
      }
      return options;
    }));

    var plot = new uPlot({
      width: Math.max(320, host.clientWidth || 720),
      height: payload.height,
      scales: scales,
      axes: axes,
      cursor: { drag: { x: true, y: false, setScale: true }, focus: { prox: 24 } },
      legend: { show: true, live: true },
      series: seriesOptions,
      plugins: [
        bandPlugin(payload.bands || [], payload.data[0]),
        rainBarPlugin(payload),
        eventMarkerPlugin(payload.events || [])
      ]
    }, payload.data, host);

    addRangeControls(card, plot, bounds);
    addWheelNavigation(card, plot, bounds);
    if ("ResizeObserver" in window) {
      new ResizeObserver(function () {
        plot.setSize({
          width: Math.max(320, Math.floor(host.clientWidth || 720)),
          height: payload.height
        });
      }).observe(host);
    }
  }

  BUNDLE.charts.forEach(renderChart);
})();
"""

INSTRUMENT_CSS = """
body.theme-instrument {
  --bg: #05080a;
  --ink: #c8e6cf;
  --ink-muted: #7fa98a;
  --body-font: "SF Mono", "Menlo", "Consolas", "Liberation Mono", monospace;
  background-image:
    linear-gradient(rgba(31, 163, 76, 0.05) 1px, transparent 1px),
    linear-gradient(90deg, rgba(31, 163, 76, 0.05) 1px, transparent 1px);
  background-size: 28px 28px;
}
.theme-instrument h1.site-title {
  font-size: 26px;
  letter-spacing: 0.24em;
  text-transform: uppercase;
  color: #35d06a;
  text-shadow: 0 0 12px rgba(53, 208, 106, 0.55);
  font-weight: 600;
}
.theme-instrument h1.site-title::after {
  content: "_";
  animation: blink 1.1s steps(1) infinite;
}
@keyframes blink { 50% { opacity: 0; } }
.theme-instrument .readout {
  background: linear-gradient(180deg, #0a120d 0%, #0a0f0b 100%);
  border: 1px solid #1e3326;
  border-radius: 6px;
  padding: 16px 20px 14px;
  box-shadow: inset 0 0 18px rgba(0, 0, 0, 0.7), 0 1px 0 rgba(53, 208, 106, 0.08);
  position: relative;
  overflow: hidden;
}
.theme-instrument .readout::after {
  content: "";
  position: absolute; inset: 0;
  background: repeating-linear-gradient(180deg, rgba(255,255,255,0.025) 0 1px, transparent 1px 3px);
  pointer-events: none;
}
.theme-instrument .readout-value {
  font-size: 58px;
  font-weight: 700;
  color: #35d06a;
  text-shadow: 0 0 16px rgba(53, 208, 106, 0.5);
  font-variant-numeric: tabular-nums;
}
.theme-instrument .readout:nth-child(2) .readout-value {
  color: #e3a41c;
  text-shadow: 0 0 16px rgba(227, 164, 28, 0.45);
}
.theme-instrument .readout-unit { font-size: 26px; margin-left: 6px; opacity: 0.85; }
.theme-instrument .readout-label {
  margin-top: 8px; font-size: 11px; letter-spacing: 0.18em; text-transform: uppercase;
  color: var(--ink-muted);
}
.theme-instrument .chart-card {
  background: #0a0f0b;
  border: 1px solid #1e3326;
  border-radius: 6px;
  padding: 14px 16px 8px;
  box-shadow: inset 0 0 24px rgba(0, 0, 0, 0.6);
}
.theme-instrument .chart-head h2 {
  font-size: 12px; letter-spacing: 0.2em; text-transform: uppercase;
  color: #7fd695; font-weight: 600;
}
.theme-instrument .chart-actions button {
  background: #0c1710; color: #7fd695; border: 1px solid #2c4a36;
  font: 11px/1.6 var(--body-font); letter-spacing: 0.12em; text-transform: uppercase;
  padding: 3px 12px; border-radius: 3px;
}
.theme-instrument .chart-actions button[aria-pressed="true"] {
  background: #35d06a; color: #05080a; border-color: #35d06a;
  box-shadow: 0 0 10px rgba(53, 208, 106, 0.5);
}
.theme-instrument .chart-host canvas {
  filter: drop-shadow(0 0 3px rgba(53, 208, 106, 0.28));
}
.theme-instrument .u-legend { font: 11px var(--body-font); }
.theme-instrument footer.site-footer {
  font-size: 12px; color: var(--ink-muted); border-top: 1px solid #1e3326; padding-top: 14px;
}
"""

AERO_CSS = """
body.theme-aero {
  --bg: linear-gradient(180deg, #8fd0f4 0%, #c9ecfb 38%, #eaf9ff 70%, #d8f2e2 100%);
  --ink: #123a55;
  --ink-muted: #4a7391;
  --body-font: "Segoe UI", "Helvetica Neue", -apple-system, "Frutiger", sans-serif;
  background: var(--bg);
  background-attachment: fixed;
}
.theme-aero .page { z-index: 2; }
.theme-aero h1.site-title {
  font-size: 40px;
  font-weight: 400;
  letter-spacing: 0.01em;
  background: linear-gradient(180deg, #063d6b 15%, #0b6bb0 60%, #2596d2 100%);
  -webkit-background-clip: text;
  background-clip: text;
  color: transparent;
  filter: drop-shadow(0 1px 0 rgba(255, 255, 255, 0.85)) drop-shadow(0 2px 10px rgba(255, 255, 255, 0.6));
}
.theme-aero .readout, .theme-aero .chart-card {
  position: relative;
  background: linear-gradient(180deg, rgba(255,255,255,0.72) 0%, rgba(255,255,255,0.5) 100%);
  border: 1px solid rgba(255, 255, 255, 0.85);
  border-radius: 20px;
  box-shadow: 0 8px 28px rgba(23, 94, 140, 0.18), inset 0 1px 0 rgba(255,255,255,0.9);
  backdrop-filter: blur(12px);
  -webkit-backdrop-filter: blur(12px);
  overflow: hidden;
}
.theme-aero .readout::before, .theme-aero .chart-card::before {
  content: "";
  position: absolute; left: 14px; right: 14px; top: 0; height: 54px;
  background: linear-gradient(180deg, rgba(255,255,255,0.65), rgba(255,255,255,0.06));
  border-radius: 16px 16px 28px 28px;
  pointer-events: none;
}
.theme-aero .readout { padding: 18px 22px; }
.theme-aero .readout-value {
  font-size: 58px; font-weight: 250; color: #0b5f9e;
  text-shadow: 0 1px 0 rgba(255,255,255,0.8); font-variant-numeric: tabular-nums;
}
.theme-aero .readout:nth-child(2) .readout-value { color: #c25a08; }
.theme-aero .readout-unit { font-size: 26px; margin-left: 5px; color: var(--ink-muted); }
.theme-aero .readout-label { margin-top: 6px; font-size: 14px; color: var(--ink-muted); }
.theme-aero .chart-card { padding: 16px 18px 10px; }
.theme-aero .chart-head h2 { font-size: 17px; font-weight: 500; color: #0b5f9e; }
.theme-aero .chart-head, .theme-aero .chart-host, .theme-aero .u-legend { position: relative; z-index: 1; }
.theme-aero .chart-actions button {
  background: linear-gradient(180deg, #eafaff 0%, #bfe9fb 45%, #9adcf7 55%, #d6f4ff 100%);
  color: #0b5f9e; border: 1px solid rgba(122, 190, 222, 0.9);
  font: 13px/1.5 var(--body-font); padding: 4px 16px; border-radius: 999px;
  box-shadow: 0 2px 6px rgba(23, 94, 140, 0.25), inset 0 1px 0 rgba(255,255,255,0.9);
}
.theme-aero .chart-actions button[aria-pressed="true"] {
  background: linear-gradient(180deg, #35b7e8 0%, #0f7fce 55%, #35b7e8 100%);
  color: #ffffff; border-color: #0f7fce;
}
.theme-aero .u-legend { font: 12px var(--body-font); color: var(--ink); }
.theme-aero footer.site-footer {
  font-size: 13.5px; color: #29597a;
  background: linear-gradient(180deg, rgba(255,255,255,0.5), rgba(255,255,255,0.3));
  border: 1px solid rgba(255,255,255,0.8); border-radius: 16px; padding: 12px 18px;
  backdrop-filter: blur(10px); -webkit-backdrop-filter: blur(10px);
}
.aero-sun {
  position: fixed; top: -140px; left: -120px; width: 460px; height: 460px; z-index: 1;
  background: radial-gradient(circle, rgba(255,255,240,0.9) 0%, rgba(255,255,240,0.35) 38%, transparent 70%);
  pointer-events: none;
}
.aero-bubble {
  position: fixed; border-radius: 50%; z-index: 1; pointer-events: none;
  background: radial-gradient(circle at 32% 28%, rgba(255,255,255,0.9) 0%, rgba(255,255,255,0.28) 22%, rgba(190,235,255,0.14) 60%, rgba(160,220,250,0.28) 100%);
  border: 1px solid rgba(255, 255, 255, 0.55);
  box-shadow: inset -6px -8px 18px rgba(120, 200, 240, 0.28);
}
.aero-hill {
  position: fixed; left: 0; right: 0; bottom: 0; height: 150px; width: 100%;
  z-index: 1; pointer-events: none;
}
"""

AERO_ART = """
<div class="aero-sun" aria-hidden="true"></div>
<div class="aero-bubble" style="width:130px;height:130px;right:6%;top:12%" aria-hidden="true"></div>
<div class="aero-bubble" style="width:70px;height:70px;right:14%;top:30%" aria-hidden="true"></div>
<div class="aero-bubble" style="width:44px;height:44px;right:4%;top:42%" aria-hidden="true"></div>
<div class="aero-bubble" style="width:90px;height:90px;left:3%;top:58%" aria-hidden="true"></div>
<div class="aero-bubble" style="width:52px;height:52px;left:10%;top:76%" aria-hidden="true"></div>
<svg class="aero-hill" aria-hidden="true" viewBox="0 0 1200 150" preserveAspectRatio="none">
  <path d="M0,110 C240,30 480,140 720,84 C900,44 1060,120 1200,74 L1200,150 L0,150 Z" fill="#8fce7e" opacity="0.5"/>
  <path d="M0,128 C300,74 560,148 840,106 C1020,80 1120,128 1200,108 L1200,150 L0,150 Z" fill="#5fb457" opacity="0.55"/>
</svg>
"""

THEMES = [
    {
        "file": "instrument-panel.html",
        "name": "Instrument panel",
        "css_class": "theme-instrument",
        "css": INSTRUMENT_CSS,
        "art": "",
        "title_markup": "Watch a basement dry",
        "config": {
            "roles": {
                "basementRh": "#1fa34c",
                "basementTemp": "#b8830a",
                "basementAh": "#0ea5bf",
                "outdoorAh": "#e05fa8",
                "rain": "#4f8ef7",
                "bedroomRh": "#9d7bf0",
                "livingRoomRh": "#e0653a",
            },
            "ink": "#c8e6cf",
            "inkMuted": "#7fa98a",
            "grid": "rgba(53, 208, 106, 0.10)",
            "event": "rgba(227, 164, 28, 0.55)",
            "bandAlpha": 0.16,
            "axisFont": "11px 'SF Mono', Menlo, Consolas, monospace",
            "axisLabelFont": "11px 'SF Mono', Menlo, Consolas, monospace",
        },
    },
    {
        "file": "frutiger-aero.html",
        "name": "Frutiger Aero",
        "css_class": "theme-aero",
        "css": AERO_CSS,
        "art": AERO_ART,
        "title_markup": "Watch a basement dry",
        "config": {
            "roles": {
                "basementRh": "#0b76c2",
                "basementTemp": "#d96608",
                "basementAh": "#0e9c60",
                "outdoorAh": "#8a63e8",
                "rain": "#1e46c9",
                "bedroomRh": "#c93f8f",
                "livingRoomRh": "#b07a00",
            },
            "ink": "#123a55",
            "inkMuted": "#4a7391",
            "grid": "rgba(15, 127, 206, 0.14)",
            "event": "rgba(194, 90, 8, 0.5)",
            "bandAlpha": 0.14,
            "axisFont": "12px 'Segoe UI', 'Helvetica Neue', sans-serif",
            "axisLabelFont": "12px 'Segoe UI', 'Helvetica Neue', sans-serif",
        },
    },
]


def main() -> None:
    payloads_text = (HERE / "payloads.json").read_text(encoding="utf-8")
    payloads = json.loads(payloads_text)
    latest = payloads["latest"]
    uplot_css = (VENDOR / "uPlot.min.css").read_text(encoding="utf-8")
    uplot_js = (VENDOR / "uPlot.iife.min.js").read_text(encoding="utf-8")

    for index, theme in enumerate(THEMES):
        previous = THEMES[(index - 1) % len(THEMES)]["file"]
        following = THEMES[(index + 1) % len(THEMES)]["file"]
        page = (
            PAGE_TEMPLATE
            .replace("%%TITLE%%", f"Watch a basement dry — mockup {index + 1}: {theme['name']}")
            .replace("%%TITLE_MARKUP%%", theme["title_markup"])
            .replace("%%THEME_CLASS%%", theme["css_class"])
            .replace("%%THEME_CSS%%", theme["css"])
            .replace("%%BODY_ART%%", theme["art"])
            .replace("%%READOUT_RH%%", f"{latest['relative_humidity_pct']:.1f}")
            .replace("%%READOUT_TEMP%%", f"{latest['temperature_c']:.1f}")
            .replace("%%LATEST_TIME%%", latest["timestamp"])
            .replace("%%PREV_FILE%%", previous)
            .replace("%%NEXT_FILE%%", following)
            .replace("%%SWITCH_LABEL%%", f"{index + 1} / {len(THEMES)} · {theme['name']}")
            .replace("%%UPLOT_CSS%%", uplot_css)
            .replace("%%UPLOT_JS%%", uplot_js)
            .replace("%%PAYLOADS_JSON%%", payloads_text)
            .replace("%%THEME_JSON%%", json.dumps(theme["config"]))
            .replace("%%RUNTIME_JS%%", RUNTIME_JS)
        )
        output = HERE / theme["file"]
        output.write_text(page, encoding="utf-8")
        print(f"wrote {output} ({output.stat().st_size / 1e6:.2f} MB)")


if __name__ == "__main__":
    main()
