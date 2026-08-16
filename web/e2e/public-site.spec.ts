import AxeBuilder from "@axe-core/playwright";
import { expect, test } from "@playwright/test";

const releaseId = "fixture-2026-08-16-001";

test("home, detail, and search use the same immutable release", async ({
  page,
  request,
}) => {
  await page.goto("/");
  await expect(
    page.getByRole("heading", { name: /最近有什么骗局/ }),
  ).toBeVisible();
  await expect(page.getByText(releaseId)).toBeVisible();

  const metadata = await request.get("/release.json");
  expect(metadata.ok()).toBeTruthy();
  expect((await metadata.json()).release_id).toBe(releaseId);

  await page.goto("/search/");
  await page.getByLabel("只输入一个或几个关键词").fill("百万保障");
  await page.getByRole("button", { name: "查一查" }).click();
  await expect(
    page.getByRole("heading", { name: /找到 1 条相似记录/ }),
  ).toBeVisible();
  await page
    .getByRole("link", { name: "“百万保障”假客服骗局", exact: true })
    .click();
  await expect(page).toHaveURL(/million-protection-fake-customer-service/);
  await expect(page.getByRole("heading", { level: 1 })).toContainText(
    "百万保障",
  );
});

test("no-result state gives a safe next action without claiming safety", async ({
  page,
}) => {
  await page.goto("/search/");
  await page.getByLabel("只输入一个或几个关键词").fill("完全不存在的测试词");
  await page.getByRole("button", { name: "查一查" }).click();
  await expect(
    page.getByRole("heading", { name: "暂时没有找到相似的已知骗局" }),
  ).toBeVisible();
  await expect(
    page.getByText("这不代表它一定安全", { exact: false }),
  ).toBeVisible();
});

test("key public pages have no automatically detectable serious accessibility issues", async ({
  page,
}) => {
  for (const path of [
    "/",
    "/search/",
    "/scam/million-protection-fake-customer-service/",
  ]) {
    await page.goto(path);
    const results = await new AxeBuilder({ page })
      .withTags(["wcag2a", "wcag2aa"])
      .analyze();
    expect(results.violations).toEqual([]);
  }
});

test("admin fixture decisions are visibly non-durable", async ({ page }) => {
  await page.goto("/admin/review/");
  await page.getByRole("button", { name: "先保留，等待更多证据" }).click();
  await expect(page.getByRole("status")).toContainText("没有写入数据库");
});
