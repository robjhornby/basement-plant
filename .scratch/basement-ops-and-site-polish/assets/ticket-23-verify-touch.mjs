import { createRequire } from "node:module";
const { chromium } = createRequire("/Users/rob/.nvm/versions/node/v24.4.1/lib/node_modules/@playwright/cli/index.js")("playwright-core");
import { pathToFileURL } from "node:url";
import path from "node:path";

const pageUrl = pathToFileURL(
  path.resolve("/Users/rob/projects/basement/build/basement-site/index.html")
).href;
const screenshotDir = "/Users/rob/projects/basement/output/playwright";

const failures = [];
function check(name, condition, detail) {
  const status = condition ? "PASS" : "FAIL";
  console.log(`${status}  ${name}${detail ? ` — ${detail}` : ""}`);
  if (!condition) failures.push(name);
}

function chartState(frameIndex) {
  const frame = document.querySelectorAll(".chart-frame")[frameIndex];
  const plot = frame.chartPlot;
  const legendValues = Array.from(
    frame.querySelectorAll(".u-legend .u-value")
  ).map((cell) => cell.textContent.trim());
  return {
    xMin: plot.scales.x.min,
    xMax: plot.scales.x.max,
    span: plot.scales.x.max - plot.scales.x.min,
    cursorIdx: plot.cursor.idx,
    legendValues,
  };
}

// Dispatch a synthetic touch event on a chart's .u-over element.
function dispatchTouch(frameIndex, type, points) {
  const frame = document.querySelectorAll(".chart-frame")[frameIndex];
  const overlay = frame.querySelector(".u-over");
  const rect = overlay.getBoundingClientRect();
  const touches = points.map(
    (point, identifier) =>
      new Touch({
        identifier,
        target: overlay,
        clientX: rect.left + rect.width * point.x,
        clientY: rect.top + rect.height * point.y,
      })
  );
  const event = new TouchEvent(type, {
    touches: type === "touchend" ? [] : touches,
    changedTouches: touches,
    targetTouches: type === "touchend" ? [] : touches,
    bubbles: true,
    cancelable: true,
  });
  overlay.dispatchEvent(event);
  return event.defaultPrevented;
}

async function loadPage(page) {
  const consoleErrors = [];
  page.on("console", (message) => {
    if (message.type() === "error" || message.type() === "warning") {
      consoleErrors.push(message.text());
    }
  });
  page.on("pageerror", (error) => consoleErrors.push(String(error)));
  await page.goto(pageUrl, { waitUntil: "load" });
  await page.waitForSelector(".chart-frame .uplot");
  await page.waitForTimeout(400);
  return consoleErrors;
}

const browser = await chromium.launch({
  executablePath:
    process.env.HOME +
    "/Library/Caches/ms-playwright/chromium_headless_shell-1223/" +
    "chrome-headless-shell-mac-arm64/chrome-headless-shell",
});

// ---------- Desktop: 1440x900, mouse ----------
{
  const context = await browser.newContext({ viewport: { width: 1440, height: 900 } });
  const page = await context.newPage();
  const consoleErrors = await loadPage(page);

  const chartCount = await page.evaluate(
    () => document.querySelectorAll(".chart-frame .uplot").length
  );
  check("desktop: four uPlot charts render", chartCount === 4, `count=${chartCount}`);

  const initial = await page.evaluate(chartState, 0);
  check(
    "desktop: initial window is one week",
    Math.abs(initial.span - 604800) < 5,
    `span=${initial.span}`
  );

  // Hover scrub fills legend values.
  const firstOverlay = page.locator(".chart-frame .u-over").first();
  await firstOverlay.scrollIntoViewIfNeeded();
  const box = await firstOverlay.boundingBox();
  await page.mouse.move(box.x + box.width * 0.5, box.y + box.height * 0.5);
  await page.waitForTimeout(200);
  const hovered = await page.evaluate(chartState, 0);
  check(
    "desktop: hover sets cursor and live legend values",
    hovered.cursorIdx != null &&
      hovered.legendValues.some((value) => /\d/.test(value)),
    `idx=${hovered.cursorIdx} legend=${JSON.stringify(hovered.legendValues)}`
  );

  // Ctrl+wheel zooms in around the pointer.
  await page.keyboard.down("Control");
  await page.mouse.wheel(0, -240);
  await page.keyboard.up("Control");
  await page.waitForTimeout(200);
  const zoomed = await page.evaluate(chartState, 0);
  check(
    "desktop: ctrl+wheel zooms in",
    zoomed.span < initial.span,
    `span ${initial.span} -> ${zoomed.span}`
  );

  // Shift+wheel pans.
  await page.keyboard.down("Shift");
  await page.mouse.wheel(0, -240);
  await page.keyboard.up("Shift");
  await page.waitForTimeout(200);
  const panned = await page.evaluate(chartState, 0);
  check(
    "desktop: shift+wheel pans",
    panned.xMin !== zoomed.xMin && Math.abs(panned.span - zoomed.span) < 2,
    `xMin ${zoomed.xMin} -> ${panned.xMin}`
  );

  // Drag-select zooms.
  await page.mouse.move(box.x + box.width * 0.3, box.y + box.height * 0.5);
  await page.mouse.down();
  await page.mouse.move(box.x + box.width * 0.6, box.y + box.height * 0.5, { steps: 8 });
  await page.mouse.up();
  await page.waitForTimeout(200);
  const dragZoomed = await page.evaluate(chartState, 0);
  check(
    "desktop: drag-select zooms",
    dragZoomed.span < panned.span,
    `span ${panned.span} -> ${dragZoomed.span}`
  );

  // Range buttons still work.
  const buttons = page.locator(".chart-card").first().locator(".chart-actions button");
  await buttons.nth(1).click();
  await page.waitForTimeout(200);
  const fullRange = await page.evaluate(chartState, 0);
  await buttons.nth(0).click();
  await page.waitForTimeout(200);
  const weekRange = await page.evaluate(chartState, 0);
  check(
    "desktop: All/1w buttons restore ranges",
    fullRange.span > 604800 * 2 && Math.abs(weekRange.span - 604800) < 5,
    `full=${fullRange.span} week=${weekRange.span}`
  );

  // Rainfall hover value carries mm on the absolute humidity chart (index 1).
  const rainLegend = await page.evaluate(() => {
    const frame = document.querySelectorAll(".chart-frame")[1];
    frame.scrollIntoView();
    const plot = frame.chartPlot;
    const data = plot.data;
    const rainIndex = data.length - 1;
    let index = -1;
    for (let i = data[0].length - 1; i >= 0; i -= 1) {
      const value = data[rainIndex][i];
      const timestamp = data[0][i];
      if (
        value != null &&
        value > 0 &&
        timestamp >= plot.scales.x.min &&
        timestamp <= plot.scales.x.max
      ) {
        index = i;
        break;
      }
    }
    if (index === -1) return { skipped: true };
    const left = plot.valToPos(data[0][index], "x");
    plot.setCursor({ left, top: 30 });
    const cells = Array.from(frame.querySelectorAll(".u-legend .u-value")).map((cell) =>
      cell.textContent.trim()
    );
    return { skipped: false, cells };
  });
  check(
    "desktop: rainfall hover value shows mm per hour",
    rainLegend.skipped || rainLegend.cells.some((cell) => / mm per hour$/.test(cell)),
    rainLegend.skipped ? "no in-window rain, skipped" : JSON.stringify(rainLegend.cells)
  );

  check(
    "desktop: no console errors/warnings",
    consoleErrors.length === 0,
    consoleErrors.join(" | ") || "clean"
  );

  await page.screenshot({
    path: `${screenshotDir}/ticket-23-touch-desktop.png`,
    fullPage: false,
  });
  await context.close();
}

// ---------- Mobile: 390x844, touch ----------
{
  const context = await browser.newContext({
    viewport: { width: 390, height: 844 },
    hasTouch: true,
    isMobile: true,
    deviceScaleFactor: 3,
    userAgent:
      "Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) AppleWebKit/605.1.15 " +
      "(KHTML, like Gecko) Version/17.0 Mobile/15E148 Safari/604.1",
  });
  const page = await context.newPage();
  const consoleErrors = await loadPage(page);

  const layout = await page.evaluate(() => ({
    charts: document.querySelectorAll(".chart-frame .uplot").length,
    scrollWidth: document.documentElement.scrollWidth,
    clientWidth: document.documentElement.clientWidth,
    touchAction: getComputedStyle(document.querySelector(".chart-frame .u-over"))
      .touchAction,
  }));
  check(
    "mobile: four charts, no horizontal overflow",
    layout.charts === 4 && layout.scrollWidth <= layout.clientWidth,
    `charts=${layout.charts} scrollWidth=${layout.scrollWidth} clientWidth=${layout.clientWidth}`
  );
  check(
    "mobile: chart overlay uses touch-action pan-y",
    layout.touchAction === "pan-y",
    `touch-action=${layout.touchAction}`
  );

  await page.evaluate(() => {
    document.querySelectorAll(".chart-frame")[0].scrollIntoView({ block: "center" });
  });
  await page.waitForTimeout(200);

  // Tap reads values.
  const tapResult = await page.evaluate(
    ([dispatchSource]) => {
      const dispatch = eval(`(${dispatchSource})`);
      dispatch(0, "touchstart", [{ x: 0.5, y: 0.5 }]);
      dispatch(0, "touchend", [{ x: 0.5, y: 0.5 }]);
      const frame = document.querySelectorAll(".chart-frame")[0];
      return {
        cursorIdx: frame.chartPlot.cursor.idx,
        legendValues: Array.from(frame.querySelectorAll(".u-legend .u-value")).map(
          (cell) => cell.textContent.trim()
        ),
      };
    },
    [dispatchTouch.toString()]
  );
  check(
    "mobile: tap sets cursor and legend values",
    tapResult.cursorIdx != null && tapResult.legendValues.some((v) => /\d/.test(v)),
    `idx=${tapResult.cursorIdx} legend=${JSON.stringify(tapResult.legendValues)}`
  );

  // Horizontal one-finger scrub is claimed (preventDefault) and moves the cursor.
  const scrubResult = await page.evaluate(
    ([dispatchSource]) => {
      const dispatch = eval(`(${dispatchSource})`);
      dispatch(0, "touchstart", [{ x: 0.3, y: 0.5 }]);
      dispatch(0, "touchmove", [{ x: 0.34, y: 0.505 }]);
      const prevented = dispatch(0, "touchmove", [{ x: 0.7, y: 0.51 }]);
      const frame = document.querySelectorAll(".chart-frame")[0];
      const duringIdx = frame.chartPlot.cursor.idx;
      dispatch(0, "touchend", [{ x: 0.7, y: 0.51 }]);
      return { prevented, duringIdx };
    },
    [dispatchTouch.toString()]
  );
  check(
    "mobile: horizontal scrub claims the gesture and moves cursor",
    scrubResult.prevented === true && scrubResult.duringIdx != null,
    `prevented=${scrubResult.prevented} idx=${scrubResult.duringIdx}`
  );

  // Vertical one-finger movement is NOT claimed — page scroll stays with the browser.
  const verticalResult = await page.evaluate(
    ([dispatchSource]) => {
      const dispatch = eval(`(${dispatchSource})`);
      dispatch(0, "touchstart", [{ x: 0.5, y: 0.3 }]);
      const preventedFirst = dispatch(0, "touchmove", [{ x: 0.505, y: 0.5 }]);
      const preventedSecond = dispatch(0, "touchmove", [{ x: 0.51, y: 0.8 }]);
      dispatch(0, "touchend", [{ x: 0.51, y: 0.8 }]);
      return { preventedFirst, preventedSecond };
    },
    [dispatchTouch.toString()]
  );
  check(
    "mobile: vertical swipe left to the browser (page scroll)",
    verticalResult.preventedFirst === false && verticalResult.preventedSecond === false,
    JSON.stringify(verticalResult)
  );

  // Pinch zooms in; two-finger drag pans. uPlot applies setScale on a deferred
  // commit, so read the scale on a later tick than the dispatched events.
  const beforePinch = await page.evaluate(chartState, 0);
  await page.evaluate(
    ([dispatchSource]) => {
      const dispatch = eval(`(${dispatchSource})`);
      dispatch(0, "touchstart", [
        { x: 0.4, y: 0.5 },
        { x: 0.6, y: 0.5 },
      ]);
      dispatch(0, "touchmove", [
        { x: 0.2, y: 0.5 },
        { x: 0.8, y: 0.5 },
      ]);
      dispatch(0, "touchend", [
        { x: 0.2, y: 0.5 },
        { x: 0.8, y: 0.5 },
      ]);
    },
    [dispatchTouch.toString()]
  );
  await page.waitForTimeout(150);
  const afterZoom = await page.evaluate(chartState, 0);
  check(
    "mobile: pinch-out zooms in",
    afterZoom.span < beforePinch.span,
    `span ${beforePinch.span} -> ${afterZoom.span}`
  );

  await page.evaluate(
    ([dispatchSource]) => {
      const dispatch = eval(`(${dispatchSource})`);
      dispatch(0, "touchstart", [
        { x: 0.3, y: 0.5 },
        { x: 0.6, y: 0.5 },
      ]);
      dispatch(0, "touchmove", [
        { x: 0.5, y: 0.5 },
        { x: 0.8, y: 0.5 },
      ]);
      dispatch(0, "touchend", [
        { x: 0.5, y: 0.5 },
        { x: 0.8, y: 0.5 },
      ]);
    },
    [dispatchTouch.toString()]
  );
  await page.waitForTimeout(150);
  const afterPan = await page.evaluate(chartState, 0);
  check(
    "mobile: two-finger drag pans without changing span",
    afterPan.xMin !== afterZoom.xMin && Math.abs(afterPan.span - afterZoom.span) < 2,
    `xMin ${afterZoom.xMin} -> ${afterPan.xMin}, span ${afterZoom.span} -> ${afterPan.span}`
  );

  // Range buttons work with touch taps.
  const chartTop = page.locator(".chart-card").first();
  await chartTop.locator(".chart-actions button").nth(0).tap();
  await page.waitForTimeout(200);
  const weekAfterTap = await page.evaluate(chartState, 0);
  check(
    "mobile: 1w button restores the week window by tap",
    Math.abs(weekAfterTap.span - 604800) < 5,
    `span=${weekAfterTap.span}`
  );

  check(
    "mobile: no console errors/warnings",
    consoleErrors.length === 0,
    consoleErrors.join(" | ") || "clean"
  );

  await page.screenshot({
    path: `${screenshotDir}/ticket-23-touch-mobile.png`,
    fullPage: false,
  });
  await context.close();
}

await browser.close();

if (failures.length > 0) {
  console.error(`\n${failures.length} check(s) failed`);
  process.exit(1);
}
console.log("\nAll checks passed");
