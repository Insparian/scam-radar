# Initial setup

## Purpose

Get a fresh checkout to a verified offline fixture state. This runbook does **not** activate collection, Gemini, production Supabase, Cloudflare, or DNS.

## Offline setup — allowed now

1. Read root `AGENTS.md` and confirm the checkout contains no real `.env` file or secret.
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

4. Start `make web` and check the fixture home, one search, one detail page, a missing route, large-text mobile layout, visible keyboard focus, public “信息核实至”, and the admin Policy Engine route/reason display.
5. Confirm `config/sources.yaml` keeps every source `enabled: false`, `config/publication-policy-v0.1.yaml` keeps `shadow_mode: true` and `live_auto_publish_enabled: false`, and `.env.example` contains only fake/disabled values.
6. Record command results and failures. Do not describe a real service as tested.

Package installation may reach approved official registries. Application tests must use fixtures/localhost only.

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
- first five exact source URLs and their terms/robots/policy review;
- Supabase region choices and data-location implications;
- reviewer email and collection contact email;
- Gemini and database call/item/character caps;
- required GitHub secrets/variables;
- Cloudflare's account-level Pages token scope; and
- R2's encrypted-backup data path, recovery-key custody, retention, and restore test; and
- confirmation that collection, AI, deploy, and live policy authorization switches start `false`.

Only after approval:

1. Create/link the approved GitHub, Supabase, Gemini, private R2 bucket, and Direct Upload Pages projects.
2. Store secrets in GitHub Encrypted Secrets, never repository files or workflow scope.
3. Apply migrations through the protected manual workflow and bootstrap one reviewer.
4. Prove anon/reviewer/worker/exporter boundaries, append-only policy decisions, distinct policy/human provenance, shadow-decision rejection, and an empty exact-policy activation allowlist with production-safe checks.
5. Before accepting live evidence, add the forward append-only evidence-resolution event migration so rejected evidence retains honest actor/policy provenance; never invent a historical reviewer or timestamp.
6. Contract-test one explicit mapping from the database v2 export to every required public-web presentation field; do not activate a build that still depends on fixture-only copy.
7. Keep collection, AI, backup, and deploy kill switches off.
8. Run one approved source with strict caps; inspect every row/proposal/log manually.
9. Expand sources and schedules only after the one-source run passes. Keep live automatic authorization off while gathering shadow false-auto and exception-capture measurements.

Provisioning is not permission to crawl, call Gemini, deploy, or change DNS.

## Stop conditions

Stop and ask Rui before any paid plan, new outbound data path, production write not described above, backup retention/deletion policy, destructive migration, public upload, DNS edit, wider credential scope, or a forward migration adding an exact policy/gate tuple to the live `safe_to_automate` allowlist.
