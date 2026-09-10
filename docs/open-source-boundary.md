# Open-source and private-data boundary

## Purpose

Public code lets people inspect how Scam Radar separates evidence, attention, policy, and publication. It does not make private operational data public and does not turn unreviewed allegations into an open dataset.

## Licensed public repository

Apache-2.0 covers the repository's software and project-authored documentation unless a file states otherwise. This includes application code, migrations, schemas, reviewed configuration, provider-neutral prompts, synthetic fixtures, tests, eval tooling, and architecture/runbook documentation.

The license does not grant rights to the Scam Radar / 骗局雷达 / Insparian names or logos. Third-party source material retains its original rights. Public release records may quote or link to evidence only within the separately reviewed product and source-use boundaries; Apache-2.0 does not automatically license those records or their third-party material for bulk reuse.

## Never commit or publish through the repository

- `.env` files, API keys, passwords, signing material, session tokens, or production identifiers that should be secret;
- production database dumps, backups, reviewer identities/notes, internal audit exports, or unpublished candidates;
- victim personal information, user reports, private correspondence, or unresolved takedown material;
- full production pages, raw HTML, screenshots, audio, binaries, arbitrary response headers, or malicious payloads;
- generated static output, package caches, local containers, or disposable `work/` results.

Only synthetic `.invalid` fixtures and deliberately fake credentials may appear in tests and examples.

## What may become public through a release

Only an immutable, authorized public release may contain canonical pattern wording, user-facing protection advice, minimal source attribution and evidence links, conservative evidence freshness, Heat, and release metadata. The release exporter is an allowlist, not a database dump.

Opening the repository does not authorize publishing a release. Production data remains in Supabase; the public website receives only the reviewed static artifact for one exact `release_id`.

## Before changing repository visibility to public

1. Run `make open-source-audit` against a full Git clone.
2. Review every tracked file plus untracked material intended for addition.
3. Confirm the Git hosting account has 2FA and recovery access.
4. Configure public-repository Actions so forked pull requests receive no production secrets and cannot run production deployment environments.
5. Protect `main`, require CI, and restrict production environment approval to maintainers.
6. Verify the public issue templates and contribution guidance direct sensitive reports to `rui@insparian.com`.
7. Inspect the generated `web/out` independently before the first public deployment.

If a secret or private record ever entered Git history, rotating it is mandatory. Removing a file from the current branch is not enough. Prefer creating a clean public repository when preserving the old history has less value than eliminating uncertainty; rewriting shared history requires a separate destructive-action decision.
