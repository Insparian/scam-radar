# ADR-002: Supabase RLS with immutable reviewed releases

- **Status:** Accepted
- **Date:** 2026-08-16

## Decision

Use Supabase PostgreSQL as the private system of record, but make an immutable static release—not a database query—the only public publishing plane.

Authorization and mutation rules:

- Enable RLS on every externally exposed table and view. Grant `anon` no table or function access.
- A publishable key identifies the static admin application; a Supabase Auth JWT identifies the human. Authentication alone is insufficient: every reviewer RPC also checks an enabled `admin_users` row.
- Reviewer writes use named transactional RPCs. Revoke default function execution from `public` and `anon`, then grant only the required function signatures to `authenticated`.
- Prefer `security invoker`. A narrowly justified `security definer` function must set `search_path = ''`, schema-qualify every object, validate `auth.uid()`, verify optimistic `row_version`, and append its audit event in the same transaction.
- Database triggers reject update/delete of approved `pattern_revisions` and immutable release-manifest rows. A correction creates a new revision and a new release.
- Approval triggers require `auth.uid() = approved_by` and an enabled admin. A worker/secret-key request without a human JWT therefore cannot manufacture an approval, even though its key bypasses RLS.
- Use current `sb_publishable_...` and `sb_secret_...` keys for new projects. Legacy `anon`/`service_role` names exist only in one compatibility adapter.

## Release invariant

`prepare_public_release()` copies the previous deployed manifest, applies only explicitly approved revisions/unpublishes, pins one Heat snapshot per pattern, and freezes an exact `release_id`. Export, static pages, detail routes, and search all use only that ID. Release status bookkeeping may advance; manifest content never mutates.

## Why

The highest-cost failure is an unsupported public accusation. Database constraints make human identity, evidence support, and revision immutability harder to bypass than UI checks. Static releases also prevent a half-published state where search knows about a pattern but its page does not exist.

## Alternatives

- **RLS plus direct table editing:** less SQL, but stale clients could write partial state and audit/revision rules would be spread across screens.
- **Mutable “currently approved” rows:** simpler publishing, but corrections erase what was actually reviewed and deployed.
- **Public read policies on approved rows:** removes export machinery, but creates runtime database dependence and release skew.

## Consequences and checks

- Migrations are the forward-only schema source of truth.
- Views use `security_invoker = true` or remain in an unexposed schema with explicit revoked grants.
- Local database tests cover anon denial, disabled-user denial, reviewer RPC success, stale version rejection, append-only audit, approved-revision immutability, and service/worker approval rejection.
- Secret keys remain backend-only. Supabase documents that they map to `service_role` and bypass RLS, so RLS is not the only approval control.

## Sources

- [Supabase Row Level Security](https://supabase.com/docs/guides/database/postgres/row-level-security)
- [Supabase database functions](https://supabase.com/docs/guides/database/functions)
- [Supabase API keys](https://supabase.com/docs/guides/getting-started/api-keys)
