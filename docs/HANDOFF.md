# Scam Radar implementation handoff

**As of:** 2026-09-16
**Repository:** <https://github.com/Insparian/scam-radar>  
**Branch:** `main`  
**Verified implementation baseline:** `52936a7` (`Patch vulnerable web dependencies`)

This file is the continuity note for starting a new Codex conversation. It does not
override `AGENTS.md` or [North Star](North%20Star.md); read those first.

## Current outcome

A public **fixture-only** Cloudflare Pages preview is running at
<https://preview.insparian-scam-radar.pages.dev/>. It is not the live-data product:
the site shows a test-data warning, sends `X-Robots-Tag: noindex, nofollow`, and has
no custom domain. Search is performed inside the visitor's browser and does not
transmit or retain the search text.

The repository is public and the fixture preview deploys only through the protected,
manual `Cloudflare Pages fixture preview` GitHub workflow. The workflow uploads the
prebuilt static `web/out` directory; it does not enable Cloudflare Workers, DNS, R2,
AI, analytics, or telemetry.

An empty Supabase Free production foundation now exists in Frankfurt
(`eu-central-1`). Five forward migrations are applied, one project-specific Auth user
is mapped to an enabled reviewer, and production probes confirm zero application
rows plus anon/authenticated/service-role table isolation. This provisioning does not
create a product login page: the web reviewer UI is still fixture-only and has no
production Supabase Auth client.

## Completed

- [x] V0.1 fixture pipeline, immutable release schema v2, local public search, public
  pattern pages, and reviewer UI.
- [x] Deterministic Policy Engine with `safe_to_automate`, `review_required`, and
  `blocked` routing. Human review is an exception path after the Policy Engine.
- [x] One-way confidence fail-safe: uncertain model output may force review but can
  never grant publication authority.
- [x] `safe_to_automate` architecture exists but remains in shadow mode. V0.1 still
  requires authenticated human confirmation, and the live policy allowlist is empty.
- [x] Evidence, revision verification, and release publication timestamps remain
  distinct. Public `last_verified_at` is the minimum verification time across the
  evidence supporting the current public claims.
- [x] Forward-only local migrations, grants/RLS, immutable audit records, policy and
  human provenance, and real PostgreSQL contract tests.
- [x] Public GitHub repository, branch protection/security baseline, secret scanning,
  dependency review, and protected `cloudflare-preview` environment.
- [x] Fixture-only Cloudflare Direct Upload project and guarded deployment workflow.
- [x] All six Dependabot alerts fixed. `npm audit --prefix web` reports zero known
  vulnerabilities, and GitHub reports zero open Dependabot alerts.
- [x] Replacement Cloudflare Pages token created with account-level Pages Write only,
  stored in the protected GitHub environment, and proven through a real deployment.
- [x] The exposed older Cloudflare Pages token was revoked after the replacement
  deployment passed. The Cloudflare account token list now contains only the active
  dated replacement for this deployment path.
- [x] Empty Frankfurt Supabase production foundation, five migration versions, one
  enabled reviewer, RPC-only worker/exporter boundaries, and an empty live automatic
  publication allowlist verified against the managed database.

## Verification evidence

At commit `52936a7`:

- `make check`: passed.
- `make test`: passed (86 Python/database tests and 4 Playwright browser tests).
- `make eval`: passed 100 recorded cases; all reported rates were `1.0`.
  `launch_qualified: false` is intentional because live automatic publication is not
  authorized.
- `make demo`: passed; the static artifact contained 92 files and secret scans passed.
- `npm audit --prefix web`: zero vulnerabilities.
- GitHub Offline CI run `34578382146`: passed.
- Cloudflare deployment run `34668000357`: passed end to end with the replacement
  token, including public smoke checks.
- Live fixture release ID: `fixture-2026-08-16-001`.
- 2026-09-16 local verification after the hosted Supabase hardening migration:
  `make check`, 93 Python/database tests, 4 Playwright tests, and 100 recorded eval
  cases passed; `launch_qualified: false` remains intentional.
- Live checks covered the home page, local search, suggestion buttons, result/detail
  navigation, bilingual `Last Verified / 信息核实至`, the fixture warning, and the
  `noindex, nofollow` response header.

## Credential state

- The replacement token is named
  `Insparian Scam Radar Pages Deploy 2026-09-11`.
- It is account-owned, permits Pages Write for the current Cloudflare account, allows
  GitHub-hosted runner IPs, and has no Workers, DNS, R2, AI, billing, or membership
  permission.
- `CLOUDFLARE_API_TOKEN` and `CLOUDFLARE_ACCOUNT_ID` live only in the protected
  GitHub `cloudflare-preview` environment. Never paste their values into a chat,
  document, issue, log, or repository file.
- The older token named `Insparian Scam Radar Pages Deploy` was exposed in chat and
  revoked on 2026-09-12. Do not recreate or reuse it.
- No credential is stored in the checkout.
- The protected GitHub `supabase-production` environment has all live-data switches
  false. Its encrypted `SUPABASE_DB_URL` uses the Frankfurt session pooler so
  GitHub-hosted IPv4 runners can connect, and `SUPABASE_REVIEWER_EMAIL` contains the
  private project mailbox. Neither value is present in the checkout or logs.

## External-boundary status

Only the fixture preview paths F6/F7 are active for application traffic. Package
registry access F0 is allowed, and fixture search F8 remains browser-local. F3/F4
have been provisioned only as an empty schema plus one reviewer identity and security
verification; the product does not yet connect to them. The following live scopes
remain disabled and require a fresh Decision Checkpoint plus Rui's explicit `proceed`:

- F1 real-source discovery/fetching;
- F2 Gemini/Google processing;
- F3 production Supabase writes;
- F4 production reviewer Auth/actions;
- F5 production release export;
- F9 encrypted private R2 backups;
- custom-domain/DNS activation; and
- any live `safe_to_automate` policy allowlist entry.

Provisioning a cloud resource is not permission to move real application data through
it. Keep all source entries disabled, all collection/AI/deploy kill switches off, and
`shadow_mode: true` until their separate activation conditions are met.

## Next implementation sequence

The production Supabase foundation is complete. The product login page and live Auth
client are not implemented; connecting the reviewer UI is a separate product slice
that needs its own Decision Checkpoint because it introduces a new browser-to-Supabase
data path. Real-source collection remains later and separately gated.

1. Commit and push the reviewed foundation changes, then dry-run the protected manual
   workflow against the already aligned migration ledger. Do not push automatically.
2. Decide whether to implement the production reviewer login/Auth slice now; do not
   assume that provisioning Supabase created or activated a login page.
3. Before accepting live evidence, add a forward, append-only evidence-resolution
   event migration so rejected evidence retains honest actor/policy provenance. Do
   not invent historical reviewers or timestamps.
4. Add one explicit database schema-v2 export mapping test covering every public-web
   presentation field; the live build must not depend on fixture-only copy.
5. Design and approve encrypted R2 recovery: exact outbound data, encryption before
   upload, recovery-key custody, retention, caps, and a restore rehearsal.
6. Separately review the first exact source URLs, terms/robots rules, collection caps,
   contact address, Gemini payload boundary, and call/character limits.
7. Run one capped source in shadow mode, manually inspect every row, proposal, decision,
   and log, and keep live automatic publication disabled.
8. Only after measured live performance, consider a narrowly defined automatic policy
   class through a new forward allowlist migration and separate approval.
9. Treat production publication, custom domain/DNS, mainland mobile/WeChat validation,
   and launch as later, separately approved steps.

Relevant runbooks: [initial setup](runbooks/initial-setup.md),
[deployment and rollback](runbooks/deploy-and-rollback.md),
[database recovery](runbooks/database-recovery.md), and
[key rotation](runbooks/key-rotation.md).

## Start the next conversation with this

> Read `AGENTS.md`, `docs/North Star.md`, and `docs/HANDOFF.md` completely. Verify the
> working tree, latest GitHub CI, and fixture-preview health. Continue with the first
> item in `Next implementation sequence`. Do not activate real collection, Gemini,
> production Supabase data movement, R2 backups, DNS, production publication, or live
> automatic publication without the repository's Decision Checkpoint and my explicit
> `proceed`. Do not spawn sub-agents unless I explicitly ask.

## Repository hygiene at handoff

- No sub-agents are running.
- Do not amend, force-push, or rewrite the existing commits.
- This handoff was checked after the old token was revoked. Its final documentation
  commit is intended to be pushed because Rui explicitly requested continuity across
  conversations and devices.
