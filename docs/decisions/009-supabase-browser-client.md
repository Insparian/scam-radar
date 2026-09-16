# ADR-009: Official Supabase browser client for the private reviewer UI

- **Status:** Accepted
- **Date:** 2026-09-16

## Decision

Use the official `@supabase/supabase-js` browser client, pinned through the committed npm lockfile, only inside client components under `/admin`. It handles password authentication, session persistence, token refresh, sign-out, and calls to the narrowly granted reviewer RPCs.

The client reads only `NEXT_PUBLIC_SUPABASE_URL` and `NEXT_PUBLIC_SUPABASE_PUBLISHABLE_KEY`. These values are public identifiers, not database secrets. Authorization remains enforced by the authenticated JWT, database grants, `private.assert_enabled_admin`, and security-definer RPCs with an empty search path.

## Maintenance status

`@supabase/supabase-js` is Supabase's first-party JavaScript SDK. Version `2.116.0` was the current npm release when this decision was recorded, with registry metadata last modified on 2026-09-07. The exact dependency graph is captured by `web/package-lock.json` and remains subject to the existing Dependabot and `npm audit` checks.

## Alternatives

- **Hand-written `fetch` calls to Auth and PostgREST:** smaller initial install, but would require Scam Radar to own session storage, token refresh, Auth error handling, and RPC request semantics. That increases the security-sensitive code we maintain and was rejected.
- **A server-side Auth layer:** incompatible with the accepted static-export architecture and would add an always-on runtime without a public-user benefit.
- **Supabase SSR helpers:** unnecessary because `/admin` authenticates only after hydration and cannot use server cookies or redirects.

## User and runtime impact

- Public pages and local public search do not import or initialize the SDK and continue to work from the immutable static release without Supabase.
- Opening `/admin` loads the Auth client and may contact only the configured Frankfurt Supabase project.
- Reviewer login credentials, Auth/session metadata, RPC request data, and durable review decisions leave the device for Supabase. Public search text does not.
- If the public environment variables are absent, the admin surface fails closed with a configuration message and makes no network request.
