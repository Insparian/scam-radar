# 骗局雷达 / Scam Radar V0.1

## Implementation Brief — Scam Intelligence Engine & Public Database

**Status:** Implementation baseline amended 2026-08-16; external activation still requires Rui approval
**Owner:** Insparian  
**Primary market:** 中国大陆  
**Primary users:** 中老年人，以及替父母查询、核实和转发信息的成年子女  
**Public domain:** `https://scamradar.insparian.com`  
**Repository / project name:** `scam-radar`  
**Infrastructure target:** approximately `$0/month` during V0.1  
**Document date:** 2026-08-15

---

## Governing 2026-08-16 architecture amendment

`docs/North Star.md` is authoritative. This amendment and [ADR-007](docs/decisions/007-policy-engine-human-exception.md) supersede every sentence below that describes human review as a permanent mandatory architecture stage.

The required publication architecture is:

```text
Scam Intelligence Engine
         ↓
Deterministic Policy Engine
         ↓
  ┌──────┴──────────────┐
  ↓                     ↓
safe_to_automate   review_required
  ↓                     ↓
policy verification  human decision
  └──────────┬──────────┘
             ↓
immutable verified revision
             ↓
exact immutable public release
             ↓
Public Database (static artifact)
```

V0.1 runs `safe_to_automate` in shadow mode. It records what the deterministic rules would have authorized, but `live_auto_publish_enabled` remains false and a human still confirms publication. This temporary confirmation is a rollout control, not the permanent architecture. Live automatic authorization requires a later explicit decision for a narrow policy class after measured live-data performance, plus a database allowlist entry binding its exact `policy_version`, `policy_hash`, and `gate_version`; a boolean switch is never sufficient.

Model confidence never grants or increases publication authority. Low or missing confidence may only downgrade an otherwise eligible safe candidate to `review_required`. High confidence cannot upgrade a candidate, override the Evidence Gate, or turn `blocked` into a publishable state.

Time semantics are locked:

- `pattern_evidence.last_verified_at` is the actual evidence-check time;
- `pattern_revisions.verified_at` is the internal policy/human verification time;
- `public_releases.published_at` is when the revision is frozen into an immutable public-release manifest; Cloudflare deployment time is separate; and
- public `pattern.last_verified_at` is the minimum verification time across evidence supporting the current revision's claims.

Evidence can be rechecked after a revision decision. Therefore `pattern_evidence.last_verified_at` and `pattern_revisions.verified_at` are independently meaningful and have no required order relative to each other; both must be present and no later than the release manifest freeze.

Both policy and human paths use the same Evidence/Publish Gate, immutable revision, publication-change, exact-release, audit, rollback, and same-`release_id` boundaries. Policy decisions and human events retain distinct provenance; automation never impersonates a reviewer.

---

## 0. Codex execution directive

This document is the build authority for V0.1. Codex should make the reasonable implementation defaults stated here and should not stop for product questions already decided below.

Before writing application code:

1. Inspect the repository and every applicable `AGENTS.md`.
2. If the repository has no root `AGENTS.md`, create it first from the rules in §6.
3. Record any proposed dependency, its purpose, maintenance status, and lighter alternative before adding it.
4. Keep all work offline and fixture-based until the external-activation checkpoint in §24.
5. Do not create cloud projects, modify DNS, deploy publicly, crawl real sources, or send source text to Gemini until Rui explicitly approves that activation step.
6. After each implementation slice, run the proportionate tests and report in Chinese: what changed, why, user impact, and verification result.
7. Do not push automatically. At handoff, ask whether Rui wants to sync the repository across devices.

Here, “offline” means the application must not contact real sources, Gemini, production Supabase, Cloudflare, DNS, or telemetry. After the required dependency review, bootstrap may download pinned packages or containers from approved official registries.

If an existing repository rule conflicts with this brief, stop and show the exact conflict. Otherwise, proceed in the task order in §24.

---

## 1. Product definition

### 1.1 North Star

骗局雷达不是诈骗新闻网站，也不是 AI 自动写稿的网站。

It is a **Scam Intelligence Engine** that continuously turns selected trustworthy public reports into a searchable, evidence-backed memory of scam patterns.

It must answer two questions:

> **最近出现的骗局里，哪几个最值得提醒爸妈？**

> **我现在遇到的这件怪事，像不像已经知道的骗局？**

The product has two permanent capabilities:

- **Radar:** discover a new scam pattern or a material change to an old pattern.
- **Memory:** consolidate repeated reports into one traceable canonical record that remains searchable over time.

### 1.2 V0.1 user promise

A user should understand within roughly 60 seconds:

- 这是什么；
- 为什么危险；
- 最明显的 warning signs；
- 现在先做什么；
- 最近为什么值得注意；
- 这些结论来自哪里；
- 这条记录所依赖的信息最保守核实到什么时候。

### 1.3 Core product hypothesis

V0.1 validates one question:

> Can a free, scheduled pipeline compress hundreds of public-source items into a small, high-quality exception queue and a useful public scam-pattern database without publishing unsupported claims?

The key technical outcome is **Attention Compression**:

```text
hundreds of public items
          ↓
dozens of relevant items
          ↓
a handful of candidate patterns or material updates
          ↓
deterministic Policy Engine routing
          ↓
only exceptions consume human attention
```

The success metric is not article volume. A day with no genuinely important alert is an acceptable and trustworthy outcome.

### 1.4 Fundamental data unit

The public unit is a **Scam Pattern**, not an article.

```text
Scam Pattern
├── canonical name
├── aliases
├── mechanism and warning signs
├── protective actions
├── evidence and updates
├── evidence level
└── Scam Heat history
```

Ten articles may describe one pattern. Those articles are evidence or updates; they must not become ten public pages.

### 1.5 Two public risk types

V0.1 must distinguish:

- `confirmed_scam`: a scam, fraud, illegal activity, or criminal case supported by the required evidence.
- `risk_alert`: a high-risk consumer or financial pattern that a regulator or other authoritative body warns about but that should not automatically be described as a criminal scam.

The UI and copy must never collapse both into the same “诈骗已确认” label.

---

## 2. Locked V0.1 decisions

These are product constraints, not suggestions.

| Decision | V0.1 rule | Why / user impact |
|---|---|---|
| Market | 中国大陆 only | Keeps source, legal, language, and action guidance coherent. |
| Language | Simplified Chinese public UI | Matches the primary audience. Code and identifiers remain English. |
| Audience | 中老年人 + 成年子女 | Determines large-text mobile UX and family-sharing copy. |
| Source strategy | Allowlisted trusted sources only | Accuracy matters more than coverage. |
| Initial source count | Enable 5 stable collectors first; grow to 15–25, then at most 30–50 after validation | Prevents parser noise from hiding core product failures. |
| Schedule | Three batch runs per day | The job is periodic, not a real-time service. |
| Hosting | GitHub Free + GitHub Actions + Supabase Free + Cloudflare Pages Free + Gemini free tier | Validates value before paying for infrastructure. |
| Server | No VPS and no always-on backend | Removes server maintenance and idle cost. |
| Database | Supabase PostgreSQL | Supports JSONB, relational evidence, auditability, search, and future vector work. |
| Frontend | Next.js static export on Cloudflare Pages | Preserves the agreed stack without introducing an SSR runtime. |
| Worker | Python batch pipeline in GitHub Actions | Natural fit for crawling, parsing, evaluation, and scheduled work. |
| AI | Gemini behind a provider interface | Free first; no architecture-level vendor lock-in. |
| Truth | Evidence Gate, never the LLM or Heat score | Prevents confident but unsupported accusations. |
| Priority | Deterministic Scam Heat computed by code | Makes ranking explainable and testable. |
| Publication | Deterministic Policy Engine; human by exception; `safe_to_automate` shadow-only in V0.1 | Compresses human attention without letting AI or unsupported certainty gain authority. |
| Search | Exact, alias, and keyword matching first | Safer than an AI chatbot making a binary fraud judgment. |
| Raw content | Do not permanently store full HTML | Protects the free database quota and reduces copyright/security risk. |
| Distribution | Social video generation and publishing are outside V0.1 | Build the intelligence engine before the loudspeaker. |

Two rules must remain separate everywhere in code and UI:

> **Hot ≠ True.** Heat answers “is this worth attention now?”

> **News ≠ Scam.** An article is evidence; a Scam Pattern is the product record.

---

## 3. Scope

### 3.1 In scope

- A version-controlled trusted Source Registry.
- Scheduled collectors for public, allowlisted sources.
- URL normalization, text extraction, hashing, exact deduplication, and conservative semantic duplicate proposals.
- Relevance classification for scams and elderly-targeted high-risk schemes.
- Schema-constrained structured extraction.
- Candidate retrieval and Scam Pattern matching.
- Evidence origin / syndication grouping so copied reports count once.
- Evidence Gate levels A–D with machine-readable reason codes.
- Deterministic Scam Heat 0–100 with component breakdown.
- A small authenticated exception Review Queue plus shadow-confirmation view.
- Human exception actions: create pattern, approve update, merge, reject, hold for evidence, edit, archive, and unpublish.
- Append-only, distinct policy-decision and human-event audit trails.
- A public database with home, detail, and search surfaces.
- Source links, conservative last-verified dates, release published-at, evidence wording, and clear uncertainty.
- Offline fixture demo, Gold Set evaluation, CI, scheduled collection, and static deployment.
- Operational summaries, quota protection, kill switches, and failure runbooks.

### 3.2 Explicit non-goals

V0.1 does **not** include:

- native app;
- user accounts on the public site;
- comments, forums, voting, community, or user submissions;
- victim case management or fund-recovery services;
- individual phone number, bank account, wallet, URL, or message “scam checker”;
- AI chat or a chatbot that declares whether a situation is fraud;
- whole-web or real-time crawling;
- active collection from 微信、视频号、微博、小红书、抖音、贴吧、论坛、微信群、公众号 or private communities;
- authenticated scraping, paywall bypass, CAPTCHA solving, proxy rotation, or anti-bot evasion;
- automatic public accusation of a person, company, or product;
- live unattended publication in V0.1; the architecture and shadow records must still support a later narrowly activated safe policy class;
- push notifications, newsletters, personalization, recommendations, or public API;
- video generation, AI presenter, AI short drama, text-to-speech, or social copy generation;
- video号、小红书、抖音 or any other social-platform publishing automation;
- analytics, ad tracking, affiliate links, advertising, or monetization;
- multilingual or overseas scam coverage;
- map, graph analysis, trend prediction, or investigator-grade case tools;
- semantic public search or embeddings as a launch dependency;
- paid fallback infrastructure or automatic upgrade from a free tier.

Absence from the database must never be presented as proof that something is safe.

---

## 4. System architecture

### 4.1 End-to-end flow

```text
Versioned Trusted Source Registry
                 ↓
GitHub Actions — three scheduled runs/day
                 ↓
      Discover → Fetch → Normalize
                 ↓
      URL / content deduplication
                 ↓
          Supabase source_items
                 ↓
     Gemini relevance classification
                 ↓
       Gemini structured extraction
                 ↓
 Existing-pattern candidate retrieval
                 ↓
 Gemini schema-constrained comparison
                 ↓
       New Pattern / Pattern Update
                 ↓
            Evidence Gate
                 ↓
     Deterministic Scam Heat v0.1
                 ↓
      Deterministic Policy Engine
                 ↓
       ┌─────────┴─────────┐
       ↓                   ↓
 safe_to_automate     review_required
       ↓                   ↓
 policy verification   human decision
       └─────────┬─────────┘
                 ↓
      Immutable verified snapshot
                 ↓
 Next.js static export → Cloudflare Pages
                 ↓
       scamradar.insparian.com
```

No component runs continuously. GitHub Actions runners start, work, persist state to Supabase, and disappear.

### 4.2 Infrastructure responsibilities

| Component | V0.1 responsibility | Must not do |
|---|---|---|
| GitHub Free | Repository, Issues, review, history | Store secrets in code |
| GitHub Actions | CI, three daily batch runs, live eval, static build and Pages deployment | Serve user requests or retain local state |
| Supabase Free | PostgreSQL system of record, Auth, RLS, policy/human RPCs, immutable decision provenance, trusted release export | Crawl sites or expose privileged keys to browsers |
| Gemini free tier | Relevance, extraction, pattern comparison; optional embedding interface | Establish truth, set final Heat, determine policy eligibility, verify, or publish |
| Cloudflare Pages Free | Serve the static public and admin frontend | Hold the Supabase secret key or Gemini key in browser assets |
| `scamradar.insparian.com` | Canonical public URL | Change the `insparian.com` apex site |

### 4.3 Frontend deployment decision

Use Next.js App Router with static export (`output: 'export'`). Do not use SSR, Next.js route handlers, server actions, Pages Functions, or a full-stack runtime in V0.1.

Required static constraints:

```js
{
  output: "export",
  trailingSlash: true,
  images: { unoptimized: true }
}
```

Do not use cookies or request-dependent rendering, ISR, Server Actions, dynamic APIs, or runtime database calls for public pages. `/scam/[slug]` implements `generateStaticParams()` and `dynamicParams = false`. Admin Auth is client-only, includes a static `/admin/auth/callback` PKCE page, and every `/admin` page emits `noindex` metadata.

Reason:

- Cloudflare Pages supports static Next.js exports.
- Full-stack Next.js would move the project toward Cloudflare Workers, which is outside the locked V0.1 infrastructure.
- Public data changes only through a verified immutable release, so rebuilding a static snapshot is acceptable.

Publication behavior:

1. Policy or human verification creates an immutable verified `pattern_revision`; later edits must create and verify another revision. V0.1 shadow-safe candidates still require authenticated human confirmation.
2. A transactional `prepare_public_release()` copies the last deployed release manifest, applies authorized verified revisions/unpublishes, pins one Heat snapshot and evidence-freshness snapshot per pattern, and returns an immutable `release_id`.
3. A trusted exporter fetches that exact release into local JSON and then drops its database secret; `generateStaticParams()` reads only the JSON, and `dynamicParams = false` makes the available detail routes explicit.
4. `deploy.yml` embeds `release_id`, builds that exact release into static pages, and deploys it to Pages.
5. The production upload makes static pages and the same artifact’s local search index public together. After smoke tests, `record_deployed_release(release_id, deployment_id)` records what is already live; a failed record step enters reconciliation rather than pretending the upload did not happen.
6. Code merged to `main` also runs CI and redeploys the currently active content release with the new code.
7. The collection workflow checks for authorized verified revisions/unpublishes not yet included in the deployed release and for deterministic freshness-decay changes that alter public Heat ordering; it prepares and deploys a new release when needed. Maximum normal content lag is therefore one collection interval; `workflow_dispatch` supports an urgent manual publish/unpublish.

The admin UI must show `safe_to_automate`, `review_required`, or `blocked` plus policy version/reasons and clearly distinguish “已验证，等待发布” from “已公开”. It must not imply instant publication. Static pages and local public search must always come from the same immutable `release_id`, never from mutable draft rows.

### 4.4 AI provider boundary

Define a provider-neutral interface:

```python
class LLMProvider(Protocol):
    def classify(self, request: ClassificationRequest) -> ClassificationResult: ...
    def extract(self, request: ExtractionRequest) -> ExtractionResult: ...
    def compare_patterns(self, request: PatternComparisonRequest) -> PatternComparisonResult: ...
    def embed(self, texts: list[str]) -> list[list[float]]: ...
```

V0.1 implements `GeminiProvider`. Production model IDs come only from versioned `config/models.yaml`; they are not scattered through code or silently overridden in GitHub settings. A local/manual live eval may request an override, but its report must record the different behavior hash. `embed()` exists for portability, but embeddings remain disabled by default until lexical matching failures justify them.

### 4.5 Required accounts

Only these external accounts are needed:

- GitHub;
- Supabase;
- Cloudflare;
- Google AI Studio / Gemini API.

No VPS, Railway, Redis, queue service, object storage, or additional hosting account is required.

---

## 5. External data flows

These flows must be shown to Rui again before the first live run:

| From | To | Data sent | Purpose |
|---|---|---|---|
| GitHub Actions runner | Registered public source sites | URL, request headers, runner IP, request timing | Collect allowed public pages |
| GitHub Actions runner | Gemini API / Google | Bounded, cleaned public-source text plus extraction prompt | Classification and structured extraction |
| GitHub Actions runner | Supabase | Source metadata, cleaned relevant text, hashes, AI outputs, evidence, scores, job logs | Persist system state |
| Human exception browser | Supabase | Auth session, exception decisions, and V0.1 shadow confirmations | Verify exception records without exposing private data |
| GitHub Actions runner | Cloudflare Pages | Compiled static web assets | Deploy website |
| Public browser | Cloudflare | Page, asset, and immutable static search-index requests | Serve and search one public release |

Rules:

- Do not send secrets, reviewer notes, auth tokens, or unrelated content to Gemini.
- Redact obvious victim PII before Gemini calls.
- Public search runs locally against the deployed release index; do not transmit or retain search text.
- Do not add analytics, error telemetry, or another network SDK without separate approval.
- Logs contain counts, IDs, versions, and reason codes, not full article bodies or personal data.

---

## 6. Repository contract

### 6.1 Required structure

```text
scam-radar/
├── AGENTS.md
├── README.md
├── SCAM_RADAR_V0_1_IMPLEMENTATION_BRIEF.md
├── .editorconfig
├── .env.example
├── .gitignore
├── Makefile
│
├── .github/
│   └── workflows/
│       ├── ci.yml
│       ├── collect.yml
│       ├── deploy.yml
│       ├── migrate-production.yml
│       └── eval-live.yml
│
├── web/
│   ├── app/
│   │   ├── page.tsx
│   │   ├── scam/[slug]/page.tsx
│   │   ├── search/page.tsx
│   │   └── admin/
│   │       ├── review/page.tsx
│   │       ├── patterns/page.tsx
│   │       ├── sources/page.tsx
│   │       └── raw-items/page.tsx
│   ├── components/
│   ├── lib/
│   │   ├── public-data/
│   │   ├── review/
│   │   ├── supabase/
│   │   └── generated/database.types.ts
│   ├── public/
│   └── tests/
│
├── worker/
│   ├── pyproject.toml
│   ├── uv.lock
│   ├── src/scam_radar/
│   │   ├── cli.py
│   │   ├── settings.py
│   │   ├── collectors/
│   │   ├── normalize/
│   │   ├── dedup/
│   │   ├── llm/
│   │   ├── extraction/
│   │   ├── matching/
│   │   ├── evidence/
│   │   ├── scoring/
│   │   ├── review/
│   │   ├── storage/
│   │   └── observability/
│   └── tests/
│       ├── unit/
│       ├── integration/
│       └── fixtures/
│
├── supabase/
│   ├── config.toml
│   ├── migrations/
│   ├── seed.sql
│   └── tests/
│
├── config/
│   ├── sources.yaml
│   ├── sources.schema.json
│   ├── taxonomy.yaml
│   ├── scoring-v0.1.yaml
│   └── models.yaml
│
├── prompts/
│   ├── relevance-v1.md
│   ├── extraction-v1.md
│   └── pattern-match-v1.md
│
├── contracts/
│   └── schemas/
│       ├── relevance-v1.json
│       ├── extraction-v1.json
│       └── pattern-match-v1.json
│
├── evals/
│   ├── README.md
│   ├── gold/
│   ├── fixtures/
│   ├── expected/
│   └── reports/
│
├── docs/
│   ├── architecture.md
│   ├── data-flow.md
│   ├── decisions/
│   └── runbooks/
│       ├── initial-setup.md
│       ├── collection-failure.md
│       ├── false-positive.md
│       ├── quota-exhaustion.md
│       ├── deploy-and-rollback.md
│       ├── key-rotation.md
│       └── database-recovery.md
│
├── scripts/
│   ├── check_env.py
│   ├── run_fixture_demo.py
│   └── production_smoke.py
│
└── work/                       # ignored, disposable local artifacts only
```

### 6.2 Rules to put in root `AGENTS.md`

- Each directory has one documented responsibility; do not create parallel locations for the same concern.
- `config/sources.yaml` is the reviewed Source Registry source of truth. Runtime health state belongs in Supabase.
- `config/scoring-v0.1.yaml`, `config/models.yaml`, schemas, and prompts are versioned behavior files.
- Prompts are code: explain the expected behavioral change, then run evals. If an eval does not exist, create it before changing the prompt.
- Model-specific patches live separately; do not contaminate the provider-neutral prompt.
- `web/lib/generated/database.types.ts` is generated, committed, and never edited by hand.
- Store database timestamps in UTC; localize only in the UI.
- Do not commit secrets, `.env` files, full production pages, real production database dumps, build output, caches, or `work/`.
- Do not permanently store raw HTML, screenshots, images, audio, or binary responses.
- Every dependency addition needs a short ADR or PR note: purpose, maintenance status, lighter alternative, and user/runtime impact.
- All migrations are forward migrations. No destructive production migration without an explicit backup and Rui confirmation.
- Commit messages are concise English descriptions of intent.
- Codex does not push, deploy, change DNS, or perform irreversible actions without authorization.

### 6.3 Stable local commands

The root `Makefile` should hide tool-specific details:

```text
make bootstrap        # install pinned local dependencies
make check            # format, lint, typecheck, fast tests
make test             # complete offline test suite
make eval             # recorded-response Gold Set evaluation
make demo             # end-to-end fixture demo; no network
make web              # local web UI with fixture/local Supabase data
make collect-dry-run  # fixture collector; no writes to production
```

All commands must work from the repository root and be documented in `README.md`.

---

## 7. Source Registry

### 7.1 Registry tiers

Use the conversation’s trust model:

- **A1 — enforcement / justice:** police, courts, procuratorates, official anti-fraud bodies.
- **A2 — regulators / public authorities:** financial regulation, market regulation, consumer protection, securities regulation, and relevant public agencies.
- **B — high-trust media:** established outlets with attributable original reporting and clear sourcing.

V0.1 does not actively collect Tier C social or community signals. The schema may reserve `C`, but it must be disabled and cannot satisfy the Evidence Gate.

### 7.2 Initial candidate registry

The initial registry should contain 15–25 reviewed candidates, all disabled by default until their exact entry URL, access policy, and fixture test are verified.

Priority candidate groups:

**A1**

- 公安部；
- 北京、上海、广东、浙江、江苏、山东、福建、湖南、四川、重庆公安机关中页面稳定的反诈 / 典型案例栏目。

**A2**

- 国家金融监督管理总局及 selected local bureaus；
- 国家市场监督管理总局；
- 中国消费者协会；
- 中国证监会及 selected local bureaus；
- other official authorities only when their remit and relevant alert section are clear.

**B**

- 新华社；
- 央视；
- 法治日报；
- 中国新闻网。

Enable only the first five sources for the first live milestone. Choose them by this order:

1. clear collection permission / no access restriction;
2. stable RSS, API, sitemap, or list structure;
3. high rate of relevant attributable cases;
4. parser reliability;
5. geographic and scam-type diversity.

Do not select provinces because they are assumed to have more fraud. Select them because the source structure is stable and useful, then expand based on measured yield.

### 7.3 Versioned registry shape

`config/sources.yaml` must validate against JSON Schema and contain no executable code or secrets.

```yaml
schema_version: 1

sources:
  - key: example-police-alerts
    display_name: Example Police Alerts
    publisher_group: example-police
    source_type: police
    authority_tier: A1
    languages: [zh-CN]
    regions: [CN-XX]
    enabled: false

    collector:
      type: rss
      entry_url: https://example.gov.cn/alerts/feed.xml

    policy:
      terms_url: https://example.gov.cn/terms
      robots_url: https://example.gov.cn/robots.txt
      collection_allowed: true
      reviewed_at: 2026-08-15

    limits:
      first_run_lookback_days: 30
      max_items_per_run: 50
      min_request_interval_ms: 1500
      timeout_seconds: 20

    parser:
      config: {}
```

Unknown fields, duplicate keys, invalid URLs, unreviewed collection policy, or a missing fixture must fail validation.

### 7.4 Collector priority

Use the least fragile method available:

```text
RSS / Atom
   ↓
documented official API
   ↓
sitemap
   ↓
stable section/list page
   ↓
HTML polling
```

Search-engine results are not a primary ingestion source. No collector may bypass login, paywall, CAPTCHA, robots restriction, explicit terms restriction, or technical access control.

---

## 8. Collector and pipeline contract

### 8.1 Collector interface

Collectors only discover, fetch, and normalize. They do not call Gemini, calculate Heat, make evidence decisions, or publish.

```python
class Collector(Protocol):
    def discover(
        self,
        client: HttpClient,
        state: SourceState,
        config: SourceConfig,
    ) -> Iterable[DiscoveredItem]: ...

    def fetch(
        self,
        client: HttpClient,
        item: DiscoveredItem,
        config: SourceConfig,
    ) -> FetchResult: ...

    def normalize(
        self,
        item: DiscoveredItem,
        fetched: FetchResult,
        config: SourceConfig,
    ) -> NormalizedItem: ...
```

`NormalizedItem` contains:

```text
source_key
external_id | null
canonical_url
title
clean_text
published_at | null
author | null
language | null
allowlisted metadata
```

Shared infrastructure owns user agent, throttling, conditional requests, timeouts, response-size limits, retry policy, URL canonicalization, text normalization, hashing, and logs.

### 8.2 Normalization and identity

- Normalize Unicode consistently and collapse irrelevant whitespace.
- Remove navigation, footer, repeated chrome, tracking fragments, and boilerplate.
- Do not blindly drop every query parameter. Registry configuration declares meaningful parameters.
- Calculate:

```text
identity_key = reliable_external_id OR sha256(canonical_url)
content_hash = sha256(normalized_title + "\n" + normalized_clean_text)
```

- `raw_html_hash` may be stored for change detection; raw HTML itself is not persisted.
- Cap stored clean text and set `text_truncated=true` when capped. The extractor must know when it did not receive the full article.

### 8.3 Deduplication layers

1. Same normalized canonical URL and same content hash → exact duplicate.
2. Same normalized content hash across URLs → mirrored / syndicated candidate.
3. Highly similar recent content → semantic duplicate candidate.
4. Different articles describing the same case → same-event candidate.
5. Different cases sharing the same deceptive mechanism → same Scam Pattern candidate.

Never delete a duplicate record. Set `duplicate_of` or an origin group so the provenance remains auditable.

Three reposts of one Xinhua report count as **one evidence origin**, not three independent sources.

### 8.4 Per-run pipeline

For each run:

1. Validate and hash the Source Registry.
2. Acquire a Supabase lease and create a `pipeline_runs` record.
3. Sync the non-secret source configuration snapshot.
4. Process enabled sources independently.
5. Discover using cursor, ETag, or `Last-Modified` where available.
6. Fetch within source-specific and global limits.
7. Normalize; reject empty, unsupported, oversized, or malformed responses with a reason code.
8. Upsert the stable source item and insert an immutable content version before the AI step.
9. Skip repeated AI calls when `content_hash + model + prompt_version + schema_version` already succeeded.
10. Run relevance classification.
11. For relevant items, run structured extraction.
12. Retrieve likely existing patterns from name, alias, and structured features.
13. Run schema-constrained pattern comparison on a bounded candidate list.
14. Propose a new pattern, an update, a duplicate, or a needs-review match.
15. Evaluate Evidence Gate eligibility.
16. Calculate Scam Heat from versioned factual features.
17. Run the versioned deterministic Policy Engine and append one hashed `safe_to_automate`, `review_required`, or `blocked` decision.
18. Create or update one deduplicated exception Review Queue item. During V0.1 shadow mode, also queue a safe candidate for confirmation without changing its recorded policy outcome.
19. Revalidate a bounded batch of due accepted evidence URLs; a changed, corrected, withdrawn, or unavailable source blocks automation, creates a highest-priority `gate_regression` item, and never silently rewrites the accepted record.
20. Commit a source cursor only after that source completes successfully.
21. Write source-level and run-level summaries, including policy/shadow counts; release the lease.

### 8.5 Relevance contract

The first model answers only: “Should this item enter the scam pipeline?”

```json
{
  "relevant": true,
  "elderly_relevance": "high",
  "category": "financial_scam",
  "confidence": 0.94,
  "reason": "Targets retirees with a high-return养老 investment claim"
}
```

Relevant categories include fraud, telecom scams, impersonation, investment scams, fake customer service, fake shopping, illegal fundraising, deepfake-enabled scams, and elderly-targeted high-risk patterns such as health-product sales, free examination funnels,养老 projects, collectible buyback, prepaid养老, or misleading medical promotion.

`unknown` and `null` are valid. The model must not invent a value to fill the schema.

### 8.6 Structured extraction contract

Extract, when supported:

```text
suspected_pattern_name
target_population[]
contact_channels[]
impersonated_identity
hook
promise
pressure_tactics[]
requested_actions[]
money_path
credential_requests[]
technology_used[]
regions[]
victim_count
reported_loss
individual_loss
case_date
source_claim_type
official_status
warning_signs[]
recommended_actions[]
supporting_spans[]
```

Each factual field must be `null`, `unknown`, or linked to a short supporting span from the source. Model output remains a proposal until verified through the deterministic policy or human exception path.

### 8.7 Pattern comparison contract

Candidate retrieval happens before the LLM. Compare at most a configured top `K` (default 10).

```json
{
  "same_pattern": true,
  "confidence": 0.91,
  "reason_codes": [
    "same_impersonation",
    "same_pressure_tactic",
    "same_money_path"
  ],
  "material_change": true,
  "changes": ["new_offline_cash_pickup"]
}
```

The model may recommend a match but may not merge clusters. V0.1 routes all merge/split decisions to human review.

The comparison `input_hash` must cover the source-item-version content hash, model/prompt/schema versions, taxonomy hash, and the sorted candidate `pattern_revision_id + content_hash` values. A changed candidate revision invalidates an old comparison result even when the source article did not change.

### 8.8 AI failure behavior

- Validate every response against a versioned JSON Schema.
- Retry malformed structured output once.
- Retry transient `429`, timeout, and `5xx` responses within the global call cap and respecting `Retry-After`.
- On quota exhaustion, stop new AI calls, leave items `pending_ai`, and continue serving the last published public state. Missing confidence may only downgrade an otherwise safe candidate to review.
- Never switch automatically to a paid model or another provider.
- Treat all source text as untrusted data. Delimit it from instructions and ignore commands found inside pages.

---

## 9. Data model

### 9.1 General database rules

- PostgreSQL migrations under `supabase/migrations/` are the schema source of truth.
- Use `uuid` primary keys, `timestamptz` in UTC, lower `snake_case`, foreign keys, explicit indexes, and `CHECK` constraints.
- Prefer `text + CHECK` over PostgreSQL enums during V0.1 so migrations remain simple.
- JSONB is allowed only for schema-versioned model results, configuration snapshots, and score breakdowns.
- Every public write occurs through a narrow transactional RPC, not arbitrary browser table updates.
- Use optimistic `row_version` checks so a stale reviewer screen cannot overwrite newer evidence.

### 9.2 Core entities

#### `sources`

| Field | Purpose |
|---|---|
| `id`, `source_key` | Stable identity; key is never reused |
| `name`, `domain`, `publisher_group` | Display and evidence-origin grouping |
| `source_type` | `police`, `regulator`, `court`, `state_media`, `media` |
| `authority_tier` | `A1`, `A2`, `B`, reserved `C` |
| `ingestion_method`, `entry_url` | Collector selection |
| `enabled`, `poll_frequency` | Runtime eligibility |
| `parser_config`, `config_hash` | Versioned behavior snapshot |
| `created_at`, `synced_at` | Audit timestamps |

#### `source_items`

| Field | Purpose |
|---|---|
| `id`, `source_id` | Item identity and source |
| `external_id`, `identity_key` | Stable source identity |
| `canonical_url`, `current_version_id` | Current location and version pointer |
| `first_seen_at`, `last_seen_at` | Discovery history |
| `created_at`, `updated_at` | Audit timestamps |

Unique `(source_id, identity_key)`. This table is stable identity only; a source-page edit must not overwrite or masquerade as a new item.

#### `source_item_versions`

| Field | Purpose |
|---|---|
| `id`, `source_item_id` | Immutable content version identity |
| `url`, `canonical_url` | Provenance at fetch time |
| `title`, `author` | Source metadata |
| `published_at`, `fetched_at` | Source and collection time |
| `clean_text`, `text_truncated` | Bounded processable text |
| `content_hash`, `raw_html_hash` | Deduplication/change detection |
| `origin_group_key` | Syndication / common-origin family |
| `duplicate_of_version_id`, `supersedes_version_id` | Non-destructive relationships |
| `processing_status`, `attempt_count`, `last_error` | Pipeline state |
| `created_at` | Audit timestamp |

Unique `(source_item_id, content_hash)` plus a global `content_hash` index. Inserting a new version and advancing `source_items.current_version_id` occurs transactionally; old versions remain immutable.

#### `ai_artifacts`

Store one record per AI stage and version:

```text
id
source_item_version_id
stage                     # relevance / extraction / pattern_match / embedding
provider
model
prompt_version
schema_version
input_hash
status                    # pending / success / invalid / error
result jsonb
usage jsonb
latency_ms
error_code
created_at
```

Unique: `(source_item_version_id, stage, provider, model, prompt_version, schema_version, input_hash)`.

#### `scam_patterns`

```text
id
slug
lifecycle_status          # candidate / evidence_pending / review_ready / rejected / archived
current_draft_revision_id
latest_approved_revision_id # compatibility pointer; verification provenance is authoritative
first_seen_at
last_seen_at
row_version
created_at
updated_at
```

This is the stable identity and internal lifecycle row. It is not the public content authority. Private individuals and victim PII never belong in this table.

#### `pattern_revisions`

Each candidate/public snapshot is a numbered revision. Draft revisions may be edited; a verified revision is immutable by trigger and can only be superseded by a new revision.

```text
id
pattern_id
revision_no
schema_version
revision_status           # draft / approved / rejected; supersession is derived, not an update
canonical_name
short_name
pattern_type
risk_type                 # confirmed_scam / risk_alert
evidence_level            # A / B / C / D
legal_status              # warning / reported_case / enforcement / charge / judgment / unknown
public_evidence_label
one_sentence_summary
target_population[]
contact_channels[]
impersonated_identities[]
hooks[]
common_phrases[]
pressure_tactics[]
requested_actions[]
money_paths[]
technology_used[]
warning_signs[]
what_to_do[]
regions[]
first_seen_at
last_seen_at
last_material_change_at
evidence_set_hash
content_hash
created_by
created_at
verified_at
verification_path         # policy / human
verification_policy_decision_id
verification_review_event_id
approved_by               # compatibility human actor; null for future live policy path
approved_at               # compatibility human decision time
```

Verification must pin the exact public fields, legal wording, and evidence set. The human path requires `approved_by = auth.uid()` plus an enabled `admin_user`. The policy path requires a matching eligible append-only policy decision and an exact activated `policy_version + policy_hash + gate_version`; it never fabricates `approved_by`. V0.1's activation allowlist is empty and uses human confirmation.

`content_hash` is calculated from canonical serialization of the public fields, revision aliases, evidence set, and claim-support mappings. The verified-revision trigger rejects `UPDATE` and `DELETE`; correction always creates a new revision.

#### `scam_aliases`

```text
id
pattern_revision_id
alias
normalized_alias
alias_type
created_at
```

Unique normalized alias per revision. Searching “粮票回收”, “古董回购”, or “旧缝纫机回收” may all resolve to one canonical pattern, while an older approved release retains its exact prior alias set.

#### `pattern_evidence`

```text
id
pattern_id
source_item_version_id
evidence_type
origin_group_key
evidence_family_id
claim_summary
event_date
region
victim_count
loss_amount
new_tactic
new_channel
new_target
new_script
is_material_update
acceptance_status          # proposed / accepted / rejected
acceptance_path            # policy / human
acceptance_policy_decision_id
accepted_by
accepted_at
last_verified_at
recheck_due_at
source_status              # available / changed / corrected / withdrawn / unavailable
created_at
```

Unique `(pattern_id, source_item_version_id)`. `origin_group_key` groups copied/syndicated text; the separately reviewed `evidence_family_id` groups reports derived from the same underlying case, press disclosure, or factual origin. Only accepted, non-duplicate evidence families contribute to corroboration, public copy, or Heat.

#### `evidence_spans` and `evidence_claim_support`

`supports_fields[]` is not sufficient for claim-level traceability. Use relational mappings:

```text
evidence_spans
  id
  pattern_evidence_id
  start_offset
  end_offset
  excerpt                 # short, bounded, internal
  excerpt_hash

evidence_claim_support
  pattern_revision_id
  field_path              # e.g. warning_signs[1]
  value_hash
  pattern_evidence_id
  evidence_span_id
```

The Publish Gate verifies that every required non-null public value has at least one accepted mapping. Foreign keys, not UUID arrays, enforce integrity.

#### `policy_decisions`

Append-only rows record `rules_outcome`, effective `decision_outcome`, `shadow/live` mode, policy/config/input/content/evidence/candidate hashes, reason codes, Evidence Gate provenance, and whether model uncertainty caused a one-way downgrade. A policy decision is not a human review event, and a shadow-safe decision is not publication authority.

#### `review_items`

```text
id
review_type                # new_pattern / pattern_update / merge / evidence_change /
                           # public_copy / gate_regression / source_health
target_id
status                     # pending / in_review / needs_evidence / approved /
                           # rejected / merged
priority
heat_at_creation
evidence_level_at_creation
reason_codes[]
candidate_payload jsonb
candidate_hash
base_row_version
dedupe_key
assigned_to
decision_note
created_at
updated_at
resolved_at
```

A partial unique index on open `dedupe_key` prevents the same rerun from generating repeated exception tasks.

### 9.3 Supporting entities

- `pipeline_runs`: GitHub run ID/attempt, trigger, commit SHA, registry hash, versions, counters, timing, outcome, and redacted error summary.
- `source_states`: one mutable row per source containing cursor, ETag, `Last-Modified`, last attempt/success, consecutive failures, and last error. Registry sync must never overwrite this operational state.
- `source_run_results`: one row per source/run with duration, counts, retry/error category, and outcome; a successful source result is not lost because another source failed.
- `review_events`: append-only human actor/action/before/after/reason/timestamp audit. It remains distinct from `policy_decisions`; clients cannot update or delete either.
- `heat_snapshots`: pattern, score version, `as_of`, score, breakdown, input hash, and calculation time.
- `admin_users`: Supabase Auth user ID, role, enabled state. Authentication alone does not confer reviewer access.
- `publication_changes`: explicit publish/unpublish request plus `request_path` and optional `policy_decision_id`.
- `public_releases`: monotonically increasing release number, state (`approved`, `deploying`, `deployed_unrecorded`, `deployed`, `deploy_failed`, `superseded`), manifest hash, artifact hash, commit/deployment IDs, `published_at`, timestamps, and redacted error.
- `public_release_items`: immutable manifest mapping `(release_id, pattern_id)` to one `pattern_revision_id`, one `heat_snapshot_id`, and the conservative `last_verified_at` snapshot. An unpublish release omits the pattern.
- `public_release_evidence_items`: immutable per-release evidence freshness snapshots, so re-exporting an old `release_id` cannot change when evidence is rechecked later.

`prepare_public_release()` must copy the prior deployed manifest and apply only authorized verified revisions/unpublishes. A production deployment accepts one exact `release_id`; it never queries “whatever is currently verified” during the build.

### 9.4 Public data boundary

V0.1 has one public publishing plane: the immutable static release. A trusted export step reads one exact release and writes:

```text
work/release/<release_id>/public-release.json
work/release/<release_id>/search-index.json
```

Next.js reads those files without database credentials and emits home, detail pages, and the same release’s client-side search index. Public release schema v2 exposes conservative pattern/evidence `last_verified_at` and release `published_at` separately. Public browsers do not query Supabase. This prevents a newly verified record from appearing in search before its detail page exists and avoids sending user-entered search text to a third party.

The anonymous database role receives no table or function access. The Supabase publishable key exists in the static application only for the separately loaded admin authentication flow. Anonymous users cannot read `clean_text`, source records, AI results, queue items, reviewer notes, run errors, decision/audit events, or verified-pending revisions.

The system uses narrow provenance-specific RPCs such as:

```text
record_policy_decision(...)
apply_live_policy_publication(...)   # activation-gated off in V0.1
confirm_policy_publication(...)
merge_pattern_candidate(...)
reject_review_item(...)
hold_for_evidence(...)
archive_pattern(...)
unpublish_pattern(...)
```

`confirm_policy_publication(...)` is the only human publication/approval entry point and requires a matching non-blocked Policy Decision before touching evidence. The former direct `approve_new_pattern(...)` and `approve_pattern_update(...)` entry points are explicitly revoked for every API role so a reviewer cannot bypass Policy Engine routing. Each verification RPC must accept proposed evidence, run the same Publish Gate, freeze one immutable `pattern_revision`, verify hashes/`row_version`, and append the appropriate policy or human provenance in one transaction.

RLS and grants are mandatory on every exposed object:

- explicitly enable RLS on every exposed table;
- revoke default table/function access from `PUBLIC`, `anon`, and `authenticated`, then grant only what is required;
- use `security_invoker = true` for views;
- functions are `SECURITY INVOKER` by default;
- a necessary reviewer `SECURITY DEFINER` RPC must set `search_path = ''`, use schema-qualified names, and re-check `auth.uid()` against enabled `admin_users`;
- reviewers do not receive arbitrary table `INSERT`, `UPDATE`, or `DELETE` grants;
- export/deploy credentials are used only in trusted Actions steps and never placed in browser code.

---

## 10. Evidence Gate

Evidence and Heat are independent axes. The Evidence Gate decides what wording is supportable. It does not decide whether something is currently important.

### 10.1 Level A — Confirmed / authoritative

At least one of:

- **A1:** Police, court, or procuratorate explicitly describes the conduct as fraud, crime, illegal activity, or reports an enforcement action.
- **A2:** A competent national or local regulator explicitly identifies a pattern as fraud, illegal fundraising, unlawful activity, consumer trap, or regulated risk.
- Multiple official bodies independently confirm the same pattern.

Public wording must match the evidence:

- police report that explicitly describes fraud: `警方通报的诈骗案件`;
- court judgment: `司法机关已公开裁判`;
- regulator warning: `监管部门已提示风险`;
- do not turn a warning, investigation, enforcement action, charge, or regulator risk notice into a judgment or a broader claim of guilt.

Evidence strength and legal status are separate fields. An A-level source makes the record eligible for policy evaluation; it does not permit wording beyond the exact status supported by that source.

### 10.2 Level B — Corroborated

Two or more genuinely independent high-trust evidence origins support the same mechanism, but the available evidence is insufficient for a broader legal accusation.

Allowed wording, only when its specific condition is met:

- `近期多地出现类似套路` only with distinct accepted evidence families in distinct regions;
- `值得警惕的新型风险`;
- `多家可信来源报道了相似做法`.

Disallowed wording:

- `某公司就是骗子`;
- `警方已经确认` when the source does not say that;
- claims of national spread or rapid growth not directly supported by evidence.

### 10.3 Level C — Emerging

Only a single media item, user claim, social signal, or otherwise weak evidence.

- May remain internal for monitoring.
- Cannot be publicly labeled as a known scam.
- Cannot enter public Heat ranking.
- V0.1 has no public “rumor” or “emerging signal” page.

### 10.4 Level D — Rejected / insufficient

Examples:

- no original source;
- several URLs all repeat one origin and the origin is insufficient;
- contradictory core facts;
- sensational or unattributed claims;
- only marketing accounts or low-trust reposts;
- candidate is legitimate commercial activity or unrelated content.

Retain a minimal internal record and reason so the system does not repeatedly investigate the same item.

### 10.5 Evidence Eligibility Gate

A candidate may become `eligible_for_policy` when all are true:

1. Proposed evidence mechanically supports a provisional A or B outcome.
2. The cluster describes one coherent deceptive mechanism; shared keywords alone are insufficient.
3. Every proposed public factual value has at least one proposed source span and claim mapping.
4. Source identity, original URL, publication/fetch date, and inspectable text are present.
5. Copied/syndicated reports are grouped by `origin_group_key`, and reports derived from the same underlying case/disclosure are grouped by `evidence_family_id`; each family counts once.
6. Minimum public fields exist: neutral name, one-sentence summary, mechanism, warning signs, protective actions, channel/context, evidence list, and last-evidence date.
7. PII is removed or masked.
8. Wording distinguishes source fact, source allegation, and system synthesis.
9. No unsupported negative claim targets a person, company, institution, or product.

Machine-readable outcomes:

```text
eligible_for_policy
needs_more_evidence
blocked
duplicate
```

Required reason codes:

```text
insufficient_evidence
sources_not_independent
cluster_incoherent
claim_not_supported
source_unavailable
duplicate_pattern
sensitive_data
legal_or_attribution_risk
unsafe_detail
needs_merge_or_split
```

Gemini confidence, source count, embedding similarity, and Heat never substitute for these requirements. Model confidence is not a positive eligibility input.

### 10.6 Publish Gate

The policy and human verification RPCs perform the same second gate inside one transaction:

1. evidence acceptance has valid policy or human provenance, with independence/family grouping still satisfied;
2. the resulting accepted evidence still produces A or B;
3. every required non-null public value has an `evidence_claim_support` mapping to accepted evidence and a bounded source span;
4. `risk_type`, `legal_status`, and every public label are compatible;
5. all Heat input enums are evidence-supported and verified;
6. the candidate’s `row_version`, content hash, evidence hash, and policy/input hashes still match;
7. the exact snapshot is frozen as an immutable verified `pattern_revision` with `verified_at` and a policy or human verification path;
8. an append-only `policy_decision` or human `review_event` records distinct provenance.

Failure leaves the candidate unverified and returns a specific reason. No deployable revision exists until this transaction succeeds. In V0.1, a shadow decision cannot invoke the live policy transaction and must use authenticated human confirmation.

### 10.7 Deterministic Policy Engine

`config/publication-policy-v0.1.yaml` is versioned behavior and part of the eval behavior hash. The engine records:

```text
policy_version
policy_hash
candidate_hash
input_hash
rules_outcome          # safe_to_automate / review_required / blocked
decision_outcome       # may only be equally or more conservative
reason_codes[]
mode                    # shadow / live
model_confidence_downgrade
publication_authorized
```

The V0.1 safe class is limited to an existing public pattern's Evidence-A routine update with no material/public-copy change, complete verified claim support, and no named-entity risk, legal/evidence status change, source regression, merge, or split. First publication and Evidence B require review.

Only after that deterministic safe result may low or missing relevance/pattern-match confidence downgrade the effective outcome to `review_required`. Confidence is never evaluated as a reason to upgrade. Unknown policy version, missing input, hash mismatch, or unprovable condition fails closed.

---

## 11. Scam Heat v0.1

### 11.1 Meaning

Scam Heat is a 0–100 **attention-priority score**. It is not:

- probability that a claim is true;
- probability that a particular user will be scammed;
- a popularity ranking;
- a legal judgment;
- total social harm.

Only an Evidence A/B pattern may appear in public Heat ordering. Code computes the final score from versioned feature buckets; the LLM never returns the final number.

Before verification, the worker may display `provisional_heat` from extracted feature proposals. Only verified, evidence-supported features may update public `heat_score`; later freshness decay is automatic because it does not alter the underlying factual features.

Heat alone does not qualify an old record for current attention. Define:

```text
active_attention = evidence_level in (A, B)
                   AND last_material_change_at >= as_of - 30 days
```

Only `active_attention=true` records may enter “今天值得注意” or the active Heat ordering. Older records remain searchable and retain score history but are labeled `历史记录`. `last_material_change_at` uses the evidence-supported event date, never fetch, processing, or review time.

```text
Heat = Target Relevance + Freshness + Harm + Spread + Novelty
       0–30              0–20        0–20   0–15    0–15
```

### 11.2 Target Relevance — 30

| Evidence-supported feature | Points |
|---|---:|
| Explicitly targets people aged 60+ / older adults | 30 |
| Primarily targets retirees, pensions, or养老 funds | 27 |
| Broad adult target but older adults are clearly at higher risk | 20 |
| General adult population | 10 |
| Older-adult relevance is incidental but evidence-supported | 5 |
| No meaningful older-adult relevance | 0 |
| Unknown | 0 |

### 11.3 Freshness — 20

Calculate from the latest **material change**, not merely a new article:

| Age of material change | Points |
|---|---:|
| 0–3 days | 20 |
| 4–7 days | 16 |
| 8–14 days | 12 |
| 15–30 days | 6 |
| More than 30 days / unknown | 0 |

An old scam with a genuinely new technology, script, payment route, target, or contact channel receives a new material-change date. A routine new case does not automatically reset freshness.

### 11.4 Harm — 20

| Evidence-supported harm | Points |
|---|---:|
| Potential loss of most retirement savings, home/property, severe health/safety risk, or similarly irreversible harm | 20 |
| Typical evidenced individual loss in the tens of thousands to hundreds of thousands CNY, or account takeover | 15 |
| Typical evidenced loss in the thousands CNY | 10 |
| Mainly personal data, credential collection, nuisance, or early-stage grooming risk | 5 |
| Insufficient information | 0 |

Do not infer a typical loss from one unusually large headline case. Store the evidence used for the bucket.

### 11.5 Spread — 15

Count independent evidence origins, not URLs.

| Evidence-supported spread | Points |
|---|---:|
| National authority explicitly reports nationwide/multi-region spread, or independent evidence families show cases in at least 3 provinces | 15 |
| Independent cases in 2 provinces | 12 |
| Multiple cities with independent cases | 10 |
| Multiple cases in one region | 7 |
| Single case | 3 |
| Unknown | 0 |

### 11.6 Novelty — 15

| Change type | Points |
|---|---:|
| Genuinely new deceptive mechanism | 15 |
| Existing scam combined with materially new technology | 13 |
| Existing scam with a materially new script or execution step | 10 |
| Existing scam with new packaging only | 6 |
| Longstanding scam with a minor presentation variation | 3 |
| Longstanding unchanged common scam | 2 |
| Unknown | 0 |

The model may suggest a novelty bucket; code applies points only from a validated feature enum, and a human exception decision can override the feature before publication.

For every component, store a verified feature enum. If more than one row appears applicable, choose the first matching row from top to bottom and store the evidence IDs that justify it.

### 11.7 Display bands

| Heat | Internal/public label | Behavior |
|---|---|---|
| 80–100 | 🔴 值得立即关注 | Eligible for `Today Queue`; Heat grants no publication authority |
| 65–79 | 🟠 近期值得关注 | High exception-queue priority when review is required |
| 50–64 | 🟡 持续观察 | Database update; not prominent by default |
| <50 | ⚪ 数据库记录 | Retain; no active distribution |

The homepage shows at most three published items in “今天值得注意”. If none qualifies, omit the section.

### 11.8 Auditability

Every calculation stores:

```text
heat_version = scam-heat-v0.1
as_of
input feature values
component points
evidence IDs used
inputs_hash
final score
calculated_at
```

Same inputs and `as_of` date must always yield the same score. Recalculate when accepted evidence changes and at least daily so freshness decays naturally.

---

## 12. Policy routing, exception Review Queue, and admin

### 12.1 Admin surfaces

V0.1 admin has only:

- `Review Queue`;
- `Scam Patterns`;
- `Sources`;
- `Raw Items`.

It is not a general CMS. Policy routing happens before this surface; the human verifies exceptions and V0.1 shadow confirmations rather than writing a parallel article system.

Use Supabase email magic-link authentication and an explicit `admin_users` allowlist. Do not build password management, public registration, or role administration UI in V0.1.

### 12.2 Queue item display

One screen must show:

- proposed canonical name and public summary;
- new pattern vs existing match recommendation;
- Heat and five-component breakdown;
- a plain-language “为什么今天值得看”; 
- evidence level and exact allowed public label;
- every evidence item, authority tier, syndication origin, underlying evidence family/case, date, and original link;
- which public fields each evidence item supports;
- duplicate/syndication grouping;
- material changes;
- model comparison result, confidence, and reason codes;
- Policy Engine outcome, version/hash, reason codes, shadow/live state, and whether low/unknown model confidence caused a downgrade;
- extraction uncertainties and contradictory facts;
- PII, attribution, and legal-risk flags;
- public-page preview;
- model, prompt, schema, and processing versions.

### 12.3 Required reviewer actions

Primary actions from the agreed design:

- **Approve Update**;
- **Create New Pattern**;
- **Merge**;
- **Reject**.

Also support:

- edit proposed public fields before approval;
- hold for more evidence with a reason;
- change syndication origin and underlying evidence-family grouping;
- archive / supersede;
- urgent unpublish;
- correct and republish.

In V0.1, first publication, Evidence B, material/public-copy change, evidence-level or legal-status change, merge/split, source regression, negative claim involving a named organization, and any item entering the homepage route to explicit human decision. Model confidence may add review; it can never remove one of these reasons.

### 12.4 Queue state

```text
candidate
  ├── insufficient evidence → needs_evidence
  └── gate passes → Policy Engine
                     ├── blocked → no publication
                     ├── review_required → exception Review Queue
                     │                      ├── create / update / merge → immutable verified pattern_revision
                     │                      └── reject → rejected
                     └── safe_to_automate
                            ├── V0.1 shadow → human confirmation
                            └── future activated class → policy verification

verified pattern_revision
  → included in exact public_release
  → deploying
  → deployed_unrecorded → deployed
  └── deploy_failed

later revision / removal release → prior release superseded
```

All decisions record their correct provenance, timestamp, reason, source snapshot, and before/after content. Human events record an actor; policy decisions record policy/input hashes and never fake one. Verification applies to one immutable revision; a later material change requires another revision and policy routing. A database status change never claims that a static page has been removed before the corresponding release deploy completes.

### 12.5 Queue ordering

1. Published pattern whose gate has regressed.
2. Heat ≥80 candidate that passes the machine gate.
3. New A-level pattern.
4. Ambiguous merge/new-pattern decision.
5. Heat 65–79 material update.
6. Lower-priority evidence and source-health items.

Within a category: newest material evidence first, then A before B, then oldest waiting item.

The desired daily funnel after initial backlog is approximately:

```text
300–400 discovered items
25–40 relevant
5–10 candidate patterns
2–5 material changes
2–5 exception or shadow-confirmation items
```

These are product targets, not fabricated activity quotas.

---

## 13. Public website information architecture

V0.1 has three primary public surfaces. Do not add more navigation until usage proves a need.

### 13.1 Home `/`

First screen:

```text
最近有什么骗局值得提醒爸妈？

[ 搜索你遇到的可疑事情 ]
“百万保障 / 孙子出事 / 高价回收 / 免费体检……”
```

Then:

1. **今天值得注意** — maximum 3 published patterns; hide if empty.
2. **最近出现变化** — 5–10 recently verified material changes.
3. **常见骗局** — simple category entry points: 电话、微信、投资理财、养老、保健品、冒充亲友、客服、收藏品.

Pattern card content:

- attention label, not a sensational rank;
- canonical name;
- one-sentence mechanism;
- one immediate protective sentence;
- evidence label;
- last material update date.

### 13.2 Detail `/scam/[slug]`

The top of the page must answer “what, danger, action” before showing a timeline.

Required reading order:

1. status: Heat band, evidence label, conservative “信息核实至” date;
2. canonical name and aliases;
3. one-sentence explanation;
4. `现在先做什么` — immediate protective actions;
5. `骗子通常怎么开始` for `confirmed_scam`, or neutral `这种高风险做法通常如何开始` for `risk_alert`;
6. `接下来通常会发生什么` — 3–5 plain steps, with actor-neutral wording for `risk_alert`;
7. `最危险的信号`;
8. `如果已经遇到了怎么办`;
9. known cases and material-change timeline;
10. evidence sources with institution, date, original title, and original link;
11. clear separation between source facts and Scam Radar synthesis;
12. `Last Verified / 信息核实至`, separate release-published date, and correction/unpublish status. Public last-verified is the oldest supporting-evidence check, never the policy/human verification time.

Do not publish a complete operational playbook that would materially help scammers. Mask personal phone numbers, bank accounts, IDs, wallet addresses, access codes, and suspicious URLs.

Rendering must be conditional on both `risk_type` and `legal_status`. A `risk_alert` can never inherit confirmed-scam or criminal-adjudication copy merely because it has strong sources; enforce this with database and UI tests.

### 13.3 Search `/search`

V0.1 search order:

1. exact canonical-name match;
2. exact alias match;
3. normalized substring / keyword match over hooks, common phrases, channels, requested actions, and impersonated identities;
4. weighted fuzzy match only if it remains explainable and tested.

Examples:

```text
百万保障  → 假冒微信/保险客服骗局
孩子撞人了 → 冒充亲属紧急事故骗局
粮票      → 高价回收老物件骗局
```

At V0.1 scale, build a compact, versioned `search-index.json` from the same immutable release as the detail pages and run deterministic matching in the browser. Cap the query length, normalize it locally, and do not persist it. Chinese semantic search and embeddings come later only if direct user tests expose real failures.

The input helper must say `请只输入关键词，不要粘贴姓名、电话、账号或完整聊天记录`. The product accepts a local search query, not a victim report.

No-result state:

> 暂时没有找到相似的已知骗局。这不代表它一定安全。先不要付款、不要共享屏幕、不要提供验证码；通过你自己找到的官方号码联系相关机构，并请家人一起核实。

### 13.4 Trust and accessibility design

The design should feel:

- 可信;
- 清楚;
- 平静;
- 老人也容易读懂.

Requirements:

- mobile first;
- large readable Simplified Chinese;
- large touch targets and visible keyboard focus;
- status must not depend on color alone;
- semantic headings and basic WCAG AA contrast;
- no flashing alarm, panic copy, autoplay, infinite scroll, or “震惊 / 曝光” headlines;
- exact evidence-verification and release-publication dates, not a false “live” impression;
- stable slugs and useful sharing metadata;
- no ads, affiliate links, engagement bait, or notification prompts.

Without adding another primary product surface, provide durable, linkable sections at `/#methodology`, `/#sources`, `/#about`, `/#privacy`, and `/#corrections`. They must explain Evidence vs Heat, current source coverage, operator/scope, the static local-search privacy behavior, disclaimer, and correction/takedown contact. Footer links point to these anchors; this trust information cannot be an unlinked afterthought.

---

## 14. Safety, attribution, copyright, and privacy

### 14.1 AI authority boundary

AI may:

- identify relevance;
- extract structured facts;
- propose a summary;
- compare patterns;
- propose a material change;
- generate a draft explanation.

AI may not:

- declare a person, company, or product fraudulent;
- override a source;
- count copied articles as independent confirmation;
- set the final Heat score;
- accept evidence, merge patterns, approve, or publish.

### 14.2 Attribution and defamation controls

- Score patterns, not alleged perpetrators.
- Do not publish private-person identity or victim PII.
- A brand may be named as the entity being impersonated; copy must make clear that the brand is not the scam operator.
- Preserve the source’s procedural status: allegation, warning, investigation, enforcement action, charge, or judgment are not interchangeable.
- Do not infer guilt, nationality, ethnicity, or geography from names, language, phone prefix, or model output.
- Support correction and urgent unpublication while retaining an internal audit record.

### 14.3 Harm-reduction controls

- Do not reproduce complete scripts, malware instructions, credential-bypass steps, or operational details that materially enable abuse.
- Never make a suspected malicious destination clickable. Defang it only when recognition is necessary.
- Link to original official or editorial evidence, not to live scam infrastructure.
- Protective guidance prioritizes: stop contact/payment, stop screen sharing, contact the bank/platform via independently found official channels, change compromised credentials, preserve evidence, tell a trusted family member, and contact relevant local authorities.
- Do not promise recovery or offer legal/financial advice.

### 14.4 Copyright and collection controls

- Respect site terms, robots directives, rate limits, and registry policy review.
- Store only what the pipeline needs.
- Public pages use original Scam Radar summaries and minimal attributed excerpts, not republished articles.
- Raw HTML is transient on the runner and is not stored.
- Irrelevant items retain metadata, hash, and classification result; their cleaned body should not be kept unless needed for a test or audit case.
- Relevant/evidence clean text is internal only and bounded by a configured maximum.

### 14.5 Public disclaimer

The site must say, in plain Chinese:

> 骗局雷达根据一组经过选择的公开来源整理信息，可能不完整或有延迟，仅用于帮助识别常见风险，不构成法律、金融、调查或紧急处置建议。数据库里没有找到，不代表某条消息、网站、产品或联系人一定安全。

---

## 15. Environment variables and secrets

`.env.example` lists names and safe fake values only.

### 15.1 GitHub Actions secrets

```text
SUPABASE_SECRET_KEY
GEMINI_API_KEY
CLOUDFLARE_API_TOKEN
SUPABASE_ACCESS_TOKEN             # migration workflow only, if required
SUPABASE_DB_PASSWORD              # migration workflow only, if required
```

For an older Supabase project, `SUPABASE_SERVICE_ROLE_KEY` may be the legacy equivalent of `SUPABASE_SECRET_KEY`; new code should prefer the current publishable/secret key model and map the legacy name only in one settings adapter.

### 15.2 GitHub Actions variables

```text
SCAM_RADAR_ENV=production
SCAM_RADAR_SITE_URL=https://scamradar.insparian.com
SUPABASE_URL
SCAM_RADAR_COLLECT_ENABLED=false
SCAM_RADAR_AI_ENABLED=false
SCAM_RADAR_DEPLOY_ENABLED=false
SCAM_RADAR_MAX_ITEMS_PER_RUN=250
SCAM_RADAR_MAX_ITEMS_PER_SOURCE=50
SCAM_RADAR_MAX_GEMINI_CALLS_PER_RUN=100
SCAM_RADAR_GEMINI_INPUT_CHAR_LIMIT=30000
SCAM_RADAR_MAX_CLEAN_TEXT_CHARS=50000
SCAM_RADAR_RUN_TIMEOUT_MINUTES=45
SCAM_RADAR_HTTP_USER_AGENT
SCAM_RADAR_CONTACT_EMAIL
SOURCE_REGISTRY_PATH=config/sources.yaml
LOG_LEVEL=INFO
CLOUDFLARE_ACCOUNT_ID
CLOUDFLARE_PAGES_PROJECT=scam-radar
SUPABASE_PROJECT_REF
```

Production model, prompt, taxonomy, schema, scoring, and publication-policy selection comes from reviewed repository files. CI derives their combined behavior hash and requires a matching approved eval manifest; no GitHub variable can select another production behavior. Scoring and policy versions are derived from checked-in content, not arbitrary environment labels. V0.1 policy config must remain shadow with live automatic authorization false, and the database live-policy allowlist must remain empty. A later activation migration must bind the exact reviewed policy and Evidence Gate hashes. Environment quota caps may lower checked-in hard maxima but may not raise them. Caps are safety defaults, not entitlement assumptions.

### 15.3 Static web variables

```text
NEXT_PUBLIC_SUPABASE_URL
NEXT_PUBLIC_SUPABASE_PUBLISHABLE_KEY
NEXT_PUBLIC_SITE_URL=https://scamradar.insparian.com
NEXT_PUBLIC_BUILD_SHA
NEXT_PUBLIC_RELEASE_ID               # injected by deploy workflow
```

Anything beginning with `NEXT_PUBLIC_` is public. The Supabase values are used only by the client-side admin Auth/review chunks; public content and search do not query Supabase. These variables must never contain a Supabase secret/service key, Gemini key, database password, or Cloudflare token.

A dedicated trusted exporter step may use `SUPABASE_SECRET_KEY` to fetch one exact published `release_id` into `work/release/<release_id>/`. It must then remove the secret from the environment before launching Next.js. The Next build process reads only those JSON artifacts and must never receive the secret. CI scans the exported bundle for a sentinel secret.

### 15.4 Key handling

- Local secrets live in ignored `.env.local` files.
- Production secrets live in GitHub Encrypted Secrets.
- PRs from forks do not receive secrets.
- Cloudflare token is scoped only to the Pages project, not a Global API Key.
- Logs do not print environment values, Authorization headers, full model payloads, or source bodies.
- Suspected leakage triggers: pause workflow → rotate → update secret → smoke test → revoke old key.

---

## 16. CI/CD

### 16.1 `ci.yml`

Trigger on every pull request and push to `main`.

Required jobs:

1. install pinned Python and Node dependencies from lockfiles;
2. Python format/lint/typecheck/unit tests;
3. web lint/typecheck/component tests/static build;
4. start local Supabase/Postgres, apply migrations and seed from zero;
5. database constraint and RLS tests;
6. collector contract tests using fixtures only;
7. recorded-response Gold Set eval;
8. offline end-to-end fixture demo;
9. generated TypeScript database-type drift check;
10. secret sentinel scan of `web/out`;
11. repository secret scan and a check that third-party GitHub Actions are pinned to full commit SHAs;
12. current behavior-hash ↔ approved live-eval-manifest check;
13. policy monotonicity, shadow-authority denial, and public freshness timestamp contract checks;
14. concise test/eval summary upload.

CI dependency installation may use approved registries, but application tests run with outbound network denied except localhost and must not call production Supabase, real source sites, Gemini, Cloudflare, or telemetry. All HTTP transports must be injectable. Production secrets are injected only into the single trusted step that needs each one, not at workflow scope.

Default workflow permissions:

```yaml
permissions:
  contents: read
```

Give each job only the extra permission it actually needs.

### 16.2 `collect.yml`

Use three Asia/Shanghai schedules away from the top of the hour, plus manual dispatch. At implementation time, confirm the current GitHub Actions timezone syntax; if unavailable, encode the equivalent UTC hours.

```yaml
on:
  schedule:
    - cron: "17 7,13,20 * * *"
      timezone: "Asia/Shanghai"
  workflow_dispatch:
```

Requirements:

- `timeout-minutes: 45`;
- fail closed before processing when production schema version or checked-in behavior hash does not match the expected deployed contract;
- one production concurrency group;
- a database lease as a second overlap guard;
- idempotent rerun behavior;
- each source isolated so one parser failure does not discard successful sources;
- hard item and Gemini-call caps;
- `workflow_dispatch` supports source selection and dry-run mode;
- structured summary with funnel counts, policy outcomes/reasons, shadow-auto candidates, failures, exception backlog, versions, and quota state;
- no full page body in logs or artifacts;
- if authorized verified revisions/unpublishes or deterministic Heat-decay changes require a new public release, prepare one immutable `release_id` and invoke the reusable deploy workflow.

The release check is a separate job and still runs when collection or AI is paused, so an authorized correction/unpublish cannot be stranded by a crawler kill switch.

Scheduled execution is best-effort, not a real-time SLA. Manual dispatch is the recovery path.

### 16.3 `deploy.yml`

Use **Cloudflare Pages Direct Upload** from GitHub Actions. Do not also enable Cloudflare Git auto-deploy, which would deploy twice.

Triggers:

- `workflow_call` from a deploy job at the end of successful `ci.yml` on `push` to `main` after launch;
- `workflow_call` when a newly prepared authorized content `release_id` exists;
- manual dispatch for urgent publish/unpublish.

Before first launch, `SCAM_RADAR_DEPLOY_ENABLED=false` makes every automatic caller exit without deployment. After launch, a human push/merge to `main` authorizes a code release; a valid policy or human verification path authorizes inclusion of that exact content revision. V0.1 shadow-safe candidates still require authenticated human confirmation. Codex still never pushes or deploys on its own.

Steps:

1. verify deploy is enabled, target commit passed CI, database schema/behavior/policy contract matches, and `release_id` contains only authorized verified revisions;
2. acquire the one production deployment concurrency/DB lease, reconcile the live `release.json` with database state, and reject an older release from overwriting a newer deployed release;
3. use a secret-bearing exporter step to write the immutable release and search JSON, record their hashes, then remove the database secret from the environment;
4. build Next.js static export from those files and embed `release_id` plus artifact hash;
5. scan export for backend secret sentinel;
6. upload the artifact as a Cloudflare preview deployment and smoke-test home, one detail page, search index, missing page, and embedded release ID;
7. re-check that the release remains deployable, then upload the exact same artifact as production;
8. verify `release.json`, home, detail, local search index, and canonical domain all expose the same release ID and correct v2 `last_verified_at`/`published_at` semantics;
9. verify the artifact's pre-frozen `published_at` is unchanged, record the Cloudflare deployment ID and `deployed_at`, and mark the release `deployed` through RPC;
10. if the final database write fails, leave the already public static artifact untouched, report `deployed_unrecorded`, and run reconciliation that reads production `release.json` and retries the idempotent mark;
11. if production smoke fails, redeploy the last known-good artifact and record both deployment IDs;
12. write commit SHA, release ID, artifact hash, deployment IDs, reconciliation state, and result to the Actions summary.

A build or preview failure leaves the existing production site unchanged. A successful production upload is already public; a later bookkeeping failure must never be described as “not deployed.”

### 16.4 `migrate-production.yml`

Production migrations are manual and protected by an explicit confirmation step.

- V0.1 migrations should be additive and backward-compatible by default.
- `DROP`, `TRUNCATE`, destructive type change, data rewrite, or RLS widening requires a backup/export, rollback plan, and Rui confirmation.
- Use expand/migrate/contract sequencing; do not make a web release depend on an unconfirmed destructive migration.
- Database recovery uses a forward fix, not Git history rewriting.

### 16.5 `eval-live.yml`

- Manual only; trusted branch only.
- Reads the Gemini secret only after approval.
- Records model ID, prompt/schema hashes, Gold Set split, call count, timing, and metrics.
- Produces a before/after report.
- Does not modify prompts, commit, push, or publish.

---

## 17. Operational constraints and failure behavior

### 17.1 Cost and quota

- Target `$0/month`; free quotas are guardrails, not a reason to maximize usage.
- No automatic paid fallback.
- Model and quota availability may change; keep model IDs and caps configurable.
- Cache by content hash and behavior version; do not pay the same AI cost twice.
- Prioritize the oldest Tier A/B `pending_ai` items when a backlog exists.
- If a quota is exhausted, collection succeeds in degraded mode and AI waits for a later run.

### 17.2 Source behavior

- Default maximum 50 items/source/run, 20-second timeout, and at least 1.5 seconds between requests to one host; registry entries may lower these limits.
- Retry timeout, `408`, `429`, and `5xx` up to three times with exponential backoff and jitter.
- Respect `Retry-After`.
- Do not retry ordinary `4xx` except an explicitly understood transient case.
- Three consecutive source failures create a `source_health` exception item and visibly degrade the run; do not silently disable or bypass the source.
- Commit a cursor only after source success so a partial failure cannot skip items.
- Recheck accepted evidence on a bounded schedule: default every seven days, and within 24 hours when it is the sole evidence family behind an active Heat ≥65 record. Conditional requests avoid unnecessary downloads.
- A new content hash creates a new source-item version. Explicit correction/withdrawal, contradictory change, or persistent unavailability creates `gate_regression`; it never edits the accepted evidence in place.

### 17.3 Database and retention

- Never store raw HTML, media, screenshots, arbitrary headers, or binaries.
- Keep relevant clean text bounded; immediately null irrelevant clean text after classification unless retained as a reviewed eval/audit fixture.
- Retain metadata, canonical URL, hashes, model decision, and timestamps for deduplication/audit.
- Report table sizes and a configurable warning threshold in each daily summary.
- Do not implement automatic destructive cleanup in V0.1. A retention change needs a reviewed policy and migration.

### 17.4 Observability

Each run records:

- discovered, fetched, new, exact duplicate, origin duplicate, failed;
- relevant / irrelevant;
- AI pending / success / invalid / error;
- candidate pattern / linked pattern / ambiguous match;
- gate outcomes and reason-code counts;
- policy outcomes/reasons, shadow-auto counts, and exception/shadow-confirmation items created/updated;
- Heat recomputations;
- per-source duration, retry count, and health;
- model, prompt, schema, registry, score, and commit versions;
- backlog and quota-cap status.

Fatal run errors:

- invalid registry;
- missing/invalid Supabase credentials;
- failure to acquire or renew the lease;
- systemic Supabase write failure;
- corrupted migration/schema contract.

A single source or Gemini failure is isolated and must not corrupt the public database.

### 17.5 Kill switches

Without code changes:

- `SCAM_RADAR_COLLECT_ENABLED=false` stops real crawling;
- `SCAM_RADAR_AI_ENABLED=false` stops Gemini calls while retaining pending items;
- `SCAM_RADAR_DEPLOY_ENABLED=false` blocks all production Pages uploads before launch or during an incident;
- GitHub scheduled workflow can be disabled in an emergency.

Old published pages remain available while new processing is paused.

Verification authority is not granted by a feature flag or model output. Database triggers/RPC checks require either enabled-human exception provenance or a matching eligible live policy decision whose exact policy version/hash and Evidence Gate version appear in the database activation allowlist. V0.1's allowlist is empty, so the worker cannot convert shadow outcomes into verified revisions. Deploy rejects releases containing anything outside these paths.

### 17.6 Mainland access

Cloudflare Pages access quality from mainland China is a known validation risk, not a reason to block V0.1. Before declaring launch complete, test the production site on several mainland mobile networks and record load success and latency. If experience is consistently unacceptable, hosting migration becomes a separate decision; the Engine and database must remain portable.

---

## 18. Testing strategy

### 18.1 Unit tests

Cover:

- URL normalization and meaningful query parameters;
- Unicode/text cleanup, encoding errors, empty and truncated pages;
- content/identity/origin hashes;
- dedup and rerun idempotency;
- all Evidence Gate branches and reason codes;
- Policy Engine safe/review/blocked branches, stable hashes, fail-closed unknowns, shadow authority denial, and the invariant that confidence can only downgrade;
- syndication-origin versus underlying evidence-family independence;
- the `risk_type × legal_status × evidence_level` public-copy matrix;
- every Scam Heat bucket, boundary, cap, unknown case, and final total;
- date/timezone/amount parsing;
- AI schema validation for missing, extra, invalid, null, and truncated output;
- quota caps and retries without real sleeps/network;
- PII masking and unsafe-link defanging.

### 18.2 Collector contract tests

Every collector must prove with fixed fixtures:

- it discovers and parses expected list/detail content;
- empty or changed markup creates a structured error instead of overwriting good data;
- rerunning produces no duplicate rows;
- requests cannot escape registry-allowed domains;
- request count, timeout, response size, and text limits are enforced;
- prompt-injection text inside a page remains data;
- PR tests do not touch the live site.

### 18.3 Database and RLS tests

- Build the database from zero using migrations.
- Anonymous database access sees no application data; public content comes only from the static release artifact.
- Authenticated non-reviewer has no review capability.
- Enabled reviewer can call only intended RPCs.
- Secret/service role never appears in web code or bundle.
- `policy_decisions` and `review_events` are separately append-only and automation never populates a human actor.
- Concurrent duplicate insert attempts remain one logical item.
- Verification transaction fails if Evidence Gate, policy/input/content/evidence hash, or `row_version` changed.
- A verified revision cannot be updated/deleted; an edit creates a new draft revision.
- A generic service/worker request cannot impersonate a reviewer; a shadow policy decision cannot satisfy live verification.
- Verified-but-not-released and rejected records cannot enter the static exporter.
- Release manifests pin exact pattern revisions, Heat snapshots, conservative pattern `last_verified_at`, and per-evidence verification timestamps.
- Evidence `last_verified_at`, revision `verified_at`, and release `published_at` remain semantically and structurally distinct.

### 18.4 Web tests

- Home/search/detail components: loading, empty, stale, error, archived, and missing-source states.
- Heat breakdown and evidence wording.
- Keyboard navigation, focus, semantic headings, touch target, and contrast checks.
- Playwright core public flow: home → search → detail → evidence source.
- Playwright admin flow: Policy Engine route → exception review → approve/reject → distinct audit state.
- Static export contains every published fixture slug and stable metadata.
- Home, detail, and search index expose one identical `release_id`; search performs no network request.
- `risk_alert` fixtures never render confirmed-scam or adjudication wording.
- Bundle secret sentinel scan.

Deployment contract tests must also inject failure between production upload and database recording, verify idempotent reconciliation from live `release.json`, prevent an older release from overwriting a newer one, and prove an urgent removal release removes the canonical slug from the current artifact.

### 18.5 Offline end-to-end demo

`make demo` must run without cloud accounts or network:

```text
fixture source
→ collect
→ normalize
→ deduplicate
→ recorded Gemini relevance/extraction/comparison
→ Evidence Gate
→ Scam Heat
→ deterministic Policy Engine
→ shadow-safe / exception route
→ fixture human confirmation
→ immutable static release export
→ static detail page
```

---

## 19. Gold Set and evals

### 19.1 Size and labels

Build the first 50–100 historical public reports before prompt tuning. Before launch, the item-level set must contain at least 100 stratified records; matching/material-change pairs and temporal scenarios may be derived from those same reports. Label:

- `Relevant / Not Relevant`;
- `Same Pattern / Different Pattern` pairs;
- Evidence level A/B/C/D;
- elderly relevance bucket;
- material change yes/no and change type;
- structured fields with supported source spans;
- expected Heat components and expected score band;
- expected gate reason codes;
- expected Policy Engine rules/effective outcomes and reason codes;
- low/unknown confidence downgrade cases and matched high-confidence cases that must not upgrade;
- forbidden public claims.

Minimum launch denominators:

- ≥100 relevance/evidence records, including at least 20 A, 20 B, 20 C/D, and 25 legitimate/unrelated negative controls;
- ≥40 balanced `Same Pattern / Different Pattern` pairs;
- ≥30 material-change / routine-update pairs;
- ≥10 temporal exception-queue and shadow-routing scenarios;
- ≥5 examples each of prompt injection, correction/retraction, common-origin syndication, and legitimate lookalikes. Categories may overlap.

Use a stratified 70/30 development/locked-holdout split. At least 20% of records receive a second human review, and every holdout public-eligibility label is adjudicated. A holdout label changes only for a documented labeling error.

### 19.2 Required hard cases

Include:

- same scam, different titles: 收藏品回购 vs 高价收粮票;
- similar words, different patterns: 假客服 vs 假警察;
- high apparent Heat but Evidence C;
- authoritative but old/common and not worth today’s attention;
- elderly-targeted risk that is not a confirmed criminal scam;
- legitimate auction, insurance, medical, or consumer activity;
- multiple URLs copied from one origin;
- later correction, retraction, or contradictory source;
- article with missing date or inaccessible original;
- prompt injection and malformed page content;
- unknown values that must remain null rather than guessed.

### 19.3 Initial quality gates

These are launch gates and may change only through a versioned eval-policy change:

- relevance recall ≥90% on positive cases and precision ≥80%;
- pairwise pattern-match precision ≥90% and recall ≥85%;
- 100% of C/D holdout cases blocked from public eligibility;
- public-eligibility precision ≥95%;
- every non-null public factual field has accepted evidence in 100% of holdout cases;
- material-change F1 ≥85%;
- Heat calculation is 100% deterministic for fixed features;
- ≥90% of labeled cases fall in the expected Heat band;
- temporal simulation puts ≥90% of human-selected “must review” items in the system’s top exception-queue group;
- 100% monotonic authority: changing model confidence alone never upgrades a policy outcome;
- 100% of shadow `safe_to_automate` decisions have `publication_authorized=false`;
- measured shadow false-auto rate and review-required capture rate are reported with denominators; no live-auto threshold exists until a separate activation decision;
- zero severe unsupported accusations in the holdout set.

False-publication precision is more important than maximal coverage. Missing a weak signal is cheaper than falsely calling a legitimate party fraudulent.

### 19.4 Prompt/model evaluation policy

- Normal CI uses recorded model responses so it is deterministic and free.
- A prompt, schema, or model change requires manual live eval on the trusted branch.
- Store the combined behavior hash, prompt/schema/taxonomy/scoring/policy hashes, model ID, timestamp, denominators, metrics, and failure-case IDs in an approved eval manifest.
- CI and deploy recompute the current behavior hash and fail when no matching approved eval manifest exists.
- A critical metric regression or >2 percentage-point unexplained drop blocks release.
- Add every meaningful false positive, false merge, or missed high-priority item as a regression case.

---

## 20. Milestones

| Milestone | Deliverable | Exit gate |
|---|---|---|
| **M0 — Rules & scaffold** | Root `AGENTS.md`, repo structure, architecture/data-flow docs, dependency decisions, schemas, env template, Makefile, minimal offline CI | Rules precede business code; fixture commands run |
| **M1 — Deterministic ingestion** | Supabase schema/RLS, Source Registry, five fixture/seed collectors, stable item/version storage, run tracking, dedup | System can reliably “start reading”; identical rerun creates no duplicate |
| **M2 — Scam Intelligence & Policy** | Gold/eval harness, relevance, structured extraction, matching, Evidence Gate, Scam Heat, deterministic Policy Engine and shadow routing | System can explain what is safe, what needs review, and why; model confidence cannot increase authority |
| **M3 — Human exception path** | Auth, exception Review Queue, immutable verified revisions, claim/evidence mapping, confirm/merge/reject/unpublish, distinct audit | No deployable revision can exist outside a valid policy or human path; V0.1 shadow still requires authenticated confirmation |
| **M4 — Public Database** | Home, detail, local static search, immutable release export, preview/production Pages workflow | One release produces consistent, searchable, traceable public output |
| **M5 — Real-world validation & launch** | 15–25 live sources, three daily runs, failure/quota/takedown runbooks, shadow review, domain | Live Definition of Done passes and Rui approves launch |

Distribution is a post-V0.1 roadmap item, not a V0.1 milestone.

Do not spend significant time on homepage visual polish before M2 produces real data. The website should grow from actual patterns and review behavior.

---

## 21. Definition of Done

V0.1 is complete only when all conditions below are true.

### 21.1 Product and intelligence

- Enabled seed sources are collected automatically and stably three times daily.
- Most irrelevant items require no human action.
- Repeated reports and common-origin reposts do not inflate evidence or Heat.
- Existing patterns and genuinely new patterns are usually distinguished correctly against the Gold Set gates.
- Every public factual field is traceable to accepted evidence.
- Evidence level and Heat are stored, calculated, displayed, and tested independently.
- A human can override, merge, reject, correct, archive, and unpublish every AI proposal or policy decision.
- The daily exception queue is short enough to inspect in 2–5 minutes after initial backlog.
- Every candidate has a reproducible policy version/hash, outcome, reasons, mode, and authority result; shadow safe candidates never auto-publish.
- AI model, prompt, schema, input hash, and processing time are recorded.

### 21.2 Public experience

- Home, `/scam/[slug]`, and `/search` are complete and mobile usable.
- Search resolves canonical names, aliases, and common user wording.
- A user can understand mechanism, warning sign, action, evidence, conservative information freshness, and separate release publication time without opening the source article.
- No-result search explains that absence does not mean safety and gives immediate safe actions.
- The UI is calm, large, accessible, and does not sensationalize.
- The site works independently of 视频号、小红书、抖音, or any distribution platform.

### 21.3 Engineering quality

- Fresh clone can run `make bootstrap`, `make check`, `make test`, `make eval`, and `make demo` as documented.
- All initial Gold Set quality gates pass.
- CI is entirely offline for application behavior.
- Same collection input can be rerun without duplicate logical records, policy decisions, or exception tasks.
- Static build contains no backend secrets.
- No unresolved P0/P1 defect remains.

### 21.4 Security and operations

- Supabase grants/RLS tests prove public/private separation.
- Repository and logs contain no secret, production `.env`, full raw HTML, or victim PII.
- All outbound data paths in §5 were explicitly reviewed before activation.
- Kill switches and quota caps are tested.
- One source or Gemini failure cannot corrupt or remove the prior public site.
- Pipeline records answer when it ran, what it processed, which behavior versions were used, and why it failed.
- False-positive, collection-failure, quota, deployment/rollback, key-rotation, and recovery runbooks have been exercised once.
- Architecture contains no VPS, daemon, queue server, or automatic paid fallback.

### 21.5 Live validation and launch

- The reviewed registry contains 15–25 enabled live sources across A1, A2, and B, each with a passing fixture/contract test.
- During seven consecutive shadow-run days, at least 18 of the expected 21 end-to-end windows succeed, every enabled source succeeds at least once per day, and no fatal collection gap exceeds 24 hours.
- When provider quota is healthy, the 95th-percentile `pending_ai` item age stays below 24 hours.
- Human shadow comparison finds no known Evidence C/D item published, no uninvestigated severe false accusation, and reports false-auto/review-capture results for every `safe_to_automate` candidate.
- After excluding initial backlog, median new exception items are ≤5/day, p90 is ≤8/day, and measured median human decision time is ≤5 minutes; outliers have an explained source or rule cause.
- Cloudflare Pages production deployment succeeds.
- `https://scamradar.insparian.com` has valid HTTPS, canonical metadata, and a passing read-only smoke test.
- Mainland checks cover at least three independent network paths, both iOS and Android, and the WeChat in-app browser; ≥90% of ten or more attempts load home, search, and one detail page without a critical failure, with median/p95 timings recorded.
- Static home, detail, and search all expose the same `release_id`, including after rollback and unpublish tests.
- Database tests prove a generic worker/service request cannot impersonate a reviewer or turn shadow into live authority; every V0.1 deployed release contains authenticated human confirmation even when the stored rules outcome was `safe_to_automate`.
- Rui explicitly approves the first public release and DNS change.

---

## 22. Operational runbooks required before launch

### False positive

1. Reviewer confirms an emergency takedown; the system records `takedown_requested` and excludes the pattern from the next release manifest. Do not claim it is already removed.
2. Trigger the urgent removal release immediately; bypass the normal collection interval, but never bypass artifact checks.
3. Verify the current canonical URL no longer appears in home/search and returns 404/410 after production deploy. Operational target: within 30 minutes of reviewer confirmation.
4. Record reviewer, reason, timestamps, prior revision, evidence, model/prompt, Heat, removal release, and Cloudflare deployment ID.
5. If an old Cloudflare preview/deployment URL or CDN copy remains accessible, record that limitation and use the supported Cloudflare removal/purge path only with the required destructive-action approval.
6. Identify whether source, extraction, evidence-family grouping, gate, Policy Engine, one-way confidence downgrade, Heat, or human exception decision failed. Disable any implicated live policy class first.
7. Add the case to the Gold Set and rerun relevant evals before any corrected revision is authorized.

The admin must distinguish `takedown_requested`, `removal_deploying`, and `removed_from_current_site`; a database flag alone does not remove an already deployed static page.

### Source/parser failure

1. Identify failing source and reason from the run summary.
2. Save a minimal permitted fixture.
3. Write the failing test before changing the parser.
4. If login/CAPTCHA/blocking/terms prevent collection, disable the source; do not evade.
5. Rerun the one source manually and verify idempotency.

### Quota exhaustion

1. Stop new Gemini calls before crossing the configured cap.
2. Leave items `pending_ai`.
3. Resume oldest high-trust items next run.
4. Missing model output may only downgrade an otherwise safe policy candidate to review; it never grants authority.
5. Do not buy, upgrade, or switch provider automatically.

### Rollback

- Web: redeploy the last tested artifact/commit; do not force-push.
- Worker: stop collection, deploy a verified forward fix, then resume.
- Prompt/model/scoring/policy: disable live policy authorization, select the prior version, and rerun eval.
- Database: prefer forward migration; back up before any irreversible repair.

### Emergency pause

Turn off collection and/or AI via variables. Existing published pages remain read-only and available. Live policy authorization, if separately activated in a later version, must have its own immediate disable path; V0.1 remains shadow-only.

---

## 23. Inputs Rui must provide only at activation time

These do not block offline implementation:

- GitHub repository destination and whether it remains private (recommended: private for V0.1);
- Supabase project region, chosen after reviewing current options and data-location implications;
- reviewer email / Supabase Auth bootstrap user;
- collector contact email used in the User-Agent;
- scoped Cloudflare Pages token and access to the `insparian.com` DNS provider;
- Gemini API key with no automatic paid fallback;
- approval of the first five exact source URLs and their recorded collection policy.

Codex should reach this checkpoint with a fully working offline demo, not an empty scaffold waiting for accounts.

---

## 24. Recommended first task sequence

Codex should execute in this order.

### Task 1 — Establish repository rules

- Inspect the repo and inherited instructions.
- Create root `AGENTS.md` before application code.
- Add structure, naming, generated-file, cleanup, prompt/eval, dependency, data-flow, Git, deployment, and verification rules from §6.
- Verify only formatting/document structure.

### Task 2 — Record architecture and data flow

- Add `docs/architecture.md`, `docs/data-flow.md`, and ADRs for Next.js static export, Supabase RLS, Python worker, Gemini provider boundary, Pages Direct Upload, and deterministic Policy Engine/human exception routing.
- List proposed dependencies, purpose, maintenance status, and lighter alternatives.
- Do not activate an application data service. Approved dependency bootstrap may use official package/container registries.

### Task 3 — Scaffold the monorepo

- Create directories, pinned tool versions, lockfiles, `.env.example`, root `Makefile`, and minimal offline CI.
- Create a fixture-only home page and fixture-only worker CLI.
- Run `make check`.

### Task 4 — Build the database contract

- Add migrations, checks, indexes, append-only policy/human provenance, trusted release-export and verification RPC skeletons, RLS, audit log, and seeds.
- Rebuild local Supabase from zero.
- Prove anon/reviewer/secret-role boundaries with tests.
- Generate and commit TypeScript database types.

### Task 5 — Build fixtures and the eval harness before prompts

- Define Gold Set schemas and development/holdout split.
- Add synthetic, short permitted, or redacted fixtures covering hard cases.
- Make `make eval` work with recorded responses and no Gemini key.

### Task 6 — Implement deterministic ingestion

- Registry schema and validator.
- Collector protocol and RSS/sitemap/list-page adapters.
- HTTP limits, normalization, hashing, URL/content dedup, source cursor, run records, and leases.
- Add five disabled candidate sources with fixtures.
- Prove identical reruns are idempotent.

### Task 7 — Implement relevance and extraction

- Define JSON Schemas and provider-neutral request/response models first.
- Add recorded Gemini responses and failure tests.
- Write `relevance-v1.md` and `extraction-v1.md` only after eval cases exist.
- Implement `GeminiProvider`, still disabled in production.

### Task 8 — Implement matching, Evidence Gate, and Scam Heat

- Candidate retrieval from names, aliases, and features.
- `pattern-match-v1` structured comparison.
- Syndication-origin and underlying evidence-family grouping plus all A/B/C/D tests.
- Exact versioned Heat feature mapping and boundary tests.
- Generate deterministic Policy Engine decisions and deduplicated exception/shadow-confirmation candidates.

### Task 9 — Implement Policy routing and human exception queue

- Supabase Auth and `admin_users` authorization.
- Policy outcome/reasons, exception list/detail, evidence groups, Heat breakdown, preview, and four primary actions.
- Transactional policy/human verification RPCs, row/hash-version checks, and distinct append-only provenance.
- Prove model confidence cannot upgrade, shadow cannot authorize, a generic worker cannot impersonate a reviewer, and V0.1 still requires authenticated confirmation.

### Task 10 — Build the public website

- Home, detail, and search exactly as §13.
- Static generation from verified/published fixture snapshots using schema v2 `last_verified_at` and `published_at` semantics.
- Calm responsive design, empty/error states, accessibility, evidence links, and stable metadata.
- Build only from one immutable fixture release; public search uses that release’s local static index.

### Task 11 — Complete offline end-to-end validation

- Make `make demo` run the whole fixture loop.
- Complete CI, RLS/policy tests, web E2E, static secret scan, and Gold Set/shadow report.
- At this point no cloud account or production secret should be required.

### Task 12 — External activation checkpoint

- Show Rui the exact §5 data flows, first five sources, free-tier caps, Supabase region choice, and secrets required.
- Obtain confirmation before creating projects, crawling, sending content to Gemini, deploying, or editing DNS.

### Task 13 — Provision production with all external actions disabled

- Create/link the approved free Supabase, Cloudflare Pages, and Gemini projects plus GitHub configuration.
- Apply production migrations and registry seed through the manual workflow.
- Bootstrap the first Supabase reviewer and configure scoped secrets/variables.
- Verify production schema/behavior version and anon/reviewer/exporter permission boundaries.
- Keep collection, AI, and production deploy switches `false`.
- Record project region, IDs, setup actor, and smoke-test result; do not crawl or deploy public content yet.

### Task 14 — One-source capped live run

- Enable collection and AI only for one approved stable source.
- Limit pages and Gemini calls well below caps.
- Inspect database rows, model output, Evidence Gate, queue, and redacted logs manually.
- Add every real edge case to fixtures/Gold Set.

### Task 15 — Expand and automate

- Grow to five live sources, then 15–25 only after stability.
- Enable three scheduled daily runs.
- Verify overlap guard, manual retry, quota degradation, and emergency pause.
- Run at least seven days of shadow policy/human comparison and report false-auto and review-required-capture denominators.

### Task 16 — Production release

- Satisfy Definition of Done.
- Keep live `safe_to_automate` authorization disabled; activating it is not part of the first public launch and requires a separate narrow policy-class decision.
- Obtain Rui’s explicit launch/DNS approval.
- Set `SCAM_RADAR_DEPLOY_ENABLED=true` only after that approval.
- Deploy Pages project `scam-radar`.
- Add `scamradar.insparian.com` in Cloudflare Pages first. If DNS is external, create only the CNAME target Cloudflare returns for that verified custom domain; do not guess or alter apex records.
- Verify HTTPS and production smoke tests.
- Do not modify the apex `insparian.com` site.

---

## 25. Implementation references

Platform behavior changes. Re-check these official references before scaffolding/deployment and record any changed assumption in an ADR:

- [Cloudflare Pages — static Next.js deployment](https://developers.cloudflare.com/pages/framework-guides/nextjs/deploy-a-static-nextjs-site/)
- [Next.js — static exports](https://nextjs.org/docs/app/guides/static-exports)
- [Cloudflare Pages — Direct Upload from CI](https://developers.cloudflare.com/pages/how-to/use-direct-upload-with-continuous-integration/)
- [Cloudflare Pages — custom domains](https://developers.cloudflare.com/pages/configuration/custom-domains/)
- [GitHub Actions — scheduled workflow behavior](https://docs.github.com/en/actions/reference/workflows-and-actions/events-that-trigger-workflows#schedule)
- [Supabase — Row Level Security](https://supabase.com/docs/guides/database/postgres/row-level-security)
- [Supabase — database functions](https://supabase.com/docs/guides/database/functions)
- [Supabase — API keys](https://supabase.com/docs/guides/getting-started/api-keys)
- [Gemini API — structured outputs](https://ai.google.dev/gemini-api/docs/structured-output)
- [Gemini API — embeddings](https://ai.google.dev/gemini-api/docs/embeddings)

If a free plan or integration changes, preserve the product and security boundaries first. Do not silently add a paid service, a new outbound data path, or a full-stack runtime merely to keep an old implementation choice alive.

---

## Final product sentence

> **骗局雷达持续观察可信公开信源，识别近期出现、尤其可能影响中老年人的骗局或高风险套路，通过 Evidence Gate 和确定性 Policy Engine 自动处理安全常规项、把例外交给人决定，再沉淀为简单、可信、可搜索、可追溯的公共 Scam Pattern 数据库。**

The website is the first window into the Engine. Social distribution can become its first loudspeaker only after the Engine proves that it can find the right things, support them with evidence, and compress human attention safely.
