import assert from "node:assert/strict";
import test from "node:test";

import { dispatchBackup } from "../src/index.mjs";

const enabled = {
  SCAM_RADAR_BACKUP_SCHEDULER_ENABLED: "true",
  GITHUB_ACTIONS_TOKEN: "synthetic-token",
};

test("disabled backup scheduler makes no request", async () => {
  let calls = 0;
  assert.equal(await dispatchBackup({}, async () => { calls++; }), "disabled");
  assert.equal(calls, 0);
});

test("backup scheduler dispatches one fixed workflow", async () => {
  let call;
  assert.equal(await dispatchBackup(enabled, async (url, options) => {
    call = { url, options };
    return { status: 204 };
  }), "accepted");
  assert.equal(call.url,
    "https://api.github.com/repos/Insparian/scam-radar/actions/workflows/backup.yml/dispatches");
  assert.deepEqual(JSON.parse(call.options.body), {
    ref: "main", inputs: { scheduled: "true" },
  });
  assert.equal(call.options.redirect, "error");
});

test("missing token and rejected dispatch fail closed", async () => {
  await assert.rejects(() => dispatchBackup({ ...enabled, GITHUB_ACTIONS_TOKEN: "" }),
    /github_actions_token_required/);
  await assert.rejects(() => dispatchBackup(enabled, async () => ({ status: 403 })),
    /github_dispatch_rejected_403/);
});
