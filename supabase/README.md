# Database contract

This directory owns the private PostgreSQL contract. Migrations are forward-only;
`seed.sql` contains synthetic `.invalid` fixtures; `tests/` verifies the contract
without Docker, PostgreSQL, Supabase, network access, or credentials.

## Migration responsibilities

- `20260816000100_core_schema.sql`: tables, relational integrity, checks, and indexes.
- `20260816000200_security_invariants.sql`: RLS, grants, reviewer identity checks,
  immutable records, append-only audit, and the database-side Publish Gate.
- `20260816000300_reviewer_release_rpcs.sql`: narrow reviewer actions and exact-release
  preparation, export, and deployment bookkeeping.
- `20260816000400_policy_engine_verification.sql`: append-only Policy Engine decisions,
  separate human/policy verification provenance, the shadow-confirmation transaction,
  a fail-closed live-policy transaction, and public release schema v2 freshness snapshots.
- `20260916000100_service_role_table_lockdown.sql`: hosted-project hardening that keeps
  `service_role` on explicitly granted worker/exporter RPCs and removes direct public
  table or sequence privileges, including future defaults.
- `20260916000200_reviewer_bootstrap_rpc.sql`: one authenticated, enabled-reviewer read
  boundary for queue, draft, public-database policy, Heat, and evidence metadata. It
  deliberately excludes raw source text and evidence spans.
- `20260917000100_evidence_resolution_events.sql`: one append-only resolution event for
  every terminal accepted/rejected evidence transition, written atomically with the
  state change and bound to honest human, live-policy, or migration-only legacy
  authority.

The Evidence Gate calculates `evidence_set_hash` as SHA-256 over accepted evidence,
ordered by evidence UUID. Each element is serialized as:

```text
evidence_id:source_version_content_hash:origin_group_key:evidence_family_id:evidence_type
```

Elements are joined with `|`. Worker code must use this exact serialization before
asking a reviewer to approve a draft.

## Policy and verification contract

`policy_decisions` records the exact draft, review item, candidate/input/content/evidence
hashes, Gate result, deterministic rules result, final result, execution mode, explicit
publication authorization, confidence downgrade, reasons, and policy version/hash. Rows
are append-only and have no browser table grant. Every decision belongs to a non-null
pipeline run. Model confidence may only downgrade `safe_to_automate` to
`review_required`; a non-eligible Evidence Gate must remain `blocked`.

Human provenance uses `accepted_by`/`approved_by` plus a real `review_event`. Policy
provenance uses a `policy_decision_id` and leaves human identity columns null. Both
accepted and rejected evidence also receive exactly one append-only
`evidence_resolution_events` row in the same transaction, including outcome, reason,
reason codes, decision/review context, and the correct human or policy authority. V0.1
can record `shadow` decisions and an authenticated reviewer can confirm any non-blocked
shadow result through `confirm_policy_publication`. The same human-exception transaction
accepts an active future live `review_required` result, but never a blocked result or a
live policy-authorized safe result. `apply_live_policy_publication` is present so
activation does not require redesigning the transaction.

`confirm_policy_publication` is the only API role's human publication entry point. It
requires Policy Decision context before evidence mutation. The legacy
`approve_new_pattern` and `approve_pattern_update` functions remain in history for
migration compatibility but are revoked from every API role.

`active_live_publication_policies()` is empty in V0.1. A policy-authorized decision and
every live application must match one exact active `(policy_version, policy_hash,
gate_version)` tuple. Activation therefore requires a separate forward migration that
adds the explicitly approved tuple; it cannot be enabled by a broad boolean switch.

The timestamps deliberately mean different things:

- `pattern_evidence.last_verified_at`: when that evidence was checked.
- `pattern_revisions.verified_at`: when the immutable revision passed verification.
- `public_releases.published_at`: when schema-v2 release contents were frozen for
  publication; `deployed_at` remains deployment bookkeeping.

For each schema-v2 release, `public_release_evidence_items` pins every claim-supporting
accepted evidence timestamp. `public_release_items.last_verified_at` is the conservative
minimum of those timestamps. Revision verification and schema-v2 release preparation
both fail closed if any accepted claim-supporting evidence lacks `last_verified_at`.
Revision and evidence verification timestamps must each be no later than the release's
manifest-freeze `published_at`; they intentionally have no ordering constraint relative
to each other. Both snapshot layers and `published_at` are covered by the release
manifest hash.

`export_public_release` preserves schema-v1 export for historical releases and emits a
numeric `schema_version: 2` for new releases. V2 exposes release `published_at`, pattern
`verified_at` and `last_verified_at`, and each evidence item's own `last_verified_at`.
It does not expose the verification path, reviewer identity, raw source text, spans, or
candidate payload.

The database v2 export currently covers the normalized public core, while the offline
web fixture also contains presentation copy such as `immediate_action`,
`mechanism_steps`, categories, search terms, and timeline entries. Before production
activation, choose and contract-test one versioned mapping: either persist those fields
on immutable revisions or add a deterministic export adapter. Do not silently invent
them during deployment. The current static build remains fixture-backed.

## Offline verification

```text
python3 -m unittest discover -s supabase/tests -p 'test_*.py' -v
python3 scripts/generate_database_types.py --check
```

`web/lib/generated/database.types.ts` is generated directly from migrations. Do not
edit it by hand. The offline generator deliberately supports the SQL forms used in
this repository, including forward `ALTER TABLE ADD COLUMN` changes and replaced RPCs.
After the Supabase CLI is available, CI must also rebuild the local database from zero,
execute transactional RPC tests, and compare against
`supabase gen types typescript --local`.

## Empty production foundation

The protected manual `Production Supabase foundation` workflow is the only reviewed
path for the first production migration. It uses a project-scoped database URL rather
than an account-wide Supabase access token, applies forward migrations without the
synthetic seed, maps a pre-created Auth user from a private environment secret, and
then checks that application tables remain empty. The verification proves that anon,
authenticated, and service roles have no broad table grants; reviewer, worker, and
exporter RPCs remain separated; and the live automatic-publication allowlist is empty.

The reviewer sets their password directly in the Supabase Dashboard bootstrap; the
workflow neither receives that password nor adds an SMTP dependency. No real evidence
enters the database, and this workflow does not enable collection, Gemini, backups,
deployment, DNS, or live automatic publication.

## Deliberate Task 4 boundary

`merge_pattern_candidate` authenticates and validates the request, then fails closed.
A safe merge must first construct a reviewed destination draft with its exact evidence
set and claim mappings. That workflow belongs to the Review Queue implementation; the
database will not perform a lossy evidence reassignment as a placeholder.

Resolved evidence rows are retained and immutable. The seventh migration adds an
append-only, one-to-one terminal resolution event for accepted and rejected evidence.
Pre-existing terminal rows are backfilled as `legacy_unknown` with no invented actor,
policy, review item, or occurrence time; the insert trigger rejects new
`legacy_unknown` events after migration. Production remains on six migrations until the
seventh migration receives its separate production-mutation approval.
