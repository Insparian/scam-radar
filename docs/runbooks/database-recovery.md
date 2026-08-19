# Database recovery

## Principle

Protect auditability before speed. The deployed static release is the public continuity layer; database recovery must not mutate approved history or silently publish drafts.

## Offline/local recovery — allowed now

1. Treat local database state and `work/` as disposable.
2. Rebuild from forward-only migrations and synthetic `supabase/seed.sql` using the repository command.
3. Run database contract/RLS tests, generated-type drift check, policy tests, evals, and fixture demo.
4. Never import a production dump into fixtures or commit generated database state.

No production backup or restore capability has been tested yet.

## Production incident — activation only

1. Set collection, AI, and deployment off. Leave the last known-good static site serving.
2. Classify the problem: availability, bad migration, permission/RLS regression, data corruption, accidental write, or credential misuse.
3. Record schema version, release ID, last good run, affected tables/rows, timestamps, and redacted errors. Do not run exploratory destructive SQL.
4. Verify the provider's current backup/restore options and take a fresh backup/export before any irreversible repair. Free-tier capabilities can change; do not assume point-in-time recovery exists.
5. Prefer an additive forward migration. For restore, restore into a separate recovery database/project first and compare counts, constraints, hashes, approvals, audit chain, and release manifests.
6. Before cutover, prove:
   - anon has no private access;
   - disabled/auth-only users cannot review;
   - a worker/secret request cannot create an authenticated approval;
   - policy decisions and human events retain distinct append-only provenance;
   - a shadow decision cannot satisfy live policy publication;
   - verified revisions, release items, policy decisions, and audit events are immutable;
   - evidence `last_verified_at`, revision `verified_at`, and release `published_at` remain distinct;
   - the deployed release can be exported byte-for-byte by its exact ID.
7. Cut over or perform a destructive production repair only with a documented rollback plan and Rui's explicit confirmation.
8. Resume one path at a time: database reads, reviewer actions, one-source collection, AI, then deployment.

## Never do

- `DROP`, `TRUNCATE`, production reset, destructive type change, or bulk rewrite without verified backup/rollback and confirmation;
- reverse migration by editing or deleting old migration files;
- overwrite a verified revision or published release to make history look clean;
- let a web release depend on an unconfirmed destructive migration;
- expose production rows, victim PII, source bodies, credentials, or dumps in issues/artifacts.

Close with a forward fix, verification evidence, affected user impact, and a regression test/runbook update. Database restoration alone is not proof that the public site and recorded deployment agree.
