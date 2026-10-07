const dispatchUrl =
  "https://api.github.com/repos/Insparian/scam-radar/actions/workflows/backup.yml/dispatches";

export async function dispatchBackup(env, fetcher = fetch) {
  if (env.SCAM_RADAR_BACKUP_SCHEDULER_ENABLED !== "true") {
    return "disabled";
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
      "User-Agent": "insparian-scam-radar-backup-scheduler",
      "X-GitHub-Api-Version": "2026-03-10",
    },
    body: JSON.stringify({ ref: "main", inputs: { scheduled: "true" } }),
  });
  if (response.status !== 200 && response.status !== 204) {
    throw new Error(`github_dispatch_rejected_${response.status}`);
  }
  return "accepted";
}

export default {
  async scheduled(_controller, env, _ctx) {
    const outcome = await dispatchBackup(env);
    console.log(`backup_scheduler_${outcome}`);
  },
};
