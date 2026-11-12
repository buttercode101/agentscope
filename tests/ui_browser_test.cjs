const http = require("node:http");
const fs = require("node:fs");
const path = require("node:path");
const { chromium } = require("playwright");

const root = path.resolve(__dirname, "..");
const siteRoot = path.join(root, "site");
const artifacts = path.join(root, "artifacts");
fs.mkdirSync(artifacts, { recursive: true });

const mime = {
  ".html": "text/html; charset=utf-8",
  ".json": "application/json; charset=utf-8",
  ".css": "text/css; charset=utf-8",
  ".js": "text/javascript; charset=utf-8",
};

const server = http.createServer((req, res) => {
  let pathname;
  try {
    pathname = decodeURIComponent(new URL(req.url, "http://127.0.0.1").pathname);
  } catch {
    res.writeHead(400).end("Bad request");
    return;
  }
  if (pathname.endsWith("/")) pathname += "index.html";
  const file = path.resolve(siteRoot, "." + pathname);
  if (!file.startsWith(siteRoot + path.sep)) {
    res.writeHead(403).end("Forbidden");
    return;
  }
  fs.readFile(file, (error, data) => {
    if (error) {
      res.writeHead(404).end("Not found");
      return;
    }
    res.writeHead(200, {
      "Content-Type": mime[path.extname(file)] || "application/octet-stream",
      "Cache-Control": "no-store",
    });
    res.end(data);
  });
});

function assert(condition, message) {
  if (!condition) throw new Error(message);
}

async function main() {
  await new Promise(resolve => server.listen(4173, "127.0.0.1", resolve));
  const browser = await chromium.launch({ headless: true, args: ["--no-sandbox"] });
  const errors = [];
  const widths = [320, 375, 768, 1120, 1440];
  const pages = [
    { path: "/", name: "home" },
    { path: "/demo.html", name: "demo" },
    { path: "/proofs.html", name: "proofs" },
  ];

  try {
    for (const item of pages) {
      for (const width of widths) {
        const page = await browser.newPage({ viewport: { width, height: 900 }, deviceScaleFactor: 1 });
        page.on("pageerror", error => errors.push(item.name + "@" + width + ": " + error.message));
        await page.goto("http://127.0.0.1:4173" + item.path, { waitUntil: "networkidle" });
        await page.waitForTimeout(100);

        const metrics = await page.evaluate(() => ({
          viewport: document.documentElement.clientWidth,
          document: document.documentElement.scrollWidth,
          title: document.title,
        }));
        assert(metrics.document <= metrics.viewport + 1,
          item.name + "@" + width + ": horizontal page overflow (" + metrics.document + "px > " + metrics.viewport + "px)");
        assert(metrics.title.length > 0, item.name + "@" + width + ": missing title");

        if (width === 320 || width === 1440) {
          await page.screenshot({
            path: path.join(artifacts, item.name + "-" + width + ".png"),
            fullPage: true,
          });
        }

        if (item.name === "home" && width === 320) {
          await page.keyboard.press("Tab");
          const focused = await page.evaluate(() => document.activeElement?.classList.contains("skip-link"));
          assert(focused, "homepage: keyboard Tab does not focus the skip link");
          assert(await page.locator('a[href="/demo.html"]').count() >= 1, "homepage: demo navigation link missing");
          assert(await page.locator('a[href="/proofs.html"]').count() >= 1, "homepage: proof navigation link missing");
        }

        if (item.name === "demo" && width === 320) {
          const cadenceVisible = await page.locator(".table th").nth(1).evaluate(el => getComputedStyle(el).display !== "none");
          const statusVisible = await page.locator(".act span:last-child").first().evaluate(el => getComputedStyle(el).display !== "none");
          const tableScroll = await page.locator(".table-scroll").evaluate(el => el.scrollWidth > el.clientWidth);
          assert(cadenceVisible, "demo@320: cadence column is hidden");
          assert(statusVisible, "demo@320: action outcome is hidden");
          assert(tableScroll, "demo@320: narrow table has no contained horizontal scroll");
          const last24 = page.locator('.filter[data-days="1"]');
          await last24.click();
          assert(await last24.getAttribute("aria-pressed") === "true", "demo: 24-hour filter did not expose pressed state");
          assert(await page.locator('.act[data-age="26"]').evaluate(el => getComputedStyle(el).display === "none"),
            "demo: 24-hour filter did not hide older activity");
          await page.locator('.filter[data-days="7"]').click();
          assert(await page.locator('.act[data-age="26"]').evaluate(el => getComputedStyle(el).display !== "none"),
            "demo: 7-day filter did not restore older activity");
        }

        if (item.name === "proofs" && width === 320) {
          await page.waitForFunction(() => document.querySelectorAll("#proof-list .proof").length === 2);
          const cards = page.locator("#proof-list .proof");
          assert(await cards.count() === 2, "proof explorer: expected two historical proof cards");
          for (let i = 0; i < await cards.count(); i++) {
            const card = cards.nth(i);
            const result = (await card.locator(".check").first().textContent()).trim();
            assert(result === "BUNDLE CHECKS PASSED", "proof explorer: card " + i + " failed: " + result);
            assert((await card.locator(".check").nth(1).textContent()).includes("LEDGER EXPORT: INTACT"),
              "proof explorer: card " + i + " ledger export status missing");
          }
          await page.keyboard.press("Tab");
          const focused = await page.evaluate(() => document.activeElement?.classList.contains("skip-link"));
          assert(focused, "proof explorer: keyboard Tab does not focus the skip link");
        }

        await page.close();
      }
    }

    assert(errors.length === 0, "browser runtime errors:\n" + errors.join("\n"));
    console.log("Browser UI acceptance passed: 3 pages × 5 widths; mobile filters, table visibility, keyboard navigation and both Habitat proof bundles verified.");
    console.log("Screenshots: artifacts/{home,demo,proofs}-{320,1440}.png");
  } finally {
    await browser.close();
    await new Promise(resolve => server.close(resolve));
  }
}

main().catch(error => {
  console.error(error);
  process.exitCode = 1;
});
