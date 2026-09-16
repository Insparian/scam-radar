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
  await expect(page.getByText("Policy Engine", { exact: true })).toBeVisible();
  await expect(
    page.getByText("公开预览 · 当前使用固定测试资料，不代表实时骗局信息"),
  ).toBeVisible();

  const metadata = await request.get("/release.json");
  expect(metadata.ok()).toBeTruthy();
  const releaseMetadata = await metadata.json();
  expect(releaseMetadata.release_id).toBe(releaseId);
  expect(releaseMetadata.schema_version).toBe(2);
  expect(releaseMetadata.manifest_hash).toMatch(/^[a-f0-9]{64}$/);
  expect(releaseMetadata.published_at).toMatch(/^2026-/);

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
  await expect(
    page.getByText("Last Verified / 信息核实至", { exact: true }),
  ).toBeVisible();
  await expect(
    page.getByText("Release / 当前版本形成于", { exact: true }),
  ).toBeVisible();
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

test("admin fails closed when the production Auth client is not configured", async ({
  page,
}) => {
  await page.goto("/admin/review/");
  await expect(
    page.getByRole("heading", { name: "审核登录尚未配置" }),
  ).toBeVisible();
  await expect(
    page.getByText("因此不会发送登录或审核请求", { exact: false }),
  ).toBeVisible();

  await page.goto("/admin/login/");
  await expect(page.getByRole("heading", { name: "登录审核台" })).toBeVisible();
  await expect(
    page.getByText("当前构建没有连接生产审核系统", { exact: false }),
  ).toBeVisible();
  await expect(page.getByLabel("审核邮箱")).toHaveCount(0);
});
