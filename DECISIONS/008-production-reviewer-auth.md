# Connect the reviewer UI to production Supabase Auth

- **What:** Add `/admin/login` with Supabase Auth, guard the reviewer routes, and replace fixture-only reviewer reads and actions with narrowly scoped RPC access while keeping the public site and public search static and browser-local.
- **Why now:** The managed reviewer identity, database migrations, and production role boundaries are verified, but the operator still has no product login or durable reviewer workflow. Proving the human control plane before live evidence arrives avoids introducing real data into an untested approval path.
- **Problem it solves:** The reviewer cannot currently sign in through the product or persist review decisions; the existing reviewer UI is fixture-only.
- **Alternative considered:** Add only a login screen while leaving the reviewer UI on fixtures. This was rejected because it would imply that authenticated actions are durable when they are not. Deferring Auth until source activation was also considered, but would leave the reviewer safety boundary unproven when the first live evidence arrives.
- **North Star check:** This supports human approval as a policy exception and preserves least privilege. The tension is a new browser-to-Supabase path: Supabase receives login credentials, Auth/session and ordinary request metadata, reviewer RPC traffic, and reviewer decisions. Public search text remains local and must never be sent to Supabase.

## Approved boundary

- Only the private `/admin` surface may initialize the production Supabase client.
- The browser may use the public Supabase project URL and publishable key; authorization continues to depend on grants, RLS, authenticated identity, and narrow RPCs rather than key secrecy.
- Reviewer credentials, session metadata, RPC request data, and durable review decisions may flow to the approved Frankfurt Supabase project.
- Public pages, public search, and the immutable static release must not query Supabase or transmit search text.
- Real-source collection, Gemini, live evidence ingestion, release export, public deployment, R2 backup, DNS, and live automatic publication remain disabled and separately gated.
- This decision authorizes implementation and offline verification. It does not authorize a production deployment.

Rui explicitly approved this decision by replying `proceed` on 2026-09-16.
