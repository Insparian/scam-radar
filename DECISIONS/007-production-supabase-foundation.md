# Establish the production Supabase foundation in Frankfurt

- **What:** Create an empty Supabase Free production project in the exact `eu-central-1` Frankfurt region, apply the existing forward migrations through a protected manual GitHub workflow, bootstrap the privately supplied project mailbox as the first reviewer, and verify the anon/reviewer/worker/exporter boundaries with synthetic records only.
- **Why now:** The offline application suite and real local PostgreSQL contract have passed, so the next unverified risk is whether Auth, grants, RLS, RPCs, and credential separation hold together in the managed production environment before any live evidence exists.
- **Problem it solves:** The operator needs a trustworthy private system of record and reviewer identity boundary before source collection can begin, so a worker cannot impersonate a reviewer or publish through an unauthorized path.
- **Alternative considered:** Remain fixture/local-only until source collection is ready. This avoids an idle cloud resource, but it defers the highest-risk managed-environment checks until real data is waiting to enter the system. Stockholm was also considered; it has no measurable user benefit because public visitors never query Supabase and the operator reaches the service through a VPN, while Frankfurt is Supabase's standard Europe placement.
- **North Star check:** This strengthens evidence traceability and fail-closed publication authority. It adds infrastructure without an immediate public feature, so the scope is limited to an empty database, one reviewer identity, synthetic boundary probes, and disabled live-data switches.

## Approved external boundary

- Primary database region: AWS `eu-central-1` (Frankfurt, Germany).
- First reviewer identity: the project-specific mailbox supplied privately by Rui; the address must stay out of the public repository, workflow inputs, and logs.
- Supabase receives schema migrations, synthetic security-probe records, the reviewer email, Auth/session metadata, and ordinary service request metadata. It receives no real source evidence, victim information, search queries, production article bodies, or Gemini payloads in this slice.
- The project-scoped database credential lives only in the protected GitHub environment or an approved local secret store; it is never committed or passed to public build steps. This path does not create or retain an account-wide Supabase access token.
- The production migration path remains manual and exact-confirmation gated. Collection, AI, backup, production deployment, DNS, and live automatic publication remain disabled.

Rui explicitly approved this decision by replying `Proceed` and supplied the private
reviewer mailbox on 2026-09-12.

## Implementation evidence

On 2026-09-16 the Free project was created in `eu-central-1`, the empty production
schema was migrated, and the pre-created Auth identity was mapped to exactly one
enabled `reviewer`. Hosted Supabase retained non-DML `service_role` table grants even
with automatic exposure disabled, so forward migration
`20260916000100_service_role_table_lockdown.sql` removed direct current and default
table/sequence privileges while preserving the explicitly granted worker/exporter
RPCs. Production probes confirmed five migration versions, zero application rows,
no direct public-table grants for API roles, reviewer/worker/exporter separation, and
an empty live-policy allowlist.

The Supabase project exists, but the web application remains fixture-only: no product
login route, production Auth client, real collection, Gemini, backup, release export,
production deployment, DNS, or live automatic publication was activated. After
Rui's explicit credential-storage confirmation, the project-scoped
session-pooler database URL and private reviewer email were stored in the protected
GitHub `supabase-production` environment. Neither value is present in the checkout.
