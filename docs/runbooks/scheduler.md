# Collection scheduler

Decision [014](../../DECISIONS/014-free-cloudflare-scheduler.md) moves the collection clock to Cloudflare Workers Free. The Worker only dispatches the existing GitHub `collect.yml`; it does not fetch sources, call a model, read Supabase, or publish. GitHub retains the one-source and activation gates. This runbook does not authorize deployment or live collection.

## Offline contract

- Source/config/tests: `cloudflare/scheduler/src/`, `wrangler.toml`, and `test/`.
- `make check` checks Worker syntax; `make test` runs dependency-free Node tests.
- One UTC cron (`17 5,12,23 * * *`) corresponds to 07:17, 13:17, and 20:17 Beijing time. The GitHub workflow has `workflow_dispatch` only, avoiding GitHub's public-repository 60-day scheduled-workflow inactivity rule.
- The Worker has no public HTTP route (`workers_dev = false`) and no committed live bindings. Missing or non-`true` `SCAM_RADAR_SCHEDULER_ENABLED` returns before any request.
- Enabled dispatch accepts one lowercase source key, never `all`, and sends `ref=main`, that key, and `dry_run=false` to one fixed GitHub API URL. It does not follow redirects or print the token/response body.

## Activation values and data flow

All cloud steps below need separate final activation approval. First verify the Cloudflare account is on **Workers Free**, the Cron limit is available, and no paid Workers plan is being selected. Deploy only this Worker from the reviewed commit; `wrangler.toml` starts it inert and disables Wrangler usage telemetry. Note that `wrangler secret put` creates a new Worker deployment immediately, so treat each secret change as an activation action.

| Location | Value | Purpose |
| --- | --- | --- |
| Cloudflare Worker secret | `GITHUB_ACTIONS_TOKEN` | Fine-grained GitHub token for `Insparian/scam-radar`, repository **Actions: write** only; dispatches `collect.yml` |
| Cloudflare Worker secret | `SCAM_RADAR_SOURCE_KEY` | Exact reviewed key, identical to GitHub `SCAM_RADAR_APPROVED_SOURCE_KEY`; using a secret preserves it across later Wrangler deploys |
| Cloudflare Worker secret | `SCAM_RADAR_SCHEDULER_ENABLED` | Exact `true` only after the full live-collection checkpoint; absent/false stops dispatch |
| GitHub repository Variables/Secrets | Existing collection values in [initial setup](initial-setup.md) | GitHub job independently checks activation, source, service/model credentials, and batch caps |

When enabled, Cloudflare sends one HTTPS POST per scheduled time to `api.github.com`: repository path, `main`, source key, `dry_run=false`, a GitHub token in the Authorization header, and ordinary request metadata. No source text, model output, Supabase key, review content, or search query passes through the Worker. GitHub may return a run ID/URL; the Worker only checks HTTP status. Token scope permits other Actions write operations on this one repository, so keep its lifetime short and rotate before expiry. Do not store it in Git or root `.env` for this Worker.

## First live check and stop

1. After source license/robots, model free-only balance, backup/recovery, production database, and separate collection approval are satisfied, set the matching GitHub source/activation values; leave Worker `ENABLED` absent while validating them.
2. Configure the exact source key and token in Cloudflare. Set `ENABLED=true` last, only with Rui's final scheduler activation confirmation. Run one scheduled dispatch and confirm the GitHub run completed, the one approved source was used, the model stayed within the free-only account cap, and the Supabase cursor/audit counts agree. A `200` dispatch response alone proves only acceptance, not a successful batch.
3. Observe at least seven days of scheduled runs, missed-run windows, source/model failures, reviewer burden, and token expiry. Until an independent missed-run alert exists and is tested, check both Cloudflare Cron Events and GitHub runs daily; do not claim silent-failure detection is complete.
4. Stop dispatch by changing Worker `ENABLED` away from `true` or revoking its token. Also set GitHub `SCAM_RADAR_COLLECT_ENABLED=false` as the independent kill switch. A queued dispatch then fails before source contact.

[Cloudflare Cron docs](https://developers.cloudflare.com/workers/configuration/cron-triggers/) describe UTC scheduling and propagation; [Workers Free limits](https://developers.cloudflare.com/workers/platform/limits/) list Cron capacity. [GitHub dispatch API](https://docs.github.com/en/rest/actions/workflows#create-a-workflow-dispatch-event) requires a fine-grained token with repository Actions write permission. [Cloudflare secrets docs](https://developers.cloudflare.com/workers/configuration/secrets/) explain secret deployment behavior.
