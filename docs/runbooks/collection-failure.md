# Collection failure

## Goal

Recover collection without skipping source items, leaking source text, or disturbing the current public site. Offline fixtures are the only currently approved diagnostic input.

## First response

1. Identify the failed `pipeline_run`, source key, stage, commit/behavior versions, and reason code. Do not copy article bodies, headers, secrets, or environment values into logs/issues.
2. Decide whether it is isolated or systemic:
   - one source/parser/HTTP failure is isolated;
   - registry, lease, schema contract, credentials, or systemic database write failure is fatal.
3. For a systemic live failure, set collection off and leave AI/deploy state unchanged unless they are also unsafe. The last deployed static release remains available.
4. Never advance a failed source cursor.

## One-source/parser recovery

1. Review the source's policy, robots response, content type, limits, and error category.
2. Save only a minimal permitted/redacted fixture; never commit a full production page.
3. Add the failing contract test before changing the parser.
4. Fix the narrow source adapter and run its fixture test plus `make collect-dry-run`.
5. Rerun the same fixture twice and confirm no duplicate item/version/review task.
6. After activation only, manually run that one approved source under reduced caps, then confirm its cursor advances exactly once.

If login, CAPTCHA, blocking, paywall, terms, or robots prevents collection, keep/mark the source disabled. Do not evade the control, rotate proxies, or weaken limits.

## Systemic recovery

- Invalid registry: fix reviewed config and rerun schema validation.
- Lease failure: confirm the prior lease is truly expired; do not create a second overlapping run.
- Schema mismatch: stop closed and apply only the reviewed forward migration path.
- Credential failure: follow [key rotation](key-rotation.md); do not print the key.
- Database incident: follow [database recovery](database-recovery.md).

## Close the incident

Verify funnel counts, per-source result, cursor, idempotency, backlog, and unchanged deployed `release_id`. Add the real edge case as a permitted fixture/eval regression and record what failed, why, user impact, and verification.
