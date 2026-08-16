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

The Evidence Gate calculates `evidence_set_hash` as SHA-256 over accepted evidence,
ordered by evidence UUID. Each element is serialized as:

```text
evidence_id:source_version_content_hash:origin_group_key:evidence_family_id:evidence_type
```

Elements are joined with `|`. Worker code must use this exact serialization before
asking a reviewer to approve a draft.

## Offline verification

```text
python3 -m unittest discover -s supabase/tests -p 'test_*.py' -v
python3 scripts/generate_database_types.py --check
```

`web/lib/generated/database.types.ts` is generated directly from migrations. Do not
edit it by hand. The offline generator deliberately supports the SQL forms used in
this repository; after the Supabase CLI is available, CI must also rebuild the local
database from zero and compare against `supabase gen types typescript --local`.

## Deliberate Task 4 boundary

`merge_pattern_candidate` authenticates and validates the request, then fails closed.
A safe merge must first construct a reviewed destination draft with its exact evidence
set and claim mappings. That workflow belongs to the Review Queue implementation; the
database will not perform a lossy evidence reassignment as a placeholder.
