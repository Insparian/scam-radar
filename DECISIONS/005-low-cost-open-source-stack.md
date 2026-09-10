# Use a low-cost open-source operating stack

- **What:** Publish the software repository under Apache-2.0 and operate V0.1 with GitHub Actions, Cloudflare Pages Free, Supabase Free, and encrypted off-site database backups, while keeping production data and unpublished review material private.
- **Why now:** External services are still disabled, so the ownership, licensing, hosting, and recovery boundaries can be fixed before accounts, credentials, or production data make a later change expensive.
- **Problem it solves:** Scam Radar needs to remain available and trustworthy as a public-interest project without committing Rui to recurring infrastructure costs before real usage justifies them.
- **Alternative considered:** Supabase Pro with Netlify was considered for managed backups and familiar automatic builds, but its fixed cost and Netlify's current production-deploy credit model do not add matching user value at V0.1. Removing PostgreSQL entirely was also considered, but would weaken reviewer authorization, immutable releases, and auditability.
- **North Star check:** Public code and methodology improve traceability, while a static public site preserves service during backend failure. The tension is that public rules are easier to inspect, so security must come from evidence gates, RLS, scoped credentials, and strict separation of public code from private operational data—not obscurity.

## Implementation boundary

This decision approves repository preparation and the architecture of the free-tier path. It does not itself approve creating cloud projects, uploading a backup, enabling collection or Gemini, deploying a public artifact, changing DNS, or adding a live policy allowlist entry. Those actions remain behind the external activation checkpoint.

The Apache-2.0 license applies to project software and project-authored documentation unless a file says otherwise. It does not license third-party source material, production database contents, unpublished candidates, reviewer notes, audit identities, credentials, backups, or the Scam Radar / 骗局雷达 / Insparian names and marks.
