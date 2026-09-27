# Deploy and rollback

## Current status

A fixture-only Cloudflare preview is active at <https://preview.insparian-scam-radar.pages.dev/> behind the manual `Cloudflare Pages fixture preview` workflow. It displays its test-data warning and sends `X-Robots-Tag: noindex, nofollow`.

A separate reviewer build is active at <https://reviewer.insparian-scam-radar-reviewer.pages.dev/> on the `reviewer` preview branch. The `Reviewer control plane` workflow refuses to upload unless the exact commit passed Offline CI and an unauthenticated preflight is redirected to Cloudflare Access; it repeats that Access probe after upload. The Pages production branch remains `production-disabled`, so this is not a public production deployment. The build contains only the public Supabase URL and publishable key, never a database URL or secret key. Cloudflare account-member Access, Supabase reviewer login, empty-queue bootstrap, sign-out, and the logged-out route guard passed an interactive production smoke test on 2026-09-17.

Public production deployment, custom domain, and rollback remain unverified and require launch approval. The dormant `deploy.yml` workflow now has a real exact-release export, credential-free build, preview and production Direct Upload, receipt reconciliation, and static smoke path. Its two external-activation switches remain off. The fixture post-upload smoke check retries only transient reachability failures during the short Pages alias propagation window; release-ID mismatch still fails immediately.

## Offline release rehearsal

1. Run the complete offline suite and build from one fixture `release_id`.
2. Confirm home, detail, local search index, and `release.json` all expose that ID; release schema v2 has `published_at` and each public pattern's `last_verified_at` equals the oldest supporting-evidence verification time.
3. Scan `web/out` for the secret sentinel and ensure no backend key or source body is present.
4. Hash the output, rerun the build, and investigate any unexplained nondeterminism.

## Production deploy — activation and launch approval only

1. Confirm deploy is enabled, the commit passed CI, schema/behavior/policy contract matches, and the exact release contains only authorized verified revisions. In V0.1, every shadow-safe revision must still have authenticated human confirmation and the database live-policy allowlist must be empty.
2. Acquire the workflow's production concurrency slot. The release RPCs serialize deployment changes with a database advisory lock and reject an ordinary older-release replacement.
3. Export the exact `release_id` in a step that alone receives the Supabase secret.
4. Build without that secret, embed release/artifact hashes, and scan the output.
5. Upload the directory as a non-production preview branch and smoke-test home, detail, search index, missing route, and release ID.
6. Recheck deployability, then upload the unchanged directory to the configured production branch. This upload is the public/irreversible point.
7. Save the Pages deployment ID and artifact hash immediately after upload, mark `deployed_unrecorded`, and smoke-test the deployment-specific Pages URL against the exact exported `release_id`, `manifest_hash`, `published_at`, search index, home, search, and one detail route. Only then register it as active in PostgreSQL. The canonical domain is checked separately after the DNS approval and change; it is not assumed to exist on the first release. If registration fails, do not say the upload failed.

The manual `deploy.yml` entry requires `SCAM_RADAR_DEPLOY_ENABLED=true` and `SCAM_RADAR_LIVE_ACTIVATION_APPROVED=true` in GitHub variables, the exact typed confirmation, the main branch, a passing Offline CI run for that commit, and approval of the `production` GitHub environment. Those settings require Rui's separate final activation decision. The Pages token is present only for upload/inspection; the Supabase service key is present only for release RPC steps. No secret is passed to the static build.

## Interrupted upload or registration

1. Stop new deploy attempts. Read the failed run's nonsecret summary and identify the exact release ID, commit SHA, artifact hash, operation ID (`run_id-run_attempt-production`), branch, and Pages deployment ID if one was returned. Do not upload the same release again.
2. If the upload result is uncertain, rebuild the same immutable release from the same commit and use `scripts/pages_upload.py inspect` with those exact fields. It only lists Pages deployments and writes a receipt under `work/`; it never uploads. A missing or ambiguous receipt is a stop condition for human investigation. The workflow performs this read-only inspection once when its upload step fails.
3. If a matching successful Pages receipt exists, run `scripts/release_rpc.py note` using that receipt and the verified artifact. This is idempotent and records `deployed_unrecorded`. Smoke-test the deployment URL with `scripts/pages_upload.py smoke` and the same immutable export. Then run `scripts/release_rpc.py record` with that exact receipt and artifact. A second invocation must return the same state, not create another receipt.
4. If public smoke fails, stop collection/AI/deploy and use the rollback path below. For a new upload that was never registered as active, restore the prior Pages deployment first, verify it, then call `scripts/release_rpc.py withdraw` with the failed release and upload IDs, expected prior active release/deployment IDs, the restored Pages receipt, prior artifact hash, and reason code `smoke_failed`. It records `upload_rolled_back` and append-only withdrawal/rollback receipts while keeping the old release active. A stale pointer or wrong hash fails. Never label an uploaded release as a pre-upload build failure.

All live commands above additionally require the same deploy activation environment variables and `SCAM_RADAR_DEPLOY_CONFIRMATION="DEPLOY APPROVED IMMUTABLE RELEASE"`; the scripts reject other origins and unapproved file destinations. Production URLs and credentials are supplied through the approved environment, never copied into command history or logs.

Reject the release if a shadow policy decision is presented as live authority, a policy/config/input hash does not match, or a live policy class was enabled without a forward migration naming its separately approved exact `policy_version + policy_hash + gate_version`.

Direct Upload and Git integration are different project types; do not enable Cloudflare Git auto-deploy. Never guess a DNS target or alter the apex site.

Cloudflare Pages Free is selected because this site is purely static: current documented limits allow 500 builds per month and static asset requests are free. Recheck these terms immediately before activation, set usage notifications where available, and do not enable an automatic paid fallback. Repository ownership may be personal or organizational; the deployment workflow, not a Git-host integration, remains the only publication authority.

The fixture and reviewer previews use Direct Upload, so their builds run in GitHub Actions rather than Cloudflare's Pages build service. They use two of the account's current Pages project slots. With no Pages Functions, their static requests do not count against the account's Workers request allowance. The Pages Write token is still account-scoped and can affect other Pages projects in that account, so it must have no Workers, DNS, R2, billing, or membership permissions and must remain scoped to the `cloudflare-preview` GitHub environment.

## Reviewer preview rollback

1. Treat Access failure as a stop condition: do not upload if the unauthenticated probe does not redirect to the expected Cloudflare Access host.
2. To stop the browser control plane without changing the database, disable the reviewer Pages deployment or remove its public Supabase build variables, then verify the URL no longer serves the configured reviewer app.
3. To revoke decision authority immediately, disable the matching `admin_users` row and revoke the Auth session. This preserves audit history.
4. Do not reverse migration `20260916000200`; fix database behavior with a new forward migration.
5. Do not repoint the Pages production branch, add custom DNS, or copy reviewer configuration into the public fixture project as a rollback shortcut.

## Rollback

- **Static site:** identify the previously verified production Pages deployment ID, immutable release ID, artifact hash, and the currently active deployment ID from the append-only receipt history. Use `scripts/pages_upload.py rollback` only with the separate exact rollback confirmation. It checks the current Pages pointer and target's original release/hash marker, then asks Pages to restore that original artifact; it never rebuilds mutable data or force-pushes Git. Smoke-test the returned target deployment URL and, once DNS exists, the canonical domain against the prior immutable release export. If the failed release was already recorded as active, finish with `scripts/release_rpc.py rollback`; if it was only `deployed_unrecorded`, finish with `scripts/release_rpc.py withdraw`. Both require the new rollback receipt, expected prior active release/deployment IDs, target artifact hash, and a redacted reason code. A stale pointer refuses the database change. If the Pages API result is uncertain, inspect the current Pages pointer before any retry. Do not reverse the database pointer first.
- **Bad content:** create an authenticated unpublish/correction release; do not edit an old release manifest.
- **Worker:** pause collection/AI, make a forward code fix, run offline tests, then resume gradually.
- **Prompt/model/scoring/policy:** restore the prior versioned behavior selection, disable live policy authorization first, and rerun evals before use. Do not rewrite an existing policy decision.
- **Database:** follow [database recovery](database-recovery.md); prefer a forward migration.

Record failed and replacement deployment IDs, who authorized the action, timestamps, reason, and final live `release_id`. Before declaring launch healthy, include mainland mobile and WeChat-path checks; no performance result is claimed until measured.
