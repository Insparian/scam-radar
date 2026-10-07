import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import test from "node:test";

const workflow = readFileSync(
  new URL("../../../.github/workflows/collect.yml", import.meta.url),
  "utf8",
);
const config = readFileSync(new URL("../wrangler.toml", import.meta.url), "utf8");

test("Cloudflare owns the only collection schedule", () => {
  assert.doesNotMatch(workflow, /^  schedule:/m);
  assert.match(config, /crons = \["17 5,12,23 \* \* \*"\]/);
  assert.match(config, /workers_dev = false/);
  assert.match(config, /send_metrics = false/);
});

test("live dispatch still requires independent GitHub activation and source match", () => {
  assert.match(workflow, /inputs\.dry_run/);
  assert.match(workflow, /SCAM_RADAR_LIVE_ACTIVATION_APPROVED/);
  assert.match(workflow, /SCAM_RADAR_COLLECT_ENABLED/);
  assert.match(workflow, /SCAM_RADAR_AI_ENABLED/);
  assert.match(workflow, /test "\$REQUESTED_SOURCE_KEY" = "\$APPROVED_SOURCE_KEY"/);
  assert.doesNotMatch(config, /^\[vars\]$/m);
});
