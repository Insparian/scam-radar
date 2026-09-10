# Database recovery

## Principle

Protect auditability before speed. The deployed static release is the public continuity layer; database recovery must not mutate approved history or silently publish drafts.

## Offline/local recovery — allowed now

1. Treat local database state and `work/` as disposable.
2. Rebuild from forward-only migrations and synthetic `supabase/seed.sql` using the repository command.
3. Run database contract/RLS tests, generated-type drift check, policy tests, evals, and fixture demo.
4. Never import a production dump into fixtures or commit generated database state.

No production backup or restore capability has been tested yet. The approved design uses a logical export encrypted on the trusted runner before upload to a private R2 bucket; the workflow remains deliberately fail-closed until external activation.

## Backup activation gate

Before accepting production data:

1. Recheck Supabase Free export support and Cloudflare R2 quotas and region implications.
2. Pin and checksum compatible `pg_dump`, `age`, and `rclone` versions as documented in ADR-008.
3. Generate an `age` recovery identity offline. Store its public recipient in the backup configuration and keep the private identity in two independently protected offline locations; never put it in GitHub.
4. Create one private bucket and the narrowest available write credential. Confirm public access is blocked.
5. Define recovery point/time objectives and an explicit retention/lifecycle policy. Automatic deletion needs approval as part of that policy.
6. Implement the job so the raw logical dump exists only in protected runner-local temporary storage, is encrypted before upload, never becomes a GitHub artifact, and is removed when the job exits.
7. Restore the encrypted object into a disposable environment and verify schema, counts, hashes, grants/RLS, policy/human provenance, immutable release controls, and byte-equivalent export of one exact release.
8. Only then set `SCAM_RADAR_BACKUP_ENABLED=true`. Keep paid auto-upgrades disabled and alert on failure or approaching free limits.

## Production incident — activation only

1. Set collection, AI, and deployment off. Leave the last known-good static site serving.
2. Classify the problem: availability, bad migration, permission/RLS regression, data corruption, accidental write, or credential misuse.
3. Record schema version, release ID, last good run, affected tables/rows, timestamps, and redacted errors. Do not run exploratory destructive SQL.
4. Verify the provider's current backup/restore options and take a fresh backup/export before any irreversible repair. Free-tier capabilities can change; do not assume point-in-time recovery exists.
5. Download the selected encrypted R2 object, verify its ciphertext checksum, decrypt only in the isolated recovery environment with the offline identity, and record which object/version was used without logging its contents.
6. Prefer an additive forward migration. For restore, restore into a separate recovery database/project first and compare counts, constraints, hashes, approvals, audit chain, and release manifests.
7. Before cutover, prove:
   - anon has no private access;
   - disabled/auth-only users cannot review;
   - a worker/secret request cannot create an authenticated approval;
   - policy decisions and human events retain distinct append-only provenance;
   - a shadow decision cannot satisfy live policy publication;
   - verified revisions, release items, policy decisions, and audit events are immutable;
   - evidence `last_verified_at`, revision `verified_at`, and release `published_at` remain distinct;
   - the deployed release can be exported byte-for-byte by its exact ID.
8. Cut over or perform a destructive production repair only with a documented rollback plan and Rui's explicit confirmation.
9. Resume one path at a time: database reads, reviewer actions, one-source collection, AI, backup, then deployment.

## Never do

- `DROP`, `TRUNCATE`, production reset, destructive type change, or bulk rewrite without verified backup/rollback and confirmation;
- reverse migration by editing or deleting old migration files;
- overwrite a verified revision or published release to make history look clean;
- let a web release depend on an unconfirmed destructive migration;
- expose production rows, victim PII, source bodies, credentials, or dumps in issues/artifacts.

Close with a forward fix, verification evidence, affected user impact, and a regression test/runbook update. Database restoration alone is not proof that the public site and recorded deployment agree.
