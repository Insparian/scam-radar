# Route publication through a Policy Engine with human exception review

- **What:** Insert a deterministic, versioned, fail-closed Policy Engine after the Scam Intelligence Engine. It records `safe_to_automate`, `review_required`, or `blocked`; both policy and human paths converge on immutable verified revisions and exact releases. V0.1 runs `safe_to_automate` in shadow mode and still requires human confirmation before publication.
- **Why now:** `docs/North Star.md` makes machine-by-default, human-by-exception the intended architecture, while the current schema hard-codes human approval as a permanent dependency at evidence, revision, and publication layers.
- **Problem it solves:** Routine safe work can progressively stop consuming reviewer attention without giving AI factual authority or weakening evidence, audit, rollback, and same-release guarantees.
- **Alternative considered:** Change only the public copy and architecture diagram while leaving the human-only authorization model intact. This was rejected because `Last Verified` would be misleading and the implementation would still be unable to support automatic publication. Immediate live auto-publication was also rejected because the current synthetic eval is not launch-qualified.
- **North Star check:** The change directly implements “machine by default, human by exception” while preserving “Heat must never determine truth,” “AI does not own factual authority,” and “when automation conflicts with unsupported certainty, choose evidence.”

Approved implementation boundaries:

1. Model confidence can only downgrade an otherwise policy-eligible case to `review_required`; it can never grant or increase publication authority.
2. `evidence.last_verified_at`, `revision.verified_at`, and `release.published_at` remain distinct timestamps.
3. Public `last_verified_at` is the minimum evidence verification timestamp across evidence supporting claims in the current public revision.
4. Policy and human decisions have distinct immutable audit provenance; automation never impersonates a human reviewer.
5. Both paths use the same database-enforced Evidence/Publish Gate and enter the next exact immutable release. Neither path mutates the live site directly.
6. `safe_to_automate` remains shadow-only in V0.1: the system records what it would automate, while an authenticated human still confirms publication.
7. Live auto-publication requires a separate explicit activation decision after measured live-data performance justifies a narrowly defined policy class.
8. That activation must bind the exact approved `policy_version`, `policy_hash`, and `gate_version` in a forward database migration; a boolean flag cannot grant publication authority.
9. Evidence and revision verification clocks are independent: either may be later, but both must exist and precede the immutable release freeze.
10. A human publication decision must reference a non-blocked Policy Decision; legacy direct approval RPCs are revoked so the Policy Engine cannot be bypassed.

Rui explicitly approved this decision and these clarifications by replying `proceed` on 2026-08-16.

## Implementation mapping

- Deterministic rules and shadow activation: `config/publication-policy-v0.1.yaml` and `worker/src/scam_radar/policy/engine.py`.
- One-way confidence downgrade and immutable rules/effective outcomes: `worker/src/scam_radar/domain.py`, policy unit tests, and the recorded eval.
- Policy/human database provenance, empty exact-policy live allowlist, legacy direct-approval revocation, verification timestamps, and exact release-v2 snapshots: `supabase/migrations/20260816000400_policy_engine_verification.sql`.
- Public `Last Verified / 信息核实至`, separate release-freeze date, and Policy Engine methodology: public Next.js pages and release-v2 validators under `web/`.
- Exception plus V0.1 shadow-confirmation UI: `web/app/admin/`.
- Architecture, flow, activation, failure, deploy, rollback, and key boundaries: ADR-007, `docs/architecture.md`, `docs/data-flow.md`, and all operator runbooks.

## Offline verification on 2026-08-16

- `make check`: passed, including Ruff, mypy, generated-type drift, workflow pinning, secret scan, Prettier, ESLint, TypeScript, and 16 web unit tests.
- Worker plus database contract suite: 76 tests passed.
- `make eval`: 100 cases; authority monotonicity and shadow-denial rates were `1.0`, with zero false authorizations. The report remains correctly `launch_qualified: false`.
- `make demo`: passed with 5 patterns, 4 `review_required`, 1 shadow `safe_to_automate`, and 0 automatic publication authorizations; all 15 static routes built and the export secret scan passed.
- `make collect-dry-run`: passed with all 15 source candidates disabled.

The environment has no PostgreSQL, Supabase CLI, or Docker, so the migration and RPC/trigger transactions have not been executed against a real database. Local Playwright could not bind its temporary test port because the desktop sandbox denied that permission; the static production build succeeded, but the updated E2E file still requires a later permitted run. Before live evidence, add append-only provenance for rejected evidence without inventing historical actors or timestamps, and contract-test the mapping from the normalized database v2 export to the fixture-backed web presentation fields.
