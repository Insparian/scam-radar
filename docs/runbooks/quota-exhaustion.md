# Quota exhaustion

## Principle

Quota loss slows new analysis; it must not weaken evidence rules, buy capacity, switch providers, or alter the current public site.

## Gemini quota

1. Stop new calls at the checked cap and set/keep AI disabled if repeated calls could worsen the incident.
2. Leave affected items `pending_ai`; do not mark them irrelevant or failed evidence.
3. Continue collection only if it is healthy and within storage limits. Collection may run in degraded mode without AI.
4. Missing/uncertain model outputs never make a candidate safer. If a deterministic policy input depends on an unavailable confidence signal, downgrade an otherwise-safe candidate to `review_required`; do not invent confidence or authorize publication.
5. Record counts, oldest pending age, provider/model, cap reached, and reason code—never full payloads.
6. Do not automatically purchase, upgrade, change provider/model, or use a personal key.
7. When quota is healthy, resume oldest high-trust Tier A/B items first under a reduced cap. Cached content/behavior hashes must prevent repeat billing.
8. Confirm pending age falls and the prior public `release_id` stayed unchanged unless a separately authorized release was deployed.

## Other limits

- GitHub Actions minutes/concurrency: keep the backlog, use manual recovery only after capacity returns, and prevent overlap with the database lease.
- Supabase storage/database limits: pause collection before data integrity is at risk; do not add destructive retention. Review table sizes and create a separate retention decision.
- Cloudflare upload limits: keep production unchanged, inspect artifact size/file count, and reduce only reproducible build output—not public evidence or audit data.

Environment caps may lower checked-in hard maxima. Raising a hard maximum, adding paid capacity, or creating another external service needs a new decision and Rui approval.
