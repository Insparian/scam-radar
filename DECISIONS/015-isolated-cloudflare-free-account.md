# Decision 015 — Isolate Scam Radar in a Cloudflare Free account

- **What:** Put Scam Radar Pages, scheduled Workers, and proposed encrypted KV backup in a dedicated Cloudflare Free account under Rui's existing login.
- **Why now:** The current shared account runs unrelated Workers and contains unrelated KV namespaces; Scam Radar has not launched publicly, so account isolation can be established before production traffic.
- **Problem it solves:** Rui needs Scam Radar's credentials, usage limits, and configuration changes to avoid affecting other products in the shared account.
- **Alternative considered:** Keep Scam Radar in the existing account with project prefixes and narrow tokens. This is simpler, but KV and Cron limits and KV write permissions remain account-wide.
- **North Star check:** A separate free account preserves the free-only constraint and lowers the blast radius. It adds a one-time preview migration and verification step before launch.

Rui replied `proceed` on 2026-10-07. This authorizes offline design, code, and verification. Creating an account or other cloud resources, moving previews, uploading real backups, collection/model calls, production changes, deployment, and DNS each retain their separate final activation gates. The dedicated account ID must be reviewed and bound to deployment before any Cloudflare write.
