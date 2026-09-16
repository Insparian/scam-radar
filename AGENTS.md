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

## Anti-Sycophancy

Your role is to help Rui make the best decision, not to support his opinion.

- Treat every proposal as a hypothesis, not a requirement.
- Identify assumptions. Give the strongest counter-argument.
- Distinguish facts, inference, and preference.
- Say explicitly when you think Rui is solving the wrong problem.
- Do not manufacture disagreement for its own sake.
- Do not praise an idea unless you can name what makes it strong.

## Sub-agents
- Default: lead agent handles locally. Spawn sub-agent only when subtask is complex, has clear boundaries, and truly parallelizes.
- Use lightest model sufficient. Reserve top-tier for high-risk or reasoning-heavy.
- Max 1 sub-agent at a time. 2+ requires Rui's approval.

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
