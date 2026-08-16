# Deploy and rollback

## Current status

Only local static builds and fixture smoke checks are approved now. No Cloudflare project, preview, production deployment, custom domain, or rollback has been verified by this repository.

## Offline release rehearsal

1. Run the complete offline suite and build from one fixture `release_id`.
2. Confirm home, detail, local search index, and `release.json` all expose that ID.
3. Scan `web/out` for the secret sentinel and ensure no backend key or source body is present.
4. Hash the output, rerun the build, and investigate any unexplained nondeterminism.

## Production deploy — activation and launch approval only

1. Confirm deploy is enabled, the commit passed CI, schema/behavior contract matches, and the exact release contains only authenticated approvals.
2. Acquire production deploy concurrency and database lease. Reject an older release replacing a newer live release.
3. Export the exact `release_id` in a step that alone receives the Supabase secret.
4. Build without that secret, embed release/artifact hashes, and scan the output.
5. Upload the directory as a non-production preview branch and smoke-test home, detail, search index, missing route, and release ID.
6. Recheck deployability, then upload the unchanged directory to the configured production branch. This upload is the public/irreversible point.
7. Verify the canonical domain and record the deployment ID. If recording fails, mark/reconcile `deployed_unrecorded`; do not say it was not deployed.

Direct Upload and Git integration are different project types; do not enable Cloudflare Git auto-deploy. Never guess a DNS target or alter the apex site.

## Rollback

- **Static site:** redeploy the last tested artifact and verify its embedded release/artifact hashes. Do not rebuild “equivalent” mutable data and do not force-push Git.
- **Bad content:** create an authenticated unpublish/correction release; do not edit an old release manifest.
- **Worker:** pause collection/AI, make a forward code fix, run offline tests, then resume gradually.
- **Prompt/model/scoring:** restore the prior versioned behavior selection and rerun evals before use.
- **Database:** follow [database recovery](database-recovery.md); prefer a forward migration.

Record failed and replacement deployment IDs, who authorized the action, timestamps, reason, and final live `release_id`. Before declaring launch healthy, include mainland mobile and WeChat-path checks; no performance result is claimed until measured.
