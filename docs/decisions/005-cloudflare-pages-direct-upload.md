# ADR-005: Cloudflare Pages Direct Upload from trusted CI

- **Status:** Accepted for design; provisioning/deployment not approved
- **Date:** 2026-08-16

## Decision

After activation, create a **Direct Upload** Pages project and upload prebuilt `web/out` assets from a trusted GitHub Actions workflow with pinned Wrangler. Do not connect Cloudflare Git auto-deploy and do not add Pages Functions or `_worker.js`.

The deploy workflow exports one exact approved release, builds and hashes it once, scans it, uploads that same directory to a preview branch, smoke-tests it, then uploads the unchanged directory to the configured production branch. A production upload is already public; a later database bookkeeping failure becomes `deployed_unrecorded` and is reconciled from the live `release.json`.

## Why

Only the repository workflow has enough context to prove CI status, schema/behavior compatibility, release approval, secret absence, and same-artifact preview/production. Cloudflare receives only compiled static assets and never receives the database or Gemini key.

## Alternatives

- **Pages Git integration:** convenient previews, but creates a second deployment authority and cannot enforce the trusted release export/approval sequence as directly. Cloudflare documents that choosing Git integration or Direct Upload is not switchable on the same project.
- **Cloudflare Workers:** supports full-stack Next.js, but no request-time runtime is needed.
- **Manual drag-and-drop:** simple first upload, but weak reproducibility, audit, smoke, and rollback guarantees.

## Credential constraint discovered during review

Cloudflare's current documented token model supports restricting a token to one **account** and the **Cloudflare Pages Write/Edit** permission. Token resources are User, Account, and Zone; there is no documented per-Pages-project resource scope. Therefore “project-scoped token” cannot be treated as an enforceable platform guarantee.

At activation, use an account-owned or user token limited to the single intended account and Pages permission only, never a Global API Key. If that account contains unrelated Pages projects and true blast-radius isolation is required, create the Scam Radar Pages project in a dedicated Cloudflare account or explicitly accept the account-level scope. Optional token TTL/IP restrictions should be considered if compatible with GitHub-hosted runners. This question does not block offline implementation.

## Consequences and checks

- Project creation must deliberately select Direct Upload and set the production branch; switching integration later requires a new Pages project.
- `SCAM_RADAR_DEPLOY_ENABLED=false` blocks uploads before launch.
- Preview uses a non-production `--branch`; production uses the configured production branch.
- Deployment credentials exist only in the upload step. Build and tests receive none.
- File-count/size limits and mainland-network performance must be checked before launch.

## Sources

- [Cloudflare Pages Direct Upload](https://developers.cloudflare.com/pages/get-started/direct-upload/)
- [Direct Upload from continuous integration](https://developers.cloudflare.com/pages/how-to/use-direct-upload-with-continuous-integration/)
- [Cloudflare API token resources](https://developers.cloudflare.com/fundamentals/api/how-to/create-via-api/)
- [Cloudflare Pages static Next.js guide](https://developers.cloudflare.com/pages/framework-guides/nextjs/deploy-a-static-nextjs-site/)
