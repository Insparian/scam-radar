# Dedicated Cloudflare Free account — activation plan

Decision [015](../../DECISIONS/015-isolated-cloudflare-free-account.md) separates Scam Radar from Rui's existing Cloudflare account, which also runs unrelated Workers. The dedicated `Scam Radar` account was created after Rui's approval; its Billing page shows `Workers Free` active and no payment method. No Pages project, Worker, KV namespace, or other cloud resource has been created in it. This plan does not authorize deployment, transfer, backup upload, or DNS changes.

| Account | Job | Why it exists |
| --- | --- | --- |
| GitHub `Insparian/scam-radar` | Open-source code, CI, and bounded batch jobs | Reproducible builds and human-reviewed changes; GitHub Actions is not the public website or backup store. |
| Supabase Free, Frankfurt | Database and reviewer authentication | Stores approved patterns, evidence, audit, and release state; Free has no managed daily backup. |
| Dedicated Cloudflare Free account, same login | Planned Scam Radar Pages, two scheduled Workers, one private KV namespace | Will serve static site and provide independent free clock and encrypted backup destination. Separating account protects unrelated Workers, KV quotas, and account-level API permissions. Workers KV Free is inside this Cloudflare account; no separate KV login. |
| Existing Cloudflare account | Other projects only | Existing Scam Radar preview projects remain here until a separately approved move; do not alter other Workers or KV namespaces. |
| Alibaba Bailian, Beijing | Free-quota Qwen model after real-data approval | AI extraction/classification; account is set to free-quota-only stop, not a paid fallback. |
| Namecheap | `insparian.com` DNS | Only after a verified production Pages target and exact DNS approval. |

The new account ID is recorded in `config/cloudflare-account.json` as `dedicated_account_id`, and both `cloudflare/scheduler/wrangler.toml` and `cloudflare/backup-scheduler/wrangler.toml` point to that exact ID. Tests reject a mismatch. The Worker configs now target only the new account, but any Worker deployment or `wrangler secret put` still needs separate final approval. Pages and KV write paths check the reviewed ID separately. Existing `CLOUDFLARE_ACCOUNT_ID` secrets from the shared account must not be copied to new environments. Create new account-scoped tokens with only Pages or KV permissions needed for their job; the KV API permission is account-level, so isolation is essential.

Create new public and reviewer Pages projects in the dedicated account only after approval. Verify the reviewer Access policy blocks unauthenticated requests before uploading any reviewer build; deploy the exact tested fixture artifact; verify Access again. Do not delete the old previews until the new ones are verified and their removal is separately confirmed. Then update preview and production GitHub environment account IDs and tokens. Keep collection, AI, backup, and public production switches off throughout transfer.

Workers: the collection dispatcher and backup dispatcher are separate, each holds only its own GitHub Actions-write token for this repository. Neither holds Supabase, model, Pages, or KV credentials. Worker creation, secrets, and enabling Cron each need final activation approval. Two Cron triggers leave room under the Free account limit of five, subject to checking the new account's current limits and plan at activation.

The backup workflow uses `age` before its private KV upload. It writes 16 MiB immutable chunks plus a verified manifest, with a hard 64 MiB ciphertext cap per backup. KV Free has a 25 MiB per-value limit, 1 GB per-account storage, and 1,000 writes/day. It has no approved deletion/retention policy yet; without one, space eventually fills and backup stops. Treat this as an open launch gate, not a solved backup. A real restore into an independent database, recipient custody, observed backup size, retention and usage alerts need separate approval and validation before live data.

Cloudflare Free does not provide guaranteed mainland-China delivery. Test three mainland networks, mobile platforms and WeChat after publication; decide on any mainland host only from measured failure. No Aliyun paid host or ICP work is authorized by this decision.

[Cloudflare additional Free accounts](https://developers.cloudflare.com/fundamentals/account/create-account/) · [KV limits](https://developers.cloudflare.com/kv/platform/limits/) · [Workers limits](https://developers.cloudflare.com/workers/platform/limits/) · [KV API write](https://developers.cloudflare.com/api/resources/kv/subresources/namespaces/subresources/values/methods/update/)
