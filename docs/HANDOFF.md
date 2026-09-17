# Scam Radar implementation handoff

**As of:** 2026-09-17
**Repository:** <https://github.com/Insparian/scam-radar>  
**Branch:** `main`  
**Verified implementation baseline:** `9054d2e` (`Preserve evidence resolution provenance`)

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

An empty Supabase Free production foundation exists in Frankfurt (`eu-central-1`).
All six forward migrations are applied there, one project-specific Auth user is mapped
to an enabled reviewer, and production probes confirm zero application rows plus
anon/authenticated/service-role table isolation.

The seventh forward migration is implemented and locally verified. It adds an
append-only event for every accepted or rejected evidence transition, including honest
human/policy provenance and migration-only `legacy_unknown` handling. It has **not**
been applied to production; the managed database remains on six migrations until Rui
separately approves that production mutation.

The approved reviewer login/Auth implementation is deployed separately at
<https://reviewer.insparian-scam-radar-reviewer.pages.dev/>. Cloudflare Access blocks
unauthenticated requests before Pages serves the app, then Supabase Auth and narrow
RPCs enforce reviewer authority. The build is only on the `reviewer` preview branch;
the Pages production branch remains `production-disabled`. The public fixture preview
is unchanged and does not initialize Supabase. Cloudflare account-member Access,
Supabase reviewer login, empty-queue bootstrap, sign-out, and the logged-out route
guard have all passed the production smoke test.

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
- [x] Append-only evidence-resolution provenance for accepted and rejected evidence,
  written atomically with the state change. Existing terminal rows are represented as
  `legacy_unknown` without invented actors or timestamps.
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
- [x] Empty Frankfurt Supabase production foundation, six migration versions, one
  enabled reviewer, RPC-only worker/exporter boundaries, and an empty live automatic
  publication allowlist verified against the managed database and through the
  protected manual GitHub workflow.
- [x] Private reviewer Auth implementation: password sign-in, session/role guard,
  live queue bootstrap, explicit per-evidence decisions, and approve/reject/hold via
  narrow RPCs. Missing public configuration fails closed without a network request.
- [x] Reviewer bootstrap excludes raw clean text, evidence spans, and candidate
  payloads. Public entry chunks are checked so they do not directly load the Auth or
  reviewer client.
- [x] Dedicated Direct Upload reviewer Pages project with a deliberately unusable
  production branch and a manual, exact-confirmation deployment workflow.
- [x] Cloudflare Access restriction on preview deployments. The workflow probes the
  Access redirect before and after every reviewer upload.
- [x] Public Supabase URL and publishable key stored only as protected GitHub
  environment values and compiled only into the private reviewer build. No database
  URL, secret key, reviewer email, or password enters the artifact.

## Verification evidence

Earlier verified baseline at commit `52936a7`:

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
- 2026-09-16 local verification after the hosted Supabase hardening migration and
  reviewer-bootstrap parser fix: `make check`, 94 Python/database tests, 4 Playwright
  tests, and 100 recorded eval cases passed; `launch_qualified: false` remains
  intentional.
- GitHub Offline CI run `35068549771`: application and from-zero PostgreSQL contracts
  passed on commit `4fb2b7f`.
- Protected Production Supabase foundation run `35068787852`: migration preview/apply,
  reviewer authorization, and production role-boundary verification all passed.
- GitHub Offline CI run `35069048522`: final application and from-zero PostgreSQL
  contracts passed on documentation commit `6701ce4`.
- Live checks covered the home page, local search, suggestion buttons, result/detail
  navigation, bilingual `Last Verified / 信息核实至`, the fixture warning, and the
  `noindex, nofollow` response header.
- Reviewer Auth implementation at `90a7563`: `make check` passed with 22 web unit
  tests; `make test` passed 95 Python/database tests and 4 Playwright tests; the eval
  suite passed all 100 recorded cases; `make demo` and the static-artifact boundary
  check passed; `npm audit --prefix web` reported zero vulnerabilities.
- The sixth migration was rebuilt from zero and exercised against a real local
  PostgreSQL/Supabase stack; the reviewer RPC grant, payload, policy, evidence, and
  publication boundaries passed.
- GitHub Offline CI run `35100601267`: both the application contract and the from-zero
  PostgreSQL contract passed on commit `90a7563`.
- Post-push fixture check on 2026-09-16: HTTP 200, `X-Robots-Tag: noindex,
  nofollow`, and release ID `fixture-2026-08-16-001`; the Auth implementation push did
  not deploy or alter the fixture preview.
- Reviewer activation preparation at `fe14468`: `make check` passed; `make test`
  passed 100 Python/database tests, 22 web unit tests, and 4 Playwright tests; all 100
  recorded eval cases passed. GitHub Offline CI run `35176507843` passed both the
  application and from-zero PostgreSQL contracts.
- Protected Production Supabase run `35176908483` applied migration
  `20260916000200`, reauthorized the reviewer identity, and passed the production
  role/RPC boundary probes with zero application rows and an empty live-policy
  allowlist.
- Reviewer project provision run `35177105741` created the empty Direct Upload Pages
  project with `production-disabled` as its production branch.
- Reviewer deployment run `35183748991` built commit `fe14468`, uploaded 99 files only
  to the `reviewer` preview branch, and passed unauthenticated Cloudflare Access probes
  both before and after upload. A separate local probe also passed after completion.
- The first reviewer build used a stale/invalid publishable key. The protected GitHub
  variable was corrected to the current public key; a fake-credential probe then
  reached Auth and returned the expected `invalid_credentials` failure. Redeploy run
  `35187327856` passed all build, offline-boundary, upload, and Access checks.
- The 2026-09-17 interactive production smoke passed: the reviewer identity loaded an
  empty `0 OPEN` queue, sign-out cleared the Supabase session, and a logged-out direct
  queue visit returned to the login page. No real evidence or review decision changed.
- Evidence-resolution implementation `9054d2e`: `make check`, 100 Python/database
  tests, 22 web unit tests, 4 Playwright tests, all 100 recorded eval cases, and the
  fixture static build passed. A real from-zero local Supabase/PostgreSQL stack applied
  all seven migrations and passed human accepted/rejected provenance, live-policy
  accepted/rejected provenance, append-only enforcement, and role/RPC boundaries.

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
- The protected `cloudflare-preview` environment stores the public Supabase URL and
  current publishable key for reviewer builds. Cloudflare preview Access uses account
  membership as the outer identity; it does not require the Supabase reviewer mailbox
  to receive Cloudflare one-time codes.

## External-boundary status

The fixture preview paths F6/F7 remain active for public application traffic. Package
registry access F0 is allowed, and fixture search F8 remains browser-local. F3 remains
an empty six-migration production schema plus one reviewer identity; the seventh
migration is verified locally but not applied there. The F4 reviewer control
plane is active only on the Access-protected preview; its unauthenticated boundary is
verified and its authenticated end-to-end smoke test passed. The following live scopes
remain disabled and require a fresh Decision Checkpoint plus Rui's explicit `proceed`:

- F1 real-source discovery/fetching;
- F2 Gemini/Google processing;
- F3 real evidence/application writes beyond the approved empty reviewer control-plane
  checks;
- F5 production release export;
- F9 encrypted private R2 backups;
- custom-domain/DNS activation; and
- any live `safe_to_automate` policy allowlist entry.

Provisioning a cloud resource is not permission to move real application data through
it. Keep all source entries disabled, all collection/AI/deploy kill switches off, and
`shadow_mode: true` until their separate activation conditions are met.

## Next implementation sequence

The reviewer control plane is deployed behind Access, while real-source collection
remains later and separately gated.

1. With a fresh explicit production-mutation approval, apply the verified seventh
   `evidence_resolution_events` migration through the protected Supabase workflow and
   confirm the managed project remains empty with all role/RPC boundaries intact.
2. Add one explicit database schema-v2 export mapping test covering every public-web
   presentation field; the live build must not depend on fixture-only copy.
3. Design and approve encrypted R2 recovery: exact outbound data, encryption before
   upload, recovery-key custody, retention, caps, and a restore rehearsal.
4. Separately review the first exact source URLs, terms/robots rules, collection caps,
   contact address, Gemini payload boundary, and call/character limits.
5. Run one capped source in shadow mode, manually inspect every row, proposal, decision,
   and log, and keep live automatic publication disabled.
6. Only after measured live performance, consider a narrowly defined automatic policy
   class through a new forward allowlist migration and separate approval.
7. Treat production publication, custom domain/DNS, mainland mobile/WeChat validation,
   and launch as later, separately approved steps.

Relevant runbooks: [initial setup](runbooks/initial-setup.md),
[deployment and rollback](runbooks/deploy-and-rollback.md),
[database recovery](runbooks/database-recovery.md), and
[key rotation](runbooks/key-rotation.md).

## Start the next conversation with this

> Read `AGENTS.md`, `docs/North Star.md`, and `docs/HANDOFF.md` completely. Verify the
> working tree, latest GitHub CI, fixture-preview health, and the protected reviewer
> preview. Continue with the first item in `Next implementation sequence`. The sixth
> production migration and Access-protected reviewer branch preview are active; the
> seventh evidence-resolution migration is locally verified but not applied to
> production. The Access + Supabase login/empty-queue/sign-out/route-guard smoke test
> passed. Do not activate real collection, Gemini, production Supabase data movement,
> R2 backups, DNS, production publication, or live
> automatic publication without the repository's Decision Checkpoint and my explicit
> `proceed`. Do not spawn sub-agents unless I explicitly ask.

## Repository hygiene at handoff

- No sub-agents are running.
- Do not amend, force-push, or rewrite the existing commits.
- The working tree should be clean and `main` should match `origin/main`; verify rather
  than assume this in the next conversation.
- `AGENTS.md` records Rui's standing authorization to commit and push complete,
  verified, secret-free change sets for this open-source repository. Production data
  mutations, deployments, releases, DNS changes, force pushes, and history rewrites
  retain their separate confirmation gates.
