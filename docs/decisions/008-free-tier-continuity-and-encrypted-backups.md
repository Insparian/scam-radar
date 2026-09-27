# ADR-008: Free-tier continuity with encrypted off-site backups

- **Status:** Accepted for design; cloud activation and backup upload not approved
- **Date:** 2026-09-10

## Decision

Run V0.1 on Supabase Free while the public website remains a self-contained static Cloudflare Pages artifact. A database outage or free-tier pause may stop collection and review, but must not remove or corrupt the last trusted public release.

Before production data is accepted, add a scheduled logical database export that is encrypted on the trusted runner **before** upload to a private Cloudflare R2 bucket. R2 receives only ciphertext, an opaque object name, ordinary request metadata, and a minimal integrity manifest. A raw dump must never be stored as a GitHub artifact, committed, logged, or uploaded.

Use an `age` public recipient for encryption so CI needs only the public encryption recipient; keep the recovery identity offline, separately backed up, and unavailable to the routine backup job. Use `pg_dump`/the Supabase-supported logical dump path to export and a pinned `rclone` binary for R2's S3-compatible upload. These are activation candidates, not current repository/runtime dependencies.

## Why this is cheaper without weakening the public site

Supabase Free does not include downloadable automatic backups. The static public site does not query Supabase at request time, so paying for uninterrupted database runtime is not necessary for V0.1 public continuity. The material missing control is recoverability, which a small encrypted logical export supplies independently of the database provider.

Cloudflare Pages Free currently permits 500 builds per month and serves static asset requests free. R2 currently includes 10 GB-month of Standard storage plus ample operations for small scheduled backups. These quotas are observations, not entitlements: the activation checklist must recheck them and configure hard cost alerts without automatic paid fallback.

## Alternatives

- **Supabase Pro:** simpler managed daily backups and less pausing risk, but a fixed monthly charge is premature before database size, review frequency, or recovery objectives require it.
- **Local-only manual backups:** no new cloud path, but depends on one person's memory and device and does not meet disaster-recovery needs.
- **Unencrypted R2 objects:** operationally simpler but exposes all private records if the bucket or key is misconfigured; rejected.
- **Passphrase encryption in CI:** avoids a recovery key file but puts decryption authority into routine automation; rejected in favor of public-key encryption.
- **Git/SQLite as the production system of record:** may remove a service account but weakens transactional reviewer authorization, append-only audit, concurrency, and immutable release enforcement; rejected.

## Dependency review

| Candidate | Purpose | Maintenance signal | Lighter alternative | User/runtime impact |
|---|---|---|---|---|
| PostgreSQL `pg_dump` matching the server major version | Consistent logical database export | PostgreSQL first-party utility | Supabase CLI wrapper | Backup runner only; never ships to browsers |
| `age` pinned stable release | Encrypt with a public recipient before any upload | Small, actively maintained open-source tool with a simple file format | OpenSSL passphrase encryption | Backup/recovery operator only; removes decryption secrets from routine CI |
| `rclone` pinned stable release | Upload ciphertext to R2 and verify object metadata | Mature open-source multi-provider tool with checksums | AWS CLI or handwritten signed HTTP | Backup runner only; R2 credentials are scoped to one private bucket where platform support permits |

Exact versions, checksums, and installation steps must be recorded when activation implements the job. No `curl | shell`, floating container tag, or unpinned action is allowed.

## Offline implementation pins (2026-09-20)

- `pg_dump`/`psql`: [Docker Official Image `postgres:17.9`](https://hub.docker.com/layers/library/postgres/17.9/images/sha256-66b6a97eac1771fc78bd201b918b4253859f436c6913aeede97bd5366cce89ae), immutable multi-platform index `sha256:2a0d0fe14825b0939f78a8cad5cd4e6aa68bf94d0e5dd96e24b6d23af4315545`. The backup job pins this index and checks the server major before dump; a newer incompatible server fails closed. This image is runner-only, never public runtime.
- `age`: [v1.3.2 official release](https://github.com/FiloSottile/age/releases/tag/v1.3.2), Linux amd64 archive SHA-256 `cbe24006683f8eb669266162894b9a522a1af52f2665fbc63a4bb032ed26ac10`. This matches the version used in the synthetic local restore rehearsal.
- `rclone`: [v1.75.1 official download manifest](https://downloads.rclone.org/v1.75.1/SHA256SUMS), Linux amd64 ZIP SHA-256 `982b5aa772841168f8e380f139e9e787b2a105403e32b94da8676a0e1c0a13ab`; macOS arm64 ZIP for the localhost rehearsal SHA-256 `c61d7a371c62bcbbe882c3423aa4b8bf63485c248dd0f692997b8f0c3f6d0c6f`. It runs only after ciphertext is verified and receives a private-bucket R2 credential. No new browser dependency or automatic paid path is added.

The scheduled workflow remains disabled until separate authorization. These
official pins establish reproducible offline code; they do not establish the
production database major version, R2 bucket permissions, or real restore.

## Recovery and retention constraints

- A backup is not healthy until a separate restore rehearsal verifies schema, row counts, release hashes, authorization boundaries, and a byte-equivalent exact release export.
- Set a written recovery point objective, recovery time objective, retention schedule, and deletion/lifecycle policy at activation. Automated deletion is not authorized by this ADR alone.
- Keep the R2 bucket private, block public access, enable the narrowest available credentials, and use a dedicated bucket/account when blast-radius isolation matters.
- The backup job must have database read/export authority and bucket write authority, but no deploy, DNS, reviewer, Gemini, or live-policy authority.
- Failure alerts must not contain row data, environment values, object credentials, or raw dump output.

## Outbound-data effect

After a later explicit activation, private Supabase records will leave Supabase through the trusted GitHub runner as a transient logical dump, become encrypted locally on that runner, and only then leave for Cloudflare R2. Cloudflare will receive encrypted database content. This flow is disabled now and is listed as F9 in `docs/data-flow.md`.

## References

- [Supabase database backups](https://supabase.com/docs/guides/platform/backups)
- [Cloudflare R2 pricing](https://developers.cloudflare.com/r2/pricing/)
- [age](https://age-encryption.org/)
- [rclone cryptographic signing and downloads](https://rclone.org/downloads/)
