import assert from "node:assert/strict";
import { createServer } from "node:http";
import { readFile, mkdir } from "node:fs/promises";
import { extname, resolve, sep } from "node:path";
import { chromium } from "@playwright/test";
import AxeBuilder from "@axe-core/playwright";

const [siteArgument, releaseId, outputArgument, expectedCountArgument] =
  process.argv.slice(2);
if (!siteArgument || !releaseId || !outputArgument) {
  throw new Error("usage: check-release-browser.mjs SITE RELEASE_ID OUTPUT");
}
const site = resolve(siteArgument);
const output = resolve(outputArgument);
const expectedCount = Number(expectedCountArgument ?? 1);
if (![0, 1].includes(expectedCount)) {
  throw new Error("expected count must be 0 or 1");
}
const release = JSON.parse(
  await readFile(resolve(site, "release.json"), "utf8"),
);
const search = JSON.parse(
  await readFile(resolve(site, "search-index.json"), "utf8"),
);
assert.equal(release.release_id, releaseId);
assert.equal(search.release_id, releaseId);
assert.equal(search.items.length, expectedCount);
assert.equal(release.pattern_count, expectedCount);
const match = search.items[0];
const name = match?.canonical_name ?? "合成补贴来电骗局";
await mkdir(output, { recursive: true });

const contentType = {
  ".html": "text/html; charset=utf-8",
  ".js": "text/javascript; charset=utf-8",
  ".css": "text/css; charset=utf-8",
  ".json": "application/json; charset=utf-8",
  ".svg": "image/svg+xml",
  ".png": "image/png",
  ".ico": "image/x-icon",
};
const server = createServer(async (request, response) => {
  const pathname = decodeURIComponent(
    new URL(request.url, "http://localhost").pathname,
  );
  const target = resolve(
    site,
    `.${pathname}`,
    pathname.endsWith("/") ? "index.html" : "",
  );
  if (target !== site && !target.startsWith(site + sep)) {
    response.writeHead(403).end();
    return;
  }
  try {
    const body = await readFile(target);
    response.writeHead(200, {
      "Content-Type":
        contentType[extname(target)] ?? "application/octet-stream",
    });
    response.end(body);
  } catch {
    response.writeHead(404).end();
  }
});
await new Promise((done) => server.listen(0, "127.0.0.1", done));
const address = server.address();
const base = `http://127.0.0.1:${address.port}`;
const browser = await chromium.launch();
try {
  for (const width of [360, 390, 768, 1440]) {
    const context = await browser.newContext({
      viewport: { width, height: 900 },
    });
    const page = await context.newPage();
    const requests = [];
    page.on("request", (request) => requests.push(request.url()));
    await page.goto(base + "/");
    assert.equal((await page.getByText(releaseId).count()) > 0, true);
    assert.equal(
      await page.evaluate(
        () => document.documentElement.scrollWidth <= innerWidth,
      ),
      true,
    );
    await page.screenshot({
      path: resolve(output, `${width}-home.png`),
      fullPage: true,
    });
    await page.locator(".category-grid a").first().click();
    await page.waitForURL(new RegExp(`${base}/search/?$`));
    assert.equal(
      await page.getByLabel("只输入一个或几个关键词").inputValue(),
      "电话",
    );
    assert.equal(
      requests.some((url) => decodeURIComponent(url).includes("电话")),
      false,
    );
    await page.goto(base + "/search/");
    const input = page.getByLabel("只输入一个或几个关键词");
    await input.focus();
    assert.equal(
      await input.evaluate((node) => document.activeElement === node),
      true,
    );
    await input.fill(name);
    await input.press("Enter");
    if (match) {
      await page.getByRole("heading", { name: /找到 1 条相似记录/ }).waitFor();
    } else {
      await page
        .getByRole("heading", { name: "暂时没有找到相似的已知骗局" })
        .waitFor();
      assert.equal(
        (await page.getByText("这不代表它一定安全", { exact: false }).count()) >
          0,
        true,
      );
    }
    assert.equal(page.url().includes(encodeURIComponent(name)), false);
    assert.equal(
      requests.some((url) => decodeURIComponent(url).includes(name)),
      false,
    );
    assert.equal(
      await page.evaluate(
        () =>
          Object.values(localStorage).join() +
          Object.values(sessionStorage).join(),
      ),
      "",
    );
    assert.equal(
      await page.evaluate(
        () => document.documentElement.scrollWidth <= innerWidth,
      ),
      true,
    );
    await page.screenshot({
      path: resolve(output, `${width}-search.png`),
      fullPage: true,
    });
    if (match) {
      await page.getByRole("link", { name, exact: true }).click();
      await page.waitForURL(new RegExp(`/scam/${match.slug}/?$`));
      await page.getByRole("heading", { name: "现在先做什么" }).waitFor();
      assert.equal(
        await page.evaluate(
          () => document.documentElement.scrollWidth <= innerWidth,
        ),
        true,
      );
      await page.screenshot({
        path: resolve(output, `${width}-detail.png`),
        fullPage: true,
      });
    } else {
      const sentinel = await page.goto(base + "/scam/release-empty/");
      assert.equal(sentinel.status(), 404);
    }
    await page.goto(base + "/search/");
    await page.getByLabel("只输入一个或几个关键词").fill("不存在的合成词");
    await page.getByRole("button", { name: "查一查" }).click();
    await page
      .getByRole("heading", { name: "暂时没有找到相似的已知骗局" })
      .waitFor();
    assert.equal(
      (await page.getByText("这不代表它一定安全", { exact: false }).count()) >
        0,
      true,
    );
    await page.goto(base + "/404.html");
    assert.equal(
      await page.evaluate(
        () => document.documentElement.scrollWidth <= innerWidth,
      ),
      true,
    );
    if (width === 390) {
      for (const path of [
        "/",
        "/search/",
        ...(match ? [`/scam/${match.slug}/`] : []),
      ]) {
        await page.goto(base + path);
        const audit = await new AxeBuilder({ page })
          .withTags(["wcag2a", "wcag2aa"])
          .analyze();
        assert.deepEqual(audit.violations, []);
      }
    }
    await context.close();
  }
  console.log(
    `GREEN exact SQL release browser path at 360/390/768/1440: ${releaseId}`,
  );
} finally {
  await browser.close();
  await new Promise((done) => server.close(done));
}
