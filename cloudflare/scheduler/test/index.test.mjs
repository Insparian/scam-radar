import assert from "node:assert/strict";
import test from "node:test";

import { dispatchCollection } from "../src/index.mjs";

const enabled = {
  SCAM_RADAR_SCHEDULER_ENABLED: "true",
  SCAM_RADAR_SOURCE_KEY: "mps-anti-fraud",
  GITHUB_ACTIONS_TOKEN: "synthetic-token",
};

test("disabled scheduler makes no outbound request", async () => {
  let calls = 0;
  const outcome = await dispatchCollection(
    { ...enabled, SCAM_RADAR_SCHEDULER_ENABLED: "false" },
    async () => {
      calls += 1;
      throw new Error("unexpected_network_request");
    },
  );
  assert.equal(outcome, "disabled");
  assert.equal(calls, 0);
});

test("one approved source dispatches a bounded live batch", async () => {
  let call;
  const outcome = await dispatchCollection(enabled, async (url, options) => {
    call = { url, options };
    return { status: 200 };
  });

  assert.equal(outcome, "accepted");
  assert.equal(
    call.url,
    "https://api.github.com/repos/Insparian/scam-radar/actions/workflows/collect.yml/dispatches",
  );
  assert.equal(call.options.method, "POST");
  assert.equal(call.options.redirect, "error");
  assert.deepEqual(JSON.parse(call.options.body), {
    ref: "main",
    inputs: { source_key: "mps-anti-fraud", dry_run: "false" },
  });
  assert.equal(call.options.headers.Authorization, "Bearer synthetic-token");
});

test("invalid source or missing token fails before network", async () => {
  for (const env of [
    { ...enabled, SCAM_RADAR_SOURCE_KEY: "all" },
    { ...enabled, SCAM_RADAR_SOURCE_KEY: "../other" },
    { ...enabled, SCAM_RADAR_SOURCE_KEY: 123 },
    { ...enabled, GITHUB_ACTIONS_TOKEN: "" },
    { ...enabled, GITHUB_ACTIONS_TOKEN: "bad token with spaces" },
  ]) {
    await assert.rejects(
      () => dispatchCollection(env, async () => { throw new Error("network_called"); }),
      /approved_source_key_required|github_actions_token_required/,
    );
  }
});

test("GitHub failure stays failed without logging response or token", async () => {
  await assert.rejects(
    () => dispatchCollection(enabled, async () => ({ status: 403 })),
    /^Error: github_dispatch_rejected_403$/,
  );
});
