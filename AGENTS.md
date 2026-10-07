## Decision Checkpoint

When a conversation involves a new feature, architectural change, removing/modifying existing behavior, adding a dependency, or any change motivated by a roadmap item rather than an immediate bug — do NOT proceed directly to implementation.

After discussion, output a decision summary:

- **What:** One sentence.
- **Why now:** Why this is the right time — not just that it's on the roadmap.
- **Problem it solves:** Whose problem, from the user's perspective.
- **Alternative considered:** At least one, and why not chosen.
- **North Star check:** Alignment or tension with product principles.

Wait for explicit "proceed." If Rui says anything else, stop and wait — do not prompt.

After "proceed," append the summary to `DECISIONS/NNN-short-title.md`, then implement.

## Active task authorization — 2026-09-18

Decision 011 authorizes all implementation, repairs, and verification within V0.1
offline launch readiness. Do not repeat product checkpoints for implementation
details within this scope. Record scope expansion in docs/BLOCKED.md for later
decision and continue independent work. Trust/privacy, factual gates, and external
activation boundaries remain unchanged. When Goal Router is explicitly invoked,
Decision 013 and the installed skill govern routing and concurrency. Resume by reading
docs/PROGRESS.md; put progress/blockers only in docs/PROGRESS.md and docs/BLOCKED.md.
Temporary outputs belong in ignored work/. Real collection, model calls,
production business data, backup upload, deployment, and DNS require separate final
activation approval. The current task does not authorize checking existing hosted
previews or production systems. Official documentation and approved installation
and Git synchronization are the only non-local network uses.

## Decision 011 continuation — 2026-09-20

Rui removed the original 12-round total limit. Continue Decision 011 without a
fixed round cap until the full offline acceptance criteria pass, Rui explicitly
pauses, or necessary authorization/credentials/external conditions are absent and
all independent in-scope work is complete. Three consecutive failures on one
problem trigger root-cause review or a changed safe approach, not abandonment of
the problem or the whole task. Preserve existing work; prioritize durable
source-to-database orchestration and one real local end-to-end path before
publication, recovery, and evaluation preparation. Code gaps are not external
activation gates. Real collection, model calls, production data, backup upload,
deployment, and DNS still require separate explicit authorization.

## Anti-Sycophancy principles

Your role is to help Rui make the best decision, not to support his opinion.

- Treat every proposal as a hypothesis, not a requirement.
- Identify assumptions. Give the strongest counter-argument.
- Distinguish facts, inference, and preference.
- Say explicitly when you think Rui is solving the wrong problem.
- Do not manufacture disagreement for its own sake.
- Do not praise an idea unless you can name what makes it strong.

## Repository Contract

- Each directory has one documented responsibility. Do not create parallel locations for the same concern.
- `config/sources.yaml` is the reviewed Source Registry source of truth. Runtime source-health state belongs in Supabase.
- `config/scoring-v0.1.yaml`, `config/models.yaml`, JSON Schemas, and prompts are versioned behavior files.
- Prompts are code: explain the expected behavior change, then run evals. If an eval does not exist, create it before changing the prompt.
- Model-specific prompt adaptations live in separate patch files and must not contaminate provider-neutral prompts.
- `web/lib/generated/database.types.ts` is generated, committed, and never edited by hand.
- Store database timestamps in UTC. Localize them only at the UI boundary.
- Use lower `snake_case` for Python and SQL, `camelCase` for TypeScript values/functions, and `PascalCase` for React components and exported TypeScript types.
- Stable public routes and slugs use lowercase kebab-case. Fixture IDs are descriptive lowercase kebab-case strings; database IDs are UUIDs.

## Directory Responsibilities

- `web/`: Next.js static public site and client-only reviewer UI.
- `worker/`: Python batch pipeline and its tests; no always-on service.
- `supabase/`: forward-only migrations, seed data, and database contract tests.
- `config/`: reviewed source, taxonomy, model, and scoring behavior.
- `prompts/`: provider-neutral prompt prose.
- `contracts/schemas/`: versioned machine-readable AI contracts.
- `evals/`: offline Gold Set, recorded responses, expected results, and reports.
- `docs/`: architecture, data flow, dependency/architecture decisions, and runbooks.
- `scripts/`: thin repository-level automation only.
- `work/`: ignored and disposable local output. Commands may recreate namespaced children and must never treat it as durable state.
- `DECISIONS/`: product decision checkpoints required by this repository's conversation rule.

## Data and Security Boundaries

- Keep application behavior offline and fixture-based until Rui explicitly approves external activation.
- Do not crawl real sources, call Gemini, connect to production Supabase, deploy, edit DNS, or add telemetry before that checkpoint.
- Public search runs locally against the exact immutable static release. Do not transmit or retain search queries.
- Never commit secrets, `.env` files, full production pages, production database dumps, raw HTML, victim PII, build output, caches, or `work/`.
- Do not permanently store raw HTML, screenshots, images, audio, arbitrary headers, or binary source responses.
- Logs contain counts, IDs, versions, hashes, and reason codes—not article bodies, prompts containing source text, personal data, or environment values.
- Any new outbound data path must be documented and explicitly approved before it is enabled.

## Database and Publishing

- PostgreSQL migrations under `supabase/migrations/` are the schema source of truth and are forward-only.
- No destructive production migration without a verified backup, rollback plan, and Rui's explicit confirmation.
- Every externally exposed database object has explicit grants and RLS. Reviewer writes go through narrow transactional RPCs.
- Approved pattern revisions and public release manifests are immutable. Corrections create new revisions/releases.
- A worker or service credential must never be able to impersonate an authenticated human approval.
- Public pages, detail routes, and search indexes must come from one exact immutable `release_id`.

## Dependencies

- Before adding a dependency, record its purpose, maintenance status, lighter alternative, and user/runtime impact in `docs/decisions/`.
- Preserve pinned lockfiles. Do not silently add a paid service, automatic paid fallback, full-stack runtime, daemon, queue server, analytics SDK, or telemetry SDK.
- Tests may use localhost and approved package registries during bootstrap; application tests must not access external services.

## Verification

- Root commands are the stable interface: `make bootstrap`, `make check`, `make test`, `make eval`, `make demo`, `make web`, and `make collect-dry-run`.
- Run proportionate tests after each implementation slice and the complete offline suite before handoff.
- Prompt/schema/model/taxonomy/scoring changes require the recorded-response eval suite and a matching behavior manifest.
- Do not comment out failing checks to make a build pass. Fix the underlying defect.

## Git and Deployment

- Commit messages are concise English descriptions of intent.
- For this open-source repository, commit and push complete, verified, secret-free change sets when appropriate without asking Rui each time. Do not push work-in-progress solely as a checkpoint.
- Force pushes, history rewrites, releases, deployments, DNS changes, and production data mutations still require Rui's explicit confirmation; preserve any stricter exact-confirmation gate already defined by the repository.
- Do not deploy, create cloud projects, modify DNS, or enable real collection/AI without Rui's explicit activation approval.
