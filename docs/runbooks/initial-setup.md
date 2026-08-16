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
   ```

4. Start `make web` and check the fixture home, one search, one detail page, a missing route, large-text mobile layout, and visible keyboard focus.
5. Confirm `config/sources.yaml` keeps every source `enabled: false` and `.env.example` contains only fake/disabled values.
6. Record command results and failures. Do not describe a real service as tested.

Package installation may reach approved official registries. Application tests must use fixtures/localhost only.

## External activation — requires separate Rui approval

Before creating or linking any cloud resource, show Rui:

- exact outbound flows from `docs/data-flow.md`;
- first five exact source URLs and their terms/robots/policy review;
- Supabase region choices and data-location implications;
- reviewer email and collection contact email;
- Gemini and database call/item/character caps;
- required GitHub secrets/variables;
- Cloudflare's account-level Pages token scope; and
- confirmation that collection, AI, and deploy switches start `false`.

Only after approval:

1. Create/link the approved GitHub, Supabase, Gemini, and Direct Upload Pages projects.
2. Store secrets in GitHub Encrypted Secrets, never repository files or workflow scope.
3. Apply migrations through the protected manual workflow and bootstrap one reviewer.
4. Prove anon/reviewer/worker/exporter boundaries with production-safe read-only checks.
5. Keep all three kill switches off.
6. Run one approved source with strict caps; inspect every row/proposal/log manually.
7. Expand sources and schedules only after the one-source run passes.

Provisioning is not permission to crawl, call Gemini, deploy, or change DNS.

## Stop conditions

Stop and ask Rui before any paid plan, new outbound data path, production write not described above, destructive migration, public upload, DNS edit, or wider credential scope.
