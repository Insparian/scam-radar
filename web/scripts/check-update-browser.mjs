import { mkdir } from "node:fs/promises";
import { fileURLToPath } from "node:url";
import { dirname, resolve } from "node:path";

import { chromium, expect } from "@playwright/test";

const baseUrl = process.env.SCAM_RADAR_REVIEW_BASE_URL;
const email = process.env.SCAM_RADAR_REVIEW_EMAIL;
const password = process.env.SCAM_RADAR_REVIEW_PASSWORD;
const decision = process.env.SCAM_RADAR_REVIEW_DECISION;
if (
  !baseUrl?.startsWith("http://127.0.0.1:") ||
  !email ||
  !password ||
  !["approve", "reject"].includes(decision)
) {
  throw new Error("local_update_browser_configuration_required");
}

const root = resolve(dirname(fileURLToPath(import.meta.url)), "../..");
const screenshot = resolve(
  root,
  `work/launch-readiness/joined-update-${decision}-browser.png`,
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
  const before = await queue.count();
  let foundUpdate = false;
  for (let index = 0; index < before; index += 1) {
    await queue.nth(index).click();
    if (await page.getByRole("button", { name: "确认更新" }).isVisible()) {
      foundUpdate = true;
      break;
    }
  }
  if (!foundUpdate) throw new Error("local_update_review_item_missing");
  if (decision === "approve") {
    const proposed = page.getByRole("button", { name: "接受为依据" });
    await expect(proposed).toHaveCount(1);
    await proposed.click();
    await page
      .getByLabel("决定说明")
      .fill("隔离合成追加案例：核对来源后接受新依据");
    await page.getByRole("button", { name: "确认更新" }).click();
    await expect(page.getByRole("status")).toContainText(
      "审核决定已写入数据库",
    );
  } else {
    await page
      .getByLabel("决定说明")
      .fill("隔离合成追加案例：本条依据不足，不公开");
    await page.getByRole("button", { name: "不公开", exact: true }).click();
    await expect(page.getByRole("status")).toContainText(
      "不公开决定已写入数据库",
    );
  }
  await expect(queue).toHaveCount(before - 1);
  if (offHostRequests.length)
    throw new Error("update_browser_sent_nonlocal_request");
  await mkdir(dirname(screenshot), { recursive: true });
  await page.screenshot({ path: screenshot, fullPage: true });
  process.stdout.write(`GREEN local browser existing update ${decision}\n`);
} finally {
  await browser.close();
}
