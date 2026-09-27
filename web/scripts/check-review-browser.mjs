import { mkdir } from "node:fs/promises";
import { fileURLToPath } from "node:url";
import { dirname, resolve } from "node:path";

import { chromium, expect } from "@playwright/test";

const baseUrl = process.env.SCAM_RADAR_REVIEW_BASE_URL;
const email = process.env.SCAM_RADAR_REVIEW_EMAIL;
const password = process.env.SCAM_RADAR_REVIEW_PASSWORD;
if (!baseUrl?.startsWith("http://127.0.0.1:") || !email || !password) {
  throw new Error("local_review_browser_configuration_required");
}

const root = resolve(dirname(fileURLToPath(import.meta.url)), "../..");
const screenshot = resolve(
  root,
  "work/launch-readiness/joined-review-browser.png",
);
const browser = await chromium.launch();
try {
  const page = await browser.newPage({
    viewport: { width: 1280, height: 900 },
  });
  const offHostRequests = [];
  page.on("request", (request) => {
    if (new URL(request.url()).hostname !== "127.0.0.1") {
      offHostRequests.push(request.url());
    }
  });

  await page.goto(`${baseUrl}/admin/login/`);
  await page.getByLabel("审核邮箱").fill(email);
  await page.getByLabel("密码").fill(password);
  await page.getByRole("button", { name: "登录", exact: true }).click();
  await expect(page.getByRole("heading", { name: "需要人工决定" })).toBeVisible(
    {
      timeout: 30_000,
    },
  );

  const queue = page.locator(".queue-list button");
  await expect(queue).toHaveCount(2);
  const targetName = "合成补贴来电骗局";
  const candidate = queue.filter({ hasText: targetName });
  const seeded = queue.filter({ hasNotText: targetName });
  await expect(candidate).toHaveCount(1);
  await expect(seeded).toHaveCount(1);

  await seeded.click();
  await page.getByLabel("决定说明").fill("隔离合成候选：不公开");
  await page.getByRole("button", { name: "不公开", exact: true }).click();
  await expect(page.getByRole("status")).toContainText(
    "不公开决定已写入数据库",
  );
  await expect(page.locator(".queue-list button")).toHaveCount(1);

  await page.locator(".queue-list button").click();
  const evidenceButtons = page.getByRole("button", { name: "接受为依据" });
  const evidenceCount = await evidenceButtons.count();
  if (evidenceCount < 1)
    throw new Error("review_candidate_has_no_proposed_evidence");
  for (let index = 0; index < evidenceCount; index += 1) {
    await evidenceButtons.nth(index).click();
  }
  await page.getByLabel("决定说明").fill("隔离本地合成来源逐条核验并接受依据");
  await page.getByRole("button", { name: "批准新记录" }).click();
  await expect(page.getByRole("status")).toContainText("审核决定已写入数据库");
  await expect(
    page.getByRole("heading", { name: "目前没有需要人工决定的项目" }),
  ).toBeVisible();
  if (offHostRequests.length)
    throw new Error("review_browser_sent_nonlocal_request");

  await mkdir(dirname(screenshot), { recursive: true });
  await page.screenshot({ path: screenshot, fullPage: true });
  process.stdout.write(
    "GREEN local browser login → reject → evidence decisions → approve; requests localhost only\n",
  );
} finally {
  await browser.close();
}
