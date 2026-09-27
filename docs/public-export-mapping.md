# Database v2 → public presentation

`worker/src/scam_radar/storage/public_export.py` is the only database presentation
adapter. It consumes one exact trusted RPC export, preserves release identity and
SQL manifest hash, and never loads fixture copy. The website validates every
presentation field before generating pages or indexes.

| Public field | Immutable revision/export source |
| --- | --- |
| Identity, names, risk/legal/evidence wording, summary | Same named revision fields |
| Immediate action | First reviewed `what_to_do` value |
| Mechanism introduction | Reviewed `hooks`, joined without added assertions |
| Mechanism steps | Reviewed pressure tactics, requested actions, money paths; deduplicated in order |
| Warnings, protection, regions, aliases | Same named revision arrays |
| Categories | Reviewed `pattern_type` |
| Search terms | Name, aliases, hooks, requested actions, phrases, channels, impersonated identities |
| Heat | Pinned snapshot points, checked sum; deterministic band and 30-day attention window |
| Timeline | Pinned evidence dates and summaries, without inferring materiality |
| Evidence and freshness | Pinned release evidence; conservative oldest verification |

Missing mechanism/actions, null required fields, unexpected Heat shape or release
identity fail. Unknown dates are not replaced with collection or current dates.
SQL approval and immutable-manifest checks remain authoritative; this mapping
cannot authorize a draft. Protocol/SQL end-to-end tests remain required separately.
