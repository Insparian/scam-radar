# Initial setup

## Purpose

Get a fresh checkout to a verified offline fixture state. This runbook does **not** activate collection, a live model, production Supabase, Cloudflare, or DNS. Decision 015's [dedicated Cloudflare Free account](dedicated-cloudflare-account.md) is now created, and its reviewed ID is recorded in `config/cloudflare-account.json`. Matching that ID is necessary for Pages, KV, and Worker writes, but does not authorize them; their separate activation gates remain closed.

## Offline setup — allowed now

1. Read root `AGENTS.md`; confirm `.env` is ignored by Git and no tracked file contains a real secret.
2. Install Node.js, Python, `uv`, npm, and `make` using versions pinned by the repository.
3. Run:

   ```bash
   make bootstrap
   make check
   make test
   make eval
   make demo
   make open-source-audit
   ```

4. Start `make web` and check the fixture home, one search, one detail page, a missing route, large-text mobile layout, visible keyboard focus, public “信息核实至”, and that `/admin/login/` visibly fails closed when the public Supabase configuration is absent.
5. Confirm `config/sources.yaml` keeps every source `enabled: false`, `config/publication-policy-v0.1.yaml` keeps `shadow_mode: true` and `live_auto_publish_enabled: false`, and `.env.example` contains only fake/disabled values.
6. Record command results and failures. Do not describe a real service as tested.

Package installation may reach approved official registries. Application tests must use fixtures/localhost only.

The private reviewer UI initializes Supabase only under `/admin`. A later approved
reviewer deployment must provide `NEXT_PUBLIC_SUPABASE_URL` and
`NEXT_PUBLIC_SUPABASE_PUBLISHABLE_KEY` at build time. Both values are visible in the
compiled site and grant no authority by themselves. Never place a secret/service key,
database URL, reviewer email, or password in a `NEXT_PUBLIC_` variable. Omit either
public value to make the admin surface fail closed without a network request.

The ignored local `.env` is only for local runs; it does not populate GitHub Actions.
Fill GitHub variables and encrypted secrets only for the approved stage. Collection
has no protected GitHub environment, so its values must be repository-level;
keep its activation switches off until Rui approves that live path.

| Stage and GitHub location | Variables | Encrypted secrets |
| --- | --- | --- |
| Production database foundation — `supabase-production` environment | None | `SUPABASE_DB_URL`, `SUPABASE_REVIEWER_EMAIL` |
| Public fixture preview — `cloudflare-preview` environment | `SCAM_RADAR_PUBLIC_PAGES_PROJECT`, `SCAM_RADAR_PUBLIC_PREVIEW_URL` from the dedicated account's actual Pages project and branch alias | `CLOUDFLARE_ACCOUNT_ID`, `CLOUDFLARE_API_TOKEN` |
| Protected reviewer — `cloudflare-preview` environment | `SCAM_RADAR_REVIEWER_PAGES_PROJECT`, `SCAM_RADAR_REVIEWER_PREVIEW_URL` from the dedicated account's actual Pages project and branch alias; `SCAM_RADAR_REVIEWER_ACCESS_HOST` from the dedicated account's Zero Trust team domain; `NEXT_PUBLIC_SUPABASE_URL`, `NEXT_PUBLIC_SUPABASE_PUBLISHABLE_KEY`, `REVIEWER_ACCESS_READY` after Access verification | `CLOUDFLARE_ACCOUNT_ID`, `CLOUDFLARE_API_TOKEN` |
| One-source collection — repository level | `SCAM_RADAR_SUPABASE_URL`, `SCAM_RADAR_APPROVED_SOURCE_KEY` | `SCAM_RADAR_SUPABASE_SERVICE_KEY`, `SCAM_RADAR_MODEL_API_KEY` |
| Encrypted backup — `production-backup` environment | `SCAM_RADAR_AGE_RECIPIENT`, `SCAM_RADAR_BACKUP_PGHOST`, `SCAM_RADAR_BACKUP_PGUSER`, `SCAM_RADAR_KV_ACCOUNT_ID`, `SCAM_RADAR_KV_NAMESPACE_ID` | `SCAM_RADAR_BACKUP_PGPASSWORD`, `SCAM_RADAR_SUPABASE_CA_PEM`, `SCAM_RADAR_KV_TOKEN` |
| Immutable public release — `production` environment | `SCAM_RADAR_SUPABASE_URL`, `SCAM_RADAR_PAGES_PROJECT`, `SCAM_RADAR_PAGES_PRODUCTION_BRANCH` | `SCAM_RADAR_SUPABASE_SERVICE_KEY`, `CLOUDFLARE_ACCOUNT_ID`, `CLOUDFLARE_PAGES_TOKEN` |

The local model evaluation uses `SCAM_RADAR_EVAL_API_KEY` in `.env`; it is not a
GitHub Actions secret. The Beijing worker credential goes in the separate
`SCAM_RADAR_MODEL_API_KEY` GitHub secret for an approved live run; it may be a
different key. Leave every `SCAM_RADAR_*_ENABLED`,
`SCAM_RADAR_LIVE_ACTIVATION_APPROVED`, and `SCAM_RADAR_LIVE_EVAL_APPROVED` variable
unset or `false` until the corresponding activation is approved. The backup and
deployment workflows also require their own exact confirmation values after
approval. Do not fill an unapproved KV namespace or publishable key with an invented
value.

Choose the reviewer project name before the separately approved empty-project
creation; then verify its name and actual `pages.dev` subdomain in Cloudflare.
The public project name likewise must be verified after its approved creation.
A taken name may receive a different subdomain. Set the full branch aliases
(for example, `https://preview.<actual-subdomain>.pages.dev`) in
`cloudflare-preview`; the workflows reject the shared account's old preview
URLs. Do not run either preview deployment until its target and, for the reviewer,
Access policy are reviewed. Set `SCAM_RADAR_REVIEWER_ACCESS_HOST` to the exact
hostname of the dedicated account's Access login (for example,
`scam-radar.cloudflareaccess.com`, without a scheme or path); the reviewer
pre/post-upload probes reject a redirect to any other Zero Trust team.

## Real local database contract — optional

This check uses disposable local containers and synthetic `.invalid` data only. It does
not connect to a Supabase account or production project.

1. Start a Docker-compatible engine. On macOS, the reviewed default is Rancher Desktop
   with Moby selected and Kubernetes, telemetry, and automatic updates disabled.
2. Start the local stack from the repository root:

   ```bash
   npx --yes supabase@2.115.0 start
   ```

3. Exercise the real PostgreSQL grants, policy routes, Publish Gate, timestamps,
   and immutable release controls:

   ```bash
   make database-test
   ```

4. Stop and discard the synthetic database:

   ```bash
   npx --yes supabase@2.115.0 stop --no-backup
   ```

If macOS blocks container mounts under `Documents`, copy only `supabase/` to a
disposable directory under `/private/tmp`, start the stack there, and set
`SUPABASE_DB_CONTAINER` to that stack's database container name. Do not grant broad
filesystem access merely to run this check.

## External activation — each path requires separate Rui approval

Before creating, linking, or enabling a cloud resource, show Rui that resource's exact outbound data, destination, purpose, caps, credentials, stop control, and user impact. Approving one path does not approve another.

Before complete live-system activation, also show Rui:

- exact outbound flows from `docs/data-flow.md`;
- the first exact source URL and its terms/robots/policy review;
- Supabase region choices and data-location implications;
- reviewer email and collection contact email;
- the selected Beijing Qwen model and database call/item/character caps;
- required GitHub secrets/variables;
- the dedicated Cloudflare Free account and account-level Pages/KV token scope; and
- KV's encrypted-backup data path, recovery-key custody, retention, and restore test; and
- confirmation that collection, AI, deploy, and live policy authorization switches start `false`.

Only after approval:

1. Reuse the verified Supabase project. The existing Frankfurt Supabase project was restored with Rui's separate authorization on 2026-10-07 and showed Healthy. Existing Pages previews are in a shared Cloudflare account; do not deploy there again. The dedicated Free account is created, but new Pages projects still require separate approval, following [account isolation](dedicated-cloudflare-account.md). R2 requires a subscription that may incur charges and is not selected; the proposed KV backup remains off until its [retention and recovery gates](kv-backup.md) pass.
2. Store secrets in GitHub Encrypted Secrets, never repository files or workflow scope.
3. Create the first reviewer in Supabase Auth through the Dashboard so the reviewer
   sets their own password; do not add an SMTP service merely for this bootstrap.
   Configure the protected `supabase-production` GitHub environment with the
   project-scoped `SUPABASE_DB_URL`, and keep the reviewer mailbox only in
   `SUPABASE_REVIEWER_EMAIL`. Run the manual production-foundation workflow with its
   exact confirmation to apply migrations and authorize that existing Auth user in
   `admin_users`. Do not put the reviewer address in a workflow input, log, issue, or
   repository file. As of 2026-10-07 the project has only the first 7 of 22 migrations;
   the evidence-resolution event migration is already applied. Before running the
   foundation workflow, compare exact production and repository migration versions.
   The workflow's read-only preflight checks the applied versions form the exact
   repository prefix and that application tables are empty. It also counts old
   irrelevant rows with retained text. These results travel from Supabase to a
   GitHub Actions job using the `supabase-production` environment; the log prints
   only zero or a failure reason, never row
   contents. This new preflight data flow remains dormant until Rui separately
   approves the production foundation workflow.
   Migration `20260920000600_irrelevant_text_retention.sql` clears old `clean_text`
   wherever `processing_status = 'irrelevant'`. If any application data or retained
   irrelevant text exists, this foundation workflow stops before `db push` even with
   its normal confirmation. A separately reviewed migration plan must first inspect
   the affected count, verify a backup in a separate recovery database, and obtain
   Rui's exact confirmation for the irreversible data change. No real backup
   destination is approved under the current free-only constraint, so this step
   remains blocked.
4. Prove anon/reviewer/worker/exporter boundaries, append-only policy decisions, distinct policy/human provenance, shadow-decision rejection, and an empty exact-policy activation allowlist with production-safe checks.
5. Confirm the existing database v2 public-export mapping still covers every required public-web presentation field on the exact approved release; do not activate a build that still depends on fixture-only copy.
6. Keep collection, AI, backup, and deploy kill switches off.
7. Run one approved source with strict caps; inspect every row/proposal/log manually.
8. Expand sources and schedules only after the one-source run passes. Keep live automatic authorization off while gathering shadow false-auto and exception-capture measurements.

Provisioning is not permission to crawl, call Qwen, deploy, or change DNS.

## Stop conditions

Stop and ask Rui before any paid plan, new outbound data path, production write not described above, backup retention/deletion policy, destructive migration, public upload, DNS edit, wider credential scope, or a forward migration adding an exact policy/gate tuple to the live `safe_to_automate` allowlist.
