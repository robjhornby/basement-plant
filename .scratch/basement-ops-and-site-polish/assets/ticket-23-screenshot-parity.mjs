// Ticket 23: capture production dashboard and prototype frutiger-aero.html at the
// same viewports/regions so the renders can be diffed side by side.
// Run: NODE_PATH="$(npm root -g)" node .scratch/basement-ops-and-site-polish/assets/ticket-23-screenshot-parity.mjs
import { pathToFileURL } from "node:url";
import path from "node:path";
import fs from "node:fs";
import { createRequire } from "node:module";

const globalRequire = createRequire(
  "/Users/rob/.nvm/versions/node/v24.4.1/lib/node_modules/@playwright/cli/index.js"
);
const { chromium } = globalRequire("playwright-core");

const repo = "/Users/rob/projects/basement";
const pages = {
  production: pathToFileURL(path.join(repo, "build/basement-site/index.html")).href,
  prototype: pathToFileURL(
    path.join(repo, "prototypes/site-redesign-mockups/frutiger-aero.html")
  ).href,
};
const viewports = {
  desktop: { width: 1440, height: 900 },
  mobile: { width: 390, height: 844 },
};
const outDir = path.join(repo, "output/playwright/ticket-23");
fs.mkdirSync(outDir, { recursive: true });

const browser = await chromium.launch({
  executablePath:
    process.env.HOME +
    "/Library/Caches/ms-playwright/chromium_headless_shell-1223/chrome-headless-shell-mac-arm64/chrome-headless-shell",
});
for (const [pageName, url] of Object.entries(pages)) {
  for (const [viewportName, viewport] of Object.entries(viewports)) {
    const context = await browser.newContext({
      viewport,
      reducedMotion: "reduce",
      deviceScaleFactor: 2,
    });
    const page = await context.newPage();
    await page.goto(url, { waitUntil: "networkidle" });
    // The prototype switcher pill is not part of the design; hide it.
    await page.addStyleTag({ content: ".proto-switcher { display: none !important; }" });
    await page.waitForTimeout(600);

    const shoot = async (label) =>
      page.screenshot({
        path: path.join(outDir, `${pageName}-${viewportName}-${label}.png`),
      });

    await shoot("fold");

    const cards = page.locator(".chart-card");
    const cardCount = await cards.count();
    for (const index of [0, 1, 2, 3]) {
      if (index >= cardCount) continue;
      await cards.nth(index).scrollIntoViewIfNeeded();
      await page.evaluate(() => window.scrollBy(0, -40));
      await page.waitForTimeout(250);
      await shoot(`chart-${index}`);
    }

    await page.evaluate(() => window.scrollTo(0, document.body.scrollHeight));
    await page.waitForTimeout(250);
    await shoot("floor");

    // Hover the first chart mid-plot so the live legend shows values with units.
    const overlay = page.locator(".chart-card .u-over").first();
    await overlay.scrollIntoViewIfNeeded();
    await page.evaluate(() => window.scrollBy(0, -60));
    const box = await overlay.boundingBox();
    if (box) {
      await page.mouse.move(box.x + box.width * 0.55, box.y + box.height * 0.5);
      await page.waitForTimeout(250);
      await shoot("hover-legend");
    }
    await context.close();
    console.log(`captured ${pageName} ${viewportName}`);
  }
}
await browser.close();
