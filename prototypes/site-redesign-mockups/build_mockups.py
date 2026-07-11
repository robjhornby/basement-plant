# pyright: basic
"""PROTOTYPE — throwaway. Generate the themed redesign mockup HTML pages.

Reads payloads.json (build_payloads.py output), the vendored uPlot assets, and the
derived WebP art in assets/derived/ (process_assets.py output), then writes
instrument-panel.html and frutiger-aero.html next to this script.

The aero page is the round-2 "extreme Frutiger Aero" build: the background scrolls
with the page and descends sky -> ground -> waterline -> underwater (see
EXTREME-AERO-PLAN.md). Run from the repo root:

    uv run python prototypes/site-redesign-mockups/build_mockups.py
"""

from __future__ import annotations

import base64
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO_ROOT = HERE.parents[1]
VENDOR = REPO_ROOT / "src" / "basement_analysis" / "vendor" / "uplot"
DERIVED = HERE / "assets" / "derived"

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
.zone { position: relative; }
.zone-art { position: absolute; top: 0; bottom: 0; left: 50%; width: 100vw;
  transform: translateX(-50%); z-index: -1; overflow: hidden; pointer-events: none; }
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
  <div class="zone zone-sky">
    %%SKY_ART%%
    <header class="site-header"><h1 class="site-title">%%TITLE_MARKUP%%</h1></header>

    <section class="readouts" aria-label="Current basement conditions">
      <div class="readout readout-humidity" style="--fill: %%READOUT_RH%%%">
        <div class="readout-value">%%READOUT_RH%%<span class="readout-unit">%</span></div>
        <div class="readout-label">Basement relative humidity</div>
      </div>
      <div class="readout readout-temperature">
        <div class="readout-value">%%READOUT_TEMP%%<span class="readout-unit">°C</span></div>
        <div class="readout-label">Basement temperature</div>
      </div>
    </section>
%%SCROLL_HINT%%
    <div class="chart-slot" data-slot="sky"></div>
  </div>

  <div class="zone zone-ground">
    %%GROUND_ART%%
    <div class="chart-slot" data-slot="ground"></div>
  </div>

  %%WATERLINE_ART%%

  <div class="zone zone-under">
    %%UNDER_ART%%
    <div class="chart-slot" data-slot="under"></div>

    <footer class="site-footer">
      <p class="freshness">Data to %%LATEST_TIME%%</p>
      <p class="sources">Indoor readings come from thermometer–hygrometer sensors in the basement,
      bedroom, and living room. Outdoor humidity comes from the Open-Meteo weather archive.
      Rainfall comes from a nearby Environment Agency rain gauge.</p>
    </footer>
  </div>
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
  var CHART_SLOTS = THEME.chartSlots || ["sky", "ground"];

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

  function drawEventBubbles(plot, x) {
    var ctx = plot.ctx;
    var bottom = plot.bbox.top + plot.bbox.height;
    var step = 26;
    var count = 0;
    for (var y = bottom - 9; y > plot.bbox.top + 8; y -= step) {
      var radius = count % 2 === 0 ? 2.4 : 3.4;
      var offset = count % 2 === 0 ? -2.5 : 2.5;
      ctx.beginPath();
      ctx.arc(x + offset, y, radius, 0, Math.PI * 2);
      ctx.globalAlpha = 0.3;
      ctx.fill();
      ctx.globalAlpha = 1;
      ctx.stroke();
      count += 1;
    }
  }

  function eventMarkerPlugin(events) {
    return { hooks: { draw: [function (plot) {
      if (!events.length) { return; }
      var ctx = plot.ctx;
      ctx.save();
      ctx.beginPath();
      ctx.rect(plot.bbox.left, plot.bbox.top, plot.bbox.width, plot.bbox.height);
      ctx.clip();
      ctx.strokeStyle = THEME.event;
      ctx.fillStyle = THEME.event;
      ctx.lineWidth = 1;
      if (!THEME.eventBubbles) { ctx.setLineDash([4, 4]); }
      events.forEach(function (event) {
        var x = plot.valToPos(event.timestamp, "x", true);
        if (x < plot.bbox.left || x > plot.bbox.left + plot.bbox.width) { return; }
        if (THEME.eventBubbles) { drawEventBubbles(plot, Math.round(x) + 0.5); return; }
        ctx.beginPath();
        ctx.moveTo(Math.round(x) + 0.5, plot.bbox.top);
        ctx.lineTo(Math.round(x) + 0.5, plot.bbox.top + plot.bbox.height);
        ctx.stroke();
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
      var droplets = THEME.rainDroplets && typeof ctx.roundRect === "function";
      timestamps.forEach(function (ts, index) {
        var value = values[index];
        if (value == null || !Number.isFinite(value) || value <= 0) { return; }
        var xLeft = plot.valToPos(ts - 1700, "x", true);
        var xRight = plot.valToPos(ts + 1700, "x", true);
        if (xRight < minX || xLeft > maxX) { return; }
        var y = plot.valToPos(value, series.scale, true);
        var width = Math.max(1, xRight - xLeft - 1);
        var height = Math.max(1, zeroY - y);
        if (droplets && width >= 2 && height >= 2) {
          var radius = Math.min(width / 2, 3.5, height);
          ctx.beginPath();
          ctx.roundRect(xLeft, y, width, height, [radius, radius, 0, 0]);
          ctx.fill();
          return;
        }
        ctx.fillRect(xLeft, y, width, height);
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

  function waterFill(color) {
    return function (plot) {
      var top = plot.bbox.top;
      var height = plot.bbox.height;
      if (!Number.isFinite(top) || !Number.isFinite(height) || height <= 0) {
        return hexToRgba(color, 0.18);
      }
      var gradient = plot.ctx.createLinearGradient(0, top, 0, top + height);
      gradient.addColorStop(0, hexToRgba(color, 0.4));
      gradient.addColorStop(1, hexToRgba(color, 0.03));
      return gradient;
    };
  }

  function renderChart(payload, chartIndex) {
    var slotName = CHART_SLOTS[chartIndex] || "under";
    var slot = document.querySelector('.chart-slot[data-slot="' + slotName + '"]');
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
    slot.append(card);
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
      if (THEME.heroWater && chartIndex === 0 && series.role === "basementRh") {
        options.fill = waterFill(THEME.roles[series.role]);
        options.width = 2.5;
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

# The extreme aero skin, round 3 (ticket 16). One tall scene image (sky -> hills ->
# waterline -> underwater) is pinned so the waterline peeks just above the fold; the
# fold screen holds only the title, the orbs, and a scroll hint; all charts live
# underwater; a concrete floor band with a dehumidifier closes the page. Asset data
# URIs are injected as CSS custom properties by the build (see aero_asset_css).
#
# Scene geometry: the image is 1024x1536 displayed at 100vw, so its height is 150vw;
# the meniscus sits at ~63% of the image, i.e. 94.5vw from its top. Pinning the
# meniscus at --waterline-y gives --scene-top (negative on landscape screens: the
# image top crops off above the viewport, which also crops the sun; on portrait
# screens it is positive and .aero-sky-extend fills the gap with a matched gradient
# and a radial continuation of the sun glow).
AERO_CSS = """
body.theme-aero {
  --bg: #073a58;
  --ink: #123a55;
  --ink-muted: #4a7391;
  --body-font: "Segoe UI", "Helvetica Neue", -apple-system, "Frutiger", sans-serif;
  --waterline-y: 92vh;
  --scene-h: 150vw;
  --scene-waterline: 94.5vw;
  --scene-top: calc(var(--waterline-y) - var(--scene-waterline));
  --scene-bottom: calc(var(--waterline-y) + var(--scene-h) - var(--scene-waterline));
  background: var(--bg);
  overflow-x: hidden;
  position: relative;
}

/* ----- the descent backdrop (body-level, scrolls with the page) ----- */
.aero-scene-wrap {
  position: absolute; top: 0; left: 0; width: 100%; height: var(--scene-bottom);
  overflow: hidden; pointer-events: none;
}
.aero-sky-extend {
  position: absolute; inset: 0;
  background:
    radial-gradient(56vw 56vw at 15vw calc(var(--scene-top) + 21vw),
      rgba(190, 235, 255, 0.6), rgba(190, 235, 255, 0) 70%),
    linear-gradient(90deg, rgba(150, 215, 255, 0.35) 0%, rgba(150, 215, 255, 0) 40%,
      rgba(2, 45, 140, 0.25) 100%),
    linear-gradient(180deg, #0143a0 0%, #0062d7 var(--scene-top), #0062d7 100%);
}
.aero-scene {
  position: absolute; top: var(--scene-top); left: 0; width: 100%; height: var(--scene-h);
  background: var(--tall-scene-img) center / 100% 100% no-repeat;
  -webkit-mask-image: linear-gradient(180deg, transparent 0, #000 56px);
  mask-image: linear-gradient(180deg, transparent 0, #000 56px);
}
.aero-scene-fade {
  position: absolute; left: 0; width: 100%; height: 22vw;
  top: calc(var(--scene-bottom) - 22vw);
  background: linear-gradient(180deg, rgba(6, 65, 110, 0) 0%, #06416e 96%);
}
.aero-deep {
  position: absolute; inset: 0; pointer-events: none;
  background: linear-gradient(180deg,
    rgba(6, 65, 110, 0) 0, rgba(6, 65, 110, 0) var(--scene-bottom),
    #06416e var(--scene-bottom), #052c46 72%, #04202f 100%);
}

/* ----- title, gone to eleven ----- */
.theme-aero h1.site-title {
  font-size: clamp(38px, 5.4vw, 58px);
  font-weight: 650;
  letter-spacing: 0.005em;
  background: linear-gradient(180deg, #04365f 0%, #0a63a8 42%, #2ea3dc 72%, #8fdcf8 100%);
  -webkit-background-clip: text;
  background-clip: text;
  color: transparent;
  filter: drop-shadow(0 1px 0 rgba(255, 255, 255, 0.95))
          drop-shadow(0 2px 2px rgba(255, 255, 255, 0.55))
          drop-shadow(0 8px 22px rgba(8, 70, 125, 0.4));
}

/* ----- zone A: the fold screen (title + orbs + scroll hint only) ----- */
.theme-aero .zone-sky { margin-top: -28px; padding-top: 0; min-height: 100vh; }
.theme-aero header.site-header { margin: 9vh 0 0; text-align: center; }
.theme-aero .readouts { margin-top: 7vh; }
.aero-scroll-hint {
  position: absolute; left: 50%; top: 74vh; transform: translateX(-50%); z-index: 1;
}
.aero-scroll-hint span {
  display: block; width: 26px; height: 26px;
  border-right: 6px solid rgba(255, 255, 255, 0.95);
  border-bottom: 6px solid rgba(255, 255, 255, 0.95);
  border-radius: 3px;
  filter: drop-shadow(0 3px 10px rgba(8, 70, 125, 0.6));
  animation: hint-bob 1.8s ease-in-out infinite;
}
@keyframes hint-bob {
  0%, 100% { transform: rotate(45deg) translate(0, 0); opacity: 0.8; }
  50% { transform: rotate(45deg) translate(7px, 7px); opacity: 1; }
}
.aero-aurora {
  position: absolute; height: 240px; width: 150%; left: -25%;
  background: linear-gradient(100deg, transparent 8%, rgba(130, 255, 225, 0.28) 30%,
    rgba(150, 195, 255, 0.32) 52%, rgba(255, 190, 245, 0.24) 72%, transparent 92%);
  filter: blur(28px);
  mix-blend-mode: screen;
  animation: aurora-drift 16s ease-in-out infinite alternate;
}
.aero-aurora.aurora-2 { animation-duration: 23s; animation-delay: -8s; opacity: 0.7; }
@keyframes aurora-drift {
  from { transform: rotate(-7deg) translateX(-50px); }
  to { transform: rotate(-4deg) translateX(50px); }
}
.aero-bokeh {
  position: absolute; border-radius: 50%;
  background: radial-gradient(circle at 35% 30%, rgba(255,255,255,0.95) 0%,
    rgba(255,255,255,0.25) 55%, transparent 72%);
  filter: blur(1.5px); opacity: 0.55;
  animation: bokeh-drift ease-in-out infinite alternate;
}
@keyframes bokeh-drift {
  from { transform: translate(0, 0); }
  to { transform: translate(26px, -34px); }
}
.aero-fish-sky {
  position: absolute; width: clamp(110px, 14vw, 185px); aspect-ratio: 640 / 480;
  background: var(--goldfish-img) center / contain no-repeat;
  filter: drop-shadow(0 10px 16px rgba(10, 70, 120, 0.35));
  animation: fish-swim 11s ease-in-out infinite alternate;
}
@keyframes fish-swim {
  from { transform: translate(0, 0) rotate(-5deg); }
  to { transform: translate(-70px, 26px) rotate(3deg); }
}

/* ----- readout orbs ----- */
.theme-aero .readouts { gap: 36px; justify-content: center; margin-bottom: 30px; }
.theme-aero .readout {
  flex: 0 0 236px; width: 236px; height: 236px; border-radius: 50%;
  display: flex; flex-direction: column; align-items: center; justify-content: center;
  text-align: center; position: relative; overflow: hidden; padding: 0 26px;
  border: 1px solid rgba(255, 255, 255, 0.95);
  backdrop-filter: blur(10px); -webkit-backdrop-filter: blur(10px);
  box-shadow: 0 14px 34px rgba(12, 80, 130, 0.35), 0 0 26px rgba(140, 220, 255, 0.4),
    inset 0 2px 2px rgba(255, 255, 255, 0.95), inset 0 -14px 26px rgba(90, 180, 230, 0.35),
    0 40px 30px -22px rgba(25, 140, 205, 0.45);
}
.theme-aero .readout-humidity {
  background: radial-gradient(circle at 32% 26%, rgba(255,255,255,0.9) 0%,
    rgba(225,246,255,0.55) 32%, rgba(170,220,248,0.4) 62%, rgba(125,195,238,0.55) 100%);
}
.theme-aero .readout-humidity::before {
  content: "";
  position: absolute; left: 0; right: 0; bottom: 0; height: var(--fill, 50%);
  background: linear-gradient(180deg, rgba(110, 210, 252, 0.6) 0%, rgba(25, 132, 202, 0.72) 100%);
  border-radius: 46% 54% 0 0 / 16px 20px 0 0;
  box-shadow: inset 0 3px 3px -1px rgba(255, 255, 255, 0.95);
  animation: water-slosh 7s ease-in-out infinite alternate;
}
@keyframes water-slosh {
  from { border-radius: 46% 54% 0 0 / 18px 12px 0 0; }
  to { border-radius: 54% 46% 0 0 / 12px 18px 0 0; }
}
.theme-aero .readout-temperature {
  background: radial-gradient(circle at 32% 26%, rgba(255,255,255,0.92) 0%,
    rgba(255,238,205,0.6) 34%, rgba(252,195,115,0.5) 66%, rgba(240,150,55,0.6) 100%);
  box-shadow: 0 14px 34px rgba(140, 85, 15, 0.3), 0 0 26px rgba(255, 205, 130, 0.45),
    inset 0 2px 2px rgba(255, 255, 255, 0.95), inset 0 -14px 26px rgba(235, 155, 60, 0.4),
    0 40px 30px -22px rgba(220, 140, 45, 0.4);
}
.theme-aero .readout::after {
  content: "";
  position: absolute; left: 19%; right: 19%; top: 7%; height: 30%;
  border-radius: 50%;
  background: linear-gradient(180deg, rgba(255,255,255,0.95) 0%, rgba(255,255,255,0.05) 100%);
  pointer-events: none;
}
.theme-aero .readout-value {
  position: relative; z-index: 1;
  font-size: 54px; font-weight: 300; color: #084a80;
  text-shadow: 0 1px 0 rgba(255,255,255,0.85); font-variant-numeric: tabular-nums;
}
.theme-aero .readout-temperature .readout-value { color: #a34a02; }
.theme-aero .readout-unit { font-size: 24px; margin-left: 4px; color: inherit; opacity: 0.75; }
.theme-aero .readout-label {
  position: relative; z-index: 1; margin-top: 8px; font-size: 13px; color: #275b7e;
}
.theme-aero .readout-temperature .readout-label { color: #7c4a14; }

/* ----- Vista-grade glass panels ----- */
.theme-aero .chart-card {
  position: relative;
  background: linear-gradient(180deg, rgba(255,255,255,0.8) 0%, rgba(255,255,255,0.56) 100%);
  border: 1px solid rgba(255, 255, 255, 0.95);
  border-radius: 22px;
  padding: 16px 18px 10px;
  box-shadow: 0 12px 36px rgba(10, 70, 120, 0.28), 0 0 0 1px rgba(150, 225, 255, 0.35),
    0 0 30px rgba(120, 210, 255, 0.35), inset 0 1px 0 rgba(255, 255, 255, 0.95),
    inset 0 -12px 20px rgba(150, 215, 245, 0.3);
  backdrop-filter: blur(16px) saturate(1.25);
  -webkit-backdrop-filter: blur(16px) saturate(1.25);
  overflow: hidden;
}
.theme-aero .chart-card::before {
  content: "";
  position: absolute; left: 14px; right: 14px; top: 0; height: 54px;
  background: linear-gradient(180deg, rgba(255,255,255,0.65), rgba(255,255,255,0.06));
  border-radius: 16px 16px 28px 28px;
  pointer-events: none;
}
.theme-aero .chart-card::after {
  content: "";
  position: absolute; top: -20px; bottom: -20px; left: 0; width: 46%;
  background: linear-gradient(105deg, transparent 20%, rgba(255,255,255,0.5) 50%, transparent 80%);
  transform: translateX(-130%) skewX(-18deg);
  pointer-events: none;
  animation: sheen-sweep 1.7s ease-out 0.5s 1 both;
}
.theme-aero .chart-card:hover::after { animation: sheen-sweep-again 1.1s ease-out 1 both; }
@keyframes sheen-sweep { to { transform: translateX(320%) skewX(-18deg); } }
@keyframes sheen-sweep-again {
  from { transform: translateX(-130%) skewX(-18deg); }
  to { transform: translateX(320%) skewX(-18deg); }
}
.theme-aero .chart-head h2 { font-size: 17px; font-weight: 600; color: #0b5f9e; }
.theme-aero .chart-head, .theme-aero .chart-host, .theme-aero .u-legend { position: relative; z-index: 1; }

/* ----- candy gel buttons ----- */
.theme-aero .chart-actions button {
  background: linear-gradient(180deg, #f4fdff 0%, #c9effd 42%, #8edcf8 58%, #cdf3ff 100%);
  color: #0b5f9e; border: 1px solid #79c3e3; font: 600 13px/1.5 var(--body-font);
  padding: 5px 18px; border-radius: 999px;
  box-shadow: 0 3px 8px rgba(20, 90, 140, 0.3), inset 0 1px 0 rgba(255,255,255,0.95),
    inset 0 -5px 8px rgba(70, 170, 220, 0.35), 0 10px 10px -6px rgba(120, 210, 255, 0.5);
}
.theme-aero .chart-actions button[aria-pressed="true"] {
  background: linear-gradient(180deg, #6fd0f2 0%, #0f7fce 52%, #0a6cb4 60%, #4db6e6 100%);
  color: #ffffff; border-color: #0a6cb4;
  box-shadow: 0 3px 10px rgba(10, 90, 150, 0.45), inset 0 1px 0 rgba(255,255,255,0.6),
    inset 0 -5px 10px rgba(6, 60, 105, 0.4), 0 10px 10px -6px rgba(60, 180, 240, 0.55);
}
.theme-aero .u-legend { font: 12px var(--body-font); color: var(--ink); }

/* ----- ground zone collapses: the scene image carries the hills ----- */
.theme-aero .zone-ground { padding: 0; }
.aero-dragonfly {
  position: absolute; top: 56vh; right: 6%; width: 148px; aspect-ratio: 512 / 342;
  background: var(--dragonfly-img) center / contain no-repeat;
  transform: rotate(-8deg); z-index: 2; pointer-events: none;
  filter: drop-shadow(0 8px 12px rgba(20, 70, 110, 0.35));
  animation: dragonfly-hover 3.2s ease-in-out infinite alternate;
}
@keyframes dragonfly-hover {
  from { transform: rotate(-8deg) translateY(0); }
  to { transform: rotate(-6deg) translateY(6px); }
}
@media (max-width: 760px) {
  .aero-dragonfly { display: none; }
  .theme-aero .readout { flex: 0 0 196px; width: 196px; height: 196px; }
  .theme-aero .readout-value { font-size: 44px; }
}

/* ----- zone C: underwater (all charts + footer) -----
   Charts start just below the fold (User, round-3 reactions), floating over the
   scene's own underwater sunbeams; the frost carries legibility. */
.theme-aero .zone-under {
  padding-top: 4vh;
  color: #e9f7ff;
}
.aero-underbubble {
  position: absolute; bottom: -70px; border-radius: 50%;
  background: radial-gradient(circle at 32% 28%, rgba(255,255,255,0.9) 0%,
    rgba(255,255,255,0.28) 24%, rgba(190,235,255,0.12) 60%, rgba(160,220,250,0.3) 100%);
  border: 1px solid rgba(255, 255, 255, 0.5);
  box-shadow: inset -5px -7px 14px rgba(120, 200, 240, 0.3);
  animation: bubble-rise linear infinite;
}
@keyframes bubble-rise {
  0% { transform: translate(0, 0); opacity: 0; }
  8% { opacity: 0.9; }
  100% { transform: translate(26px, -1600px); opacity: 0; }
}
.aero-fish-deep {
  position: absolute; top: calc(100vh + 34vw); left: 8%; width: 110px; aspect-ratio: 640 / 480;
  background: var(--goldfish-img) center / contain no-repeat;
  transform: scaleX(-1);
  filter: brightness(0.35) saturate(0.4) blur(1.5px); opacity: 0.5;
  animation: fish-deep-drift 70s ease-in-out infinite alternate;
}
@keyframes fish-deep-drift {
  from { transform: scaleX(-1) translate(0, 0); }
  to { transform: scaleX(-1) translate(-58vw, 40px); }
}

/* ----- the basement floor: concrete band + dehumidifier, emerging from the murk ----- */
.aero-deep-floor {
  position: absolute; left: 0; right: 0; bottom: 0; height: min(240px, 30vw);
  background: var(--floor-strip-img) bottom center / auto 100% repeat-x;
  -webkit-mask-image: linear-gradient(180deg, transparent 0%, #000 60%);
  mask-image: linear-gradient(180deg, transparent 0%, #000 60%);
}
.aero-deep-floor::after {
  content: "";
  position: absolute; inset: 0;
  background: linear-gradient(180deg, rgba(4, 30, 48, 0.72) 0%,
    rgba(6, 45, 70, 0.5) 45%, rgba(8, 55, 84, 0.4) 100%);
}
.aero-dehumidifier {
  position: absolute; right: 6%; bottom: min(88px, 11vw);
  width: clamp(130px, 15vw, 200px); aspect-ratio: 640 / 427;
  background: var(--dehumidifier-img) bottom / contain no-repeat;
  filter: brightness(0.88) saturate(0.92) drop-shadow(0 12px 16px rgba(2, 18, 30, 0.6));
}
.theme-aero .page { padding-bottom: 300px; }

/* underwater panels: stronger frost over the loudest background */
.theme-aero .zone-under .chart-card {
  background: linear-gradient(180deg, rgba(255,255,255,0.88) 0%, rgba(255,255,255,0.7) 100%);
  backdrop-filter: blur(20px) saturate(1.2);
  -webkit-backdrop-filter: blur(20px) saturate(1.2);
}
.theme-aero footer.site-footer {
  position: relative; z-index: 1;
  font-size: 13.5px; color: #e9f7ff;
  background: linear-gradient(180deg, rgba(10, 55, 84, 0.55), rgba(7, 40, 62, 0.75));
  border: 1px solid rgba(170, 230, 255, 0.4); border-radius: 16px; padding: 12px 18px;
  backdrop-filter: blur(12px); -webkit-backdrop-filter: blur(12px);
  box-shadow: 0 10px 28px rgba(3, 25, 40, 0.5), inset 0 1px 0 rgba(200, 240, 255, 0.35);
}
.theme-aero footer.site-footer .sources { color: #b9dcef; }

@media (prefers-reduced-motion: reduce) {
  .theme-aero *, .theme-aero *::before, .theme-aero *::after { animation: none !important; }
}
"""

AERO_BODY_ART = """
<div class="aero-scene-wrap" aria-hidden="true">
  <div class="aero-sky-extend"></div>
  <div class="aero-scene"></div>
  <div class="aero-scene-fade"></div>
</div>
<div class="aero-deep" aria-hidden="true">
  <div class="aero-underbubble" style="width:18px;height:18px;left:8%;animation-duration:13s;animation-delay:-3s"></div>
  <div class="aero-underbubble" style="width:34px;height:34px;left:23%;animation-duration:17s;animation-delay:-9s"></div>
  <div class="aero-underbubble" style="width:12px;height:12px;left:44%;animation-duration:11s;animation-delay:-6s"></div>
  <div class="aero-underbubble" style="width:26px;height:26px;left:62%;animation-duration:15s;animation-delay:-1s"></div>
  <div class="aero-underbubble" style="width:42px;height:42px;left:78%;animation-duration:19s;animation-delay:-12s"></div>
  <div class="aero-underbubble" style="width:16px;height:16px;left:91%;animation-duration:12s;animation-delay:-8s"></div>
  <div class="aero-fish-deep"></div>
  <div class="aero-deep-floor"></div>
  <div class="aero-dehumidifier"></div>
</div>
"""

AERO_SKY_ART = """
<div class="zone-art" aria-hidden="true">
  <div class="aero-aurora" style="top: 130px"></div>
  <div class="aero-aurora aurora-2" style="top: 420px"></div>
  <div class="aero-bokeh" style="width:84px;height:84px;left:6%;top:16%;animation-duration:9s"></div>
  <div class="aero-bokeh" style="width:38px;height:38px;left:16%;top:38%;animation-duration:13s"></div>
  <div class="aero-bokeh" style="width:56px;height:56px;right:9%;top:24%;animation-duration:11s"></div>
  <div class="aero-bokeh" style="width:26px;height:26px;right:20%;top:52%;animation-duration:8s"></div>
  <div class="aero-fish-sky" style="right:5%;top:330px"></div>
</div>
<div class="aero-dragonfly" aria-hidden="true"></div>
"""

AERO_SCROLL_HINT = """
    <div class="aero-scroll-hint" aria-hidden="true"><span></span></div>
"""

# Chart palettes are the validated ticket-11 round-1 palettes — do not change them
# (EXTREME-AERO-PLAN.md guardrail); only panel surfaces changed and were re-validated.
THEMES = [
    {
        "file": "instrument-panel.html",
        "name": "Instrument panel",
        "css_class": "theme-instrument",
        "css": INSTRUMENT_CSS,
        "body_art": "",
        "sky_art": "",
        "ground_art": "",
        "waterline_art": "",
        "under_art": "",
        "scroll_hint": "",
        "title_markup": "Watch a basement dry",
        "config": {
            "chartSlots": ["sky", "ground"],
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
        "name": "Frutiger Aero (extreme)",
        "css_class": "theme-aero",
        "css": AERO_CSS,
        "body_art": AERO_BODY_ART,
        "sky_art": AERO_SKY_ART,
        "ground_art": "",
        "waterline_art": "",
        "under_art": "",
        "scroll_hint": AERO_SCROLL_HINT,
        "title_markup": "Watch a basement dry",
        "config": {
            "chartSlots": [],
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
            "event": "rgba(15, 110, 175, 0.55)",
            "bandAlpha": 0.14,
            "axisFont": "12px 'Segoe UI', 'Helvetica Neue', sans-serif",
            "axisLabelFont": "12px 'Segoe UI', 'Helvetica Neue', sans-serif",
            "heroWater": True,
            "rainDroplets": True,
            "eventBubbles": True,
        },
    },
]

AERO_ASSETS = ["tall-scene", "floor-strip", "dehumidifier", "goldfish", "dragonfly"]


def aero_asset_css() -> str:
    lines = [".theme-aero {"]
    for stem in AERO_ASSETS:
        encoded = base64.b64encode((DERIVED / f"{stem}.webp").read_bytes()).decode("ascii")
        lines.append(f'  --{stem}-img: url("data:image/webp;base64,{encoded}");')
    lines.append("}")
    return "\n".join(lines)


def main() -> None:
    payloads_text = (HERE / "payloads.json").read_text(encoding="utf-8")
    payloads = json.loads(payloads_text)
    latest = payloads["latest"]
    uplot_css = (VENDOR / "uPlot.min.css").read_text(encoding="utf-8")
    uplot_js = (VENDOR / "uPlot.iife.min.js").read_text(encoding="utf-8")
    asset_css = aero_asset_css()

    for index, theme in enumerate(THEMES):
        previous = THEMES[(index - 1) % len(THEMES)]["file"]
        following = THEMES[(index + 1) % len(THEMES)]["file"]
        theme_css = theme["css"]
        if theme["css_class"] == "theme-aero":
            theme_css = asset_css + "\n" + theme_css
        page = (
            PAGE_TEMPLATE
            .replace("%%TITLE%%", f"Watch a basement dry — mockup {index + 1}: {theme['name']}")
            .replace("%%TITLE_MARKUP%%", theme["title_markup"])
            .replace("%%THEME_CLASS%%", theme["css_class"])
            .replace("%%THEME_CSS%%", theme_css)
            .replace("%%BODY_ART%%", theme["body_art"])
            .replace("%%SKY_ART%%", theme["sky_art"])
            .replace("%%GROUND_ART%%", theme["ground_art"])
            .replace("%%WATERLINE_ART%%", theme["waterline_art"])
            .replace("%%UNDER_ART%%", theme["under_art"])
            .replace("%%SCROLL_HINT%%", theme["scroll_hint"])
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
