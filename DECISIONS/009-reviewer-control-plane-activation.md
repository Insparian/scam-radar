# Activate the reviewer control plane

- **What:** Apply migration `20260916000200`, deploy the Auth-enabled reviewer build to a dedicated Cloudflare Pages preview protected by Cloudflare Access, and smoke-test password login, queue bootstrap, sign-out, and the fail-closed permission path. Keep the existing public fixture preview unconnected to Supabase.
- **Why now:** The application and from-zero database contracts pass, so the real operator path can be tested without mixing in live source data.
- **Problem it solves:** The reviewer implementation exists only in code; the operator cannot yet use the product to sign in or persist review decisions.
- **Alternative considered:** Add the production public URL/key to the existing public fixture preview. This was rejected because it would mix a deliberately fixture-only public surface with the production control plane and make the environment boundary harder to understand and revoke.
- **North Star check:** A separately restricted control plane preserves least privilege and keeps public search static and browser-local. The tension is an additional hosted surface and an extra access layer for the single reviewer.

## Approved activation boundary

- The reviewer browser may send login credentials, Auth/session metadata, narrow reviewer RPC requests, evidence choices, and decision notes only to the existing Frankfurt Supabase project.
- Cloudflare Pages receives only compiled static assets containing the public Supabase project URL and publishable key. Those values identify the project but grant no authority by themselves.
- Cloudflare Access receives the reviewer's access identity and ordinary request metadata before it serves the reviewer preview. The Pages URL must not be publicly reachable before this policy is active.
- The deployment is manual, single-reviewer, free-tier, and has no scheduled trigger or automatic paid fallback. Existing account-scoped Pages credentials keep their current Pages-only permission; do not expand them to Access, DNS, Workers, R2, billing, or membership.
- Public environment values belong in a protected GitHub environment. Database URLs, secret/service keys, reviewer email, and passwords must never enter the compiled site or repository.
- Stop controls are: disable the reviewer deployment, disable the `admin_users` row, revoke the Auth session, and remove the deployed public configuration. Database rollback, destructive migration, custom DNS, and public production publication are not authorized.
- Real-source collection, Gemini, evidence ingestion, release export, public launch, R2 backup, DNS, telemetry, and live automatic publication remain disabled and separately gated.

Rui explicitly approved this decision by replying `proceed` on 2026-09-16.
