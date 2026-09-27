# Database recovery

## Principle

Protect auditability before speed. The deployed static release is the public continuity layer; database recovery must not mutate approved history or silently publish drafts.

## Offline/local recovery — allowed now

1. Treat local database state and `work/` as disposable.
2. Rebuild from forward-only migrations and synthetic `supabase/seed.sql` using the repository command.
3. Run database contract/RLS tests, generated-type drift check, policy tests, evals, and fixture demo.
4. Never import a production dump into fixtures or commit generated database state.

No production backup or restore capability has been tested yet. The dormant `backup.yml` job now implements the logical export encrypted on the trusted runner before upload to a private R2 bucket. Its scheduled and manual entries remain fail-closed until the separate backup/activation switches and exact confirmation are set. The synthetic local `make recovery-rehearsal` and localhost S3 protocol rehearsal passed; neither proves a real R2 restore.

## Backup activation gate

Before accepting production data:

1. Recheck Supabase Free export support and Cloudflare R2 quotas and region implications.
2. Recheck the pinned `pg_dump` 17.9 image, age 1.3.2 archive and rclone 1.75.1 checksum in [ADR-008](../decisions/008-free-tier-continuity-and-encrypted-backups.md). The workflow verifies all three before connecting. It refuses a PostgreSQL server newer than its dump client.
3. Generate an `age` recovery identity offline. Store its public recipient in the backup configuration and keep the private identity in two independently protected offline locations; never put it in GitHub.
4. Create one private bucket and an object-scoped credential with only the read/list and write operations needed to verify uploaded ciphertext; no bucket administration or delete. Confirm public access is blocked. The upload adapter reads back each object and refuses hash mismatch or overwrite.
5. Define recovery point/time objectives and an explicit retention/lifecycle policy. Automatic deletion needs approval as part of that policy.
6. Configure the named production-backup environment with the exact approved Supabase host/user, database password, Supabase CA certificate, age **public recipient**, R2 account/bucket, and R2 object credential. Use `verify-full`; do not downgrade TLS to make the job pass. The job streams the raw dump from the pinned PostgreSQL client directly into age; no plaintext dump file or GitHub artifact is created. Its temporary ciphertext and CA file are removed when the job exits. The private identity is never available to CI.
7. Restore the encrypted object into a disposable environment and verify schema, counts, hashes, grants/RLS, policy/human provenance, immutable release controls, and byte-equivalent export of one exact release.
8. Only after a real-object restore succeeds, set `SCAM_RADAR_BACKUP_ENABLED=true`, `SCAM_RADAR_LIVE_ACTIVATION_APPROVED=true`, and the exact one-time saved backup confirmation according to Rui's separate approval. The daily schedule is 02:43 UTC and manual runs require the same typed confirmation. Keep paid auto-upgrades disabled; GitHub workflow failure must alert the operator, and R2 free-tier usage must be monitored. An uploaded object without its integrity manifest is an incomplete run, not a healthy backup; inspect the object ID from the failed run before any retry, and never delete it silently.

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
