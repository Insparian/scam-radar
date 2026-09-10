# Provision Cloudflare Pages for the first public preview

- **What:** Use Cloudflare Pages Free with Direct Upload from trusted GitHub Actions, publishing only the validated static `web/out` artifact and leaving Git-based auto-deploy disabled.
- **Why now:** The public repository, offline CI, and GitHub security baseline are complete, so hosting is now the next bottleneck to obtaining a real preview URL.
- **Problem it solves:** Scam Radar needs a low-cost public preview without depending on Netlify organization-repository integration or adding a continuously running server.
- **Alternative considered:** Netlify Git auto-deploy retains the organization-account friction and creates a second publication authority. A self-hosted open-source container adds server cost, patching, uptime, and monitoring without helping users because V0.1 exports a static site.
- **North Star check:** Cloudflare receives compiled static pages and ordinary request metadata only—not Supabase data, Gemini credentials, or search queries. Immutable release checks and V0.1 human confirmation remain authoritative.

## Implementation boundary

This approval permits creating a Direct Upload Pages project and uploading the validated fixture-based static artifact to a public Cloudflare preview URL. It does not approve DNS changes, production Supabase, real-source collection, Gemini calls, encrypted production backups, analytics, telemetry, or live automatic publication. GitHub Actions remains the only intended deployment authority; Cloudflare Git integration must stay disabled.

The existing Cloudflare account may be reused because this preview has no Pages Functions and therefore does not consume the account's Workers request allowance. It uses one account-level Pages project slot. The deployment token is limited to the selected account plus Cloudflare Pages Write only; it receives no Workers, DNS, R2, billing, or membership permission. Because Pages Write is account-scoped rather than project-scoped, the existing Pages-project inventory must be checked before the token is created.
