const dispatchUrl =
  "https://api.github.com/repos/Insparian/scam-radar/actions/workflows/collect.yml/dispatches";
const sourceKeyPattern = /^[a-z0-9][a-z0-9-]{0,79}$/;

export async function dispatchCollection(env, fetcher = fetch) {
  if (env.SCAM_RADAR_SCHEDULER_ENABLED !== "true") {
    return "disabled";
  }

  const sourceKey = env.SCAM_RADAR_SOURCE_KEY;
  if (
    typeof sourceKey !== "string" ||
    !sourceKeyPattern.test(sourceKey) ||
    sourceKey === "all"
  ) {
    throw new Error("approved_source_key_required");
  }
  const token = env.GITHUB_ACTIONS_TOKEN;
  if (typeof token !== "string" || token.length < 10 || /\s/.test(token)) {
    throw new Error("github_actions_token_required");
  }

  const response = await fetcher(dispatchUrl, {
    method: "POST",
    redirect: "error",
    signal: AbortSignal.timeout(10000),
    headers: {
      Accept: "application/vnd.github+json",
      Authorization: `Bearer ${token}`,
      "Content-Type": "application/json",
      "User-Agent": "insparian-scam-radar-scheduler",
      "X-GitHub-Api-Version": "2026-03-10",
    },
    body: JSON.stringify({
      ref: "main",
      inputs: { source_key: sourceKey, dry_run: "false" },
    }),
  });

  if (response.status !== 200 && response.status !== 204) {
    throw new Error(`github_dispatch_rejected_${response.status}`);
  }
  return "accepted";
}

export default {
  async scheduled(_controller, env, _ctx) {
    const outcome = await dispatchCollection(env);
    console.log(`scheduler_${outcome}`);
  },
};
