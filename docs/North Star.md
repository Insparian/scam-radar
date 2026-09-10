# Scam Radar — North Star

**Document type:** Product North Star  
**Authority:** Highest-level product direction  
**Status:** Active  
**Applies to:** Scam Radar / 骗局雷达

---

## 1. Why Scam Radar exists

Scam Radar exists to answer two questions:

> **最近出现的骗局里，哪些最值得提醒爸妈？**

and:

> **我现在遇到的这件可疑事情，是不是已经出现过的骗局或高风险套路？**

The product is not fundamentally a news website, a content account, or an AI media project.

It is a:

# Scam Intelligence and Early Warning System

Its purpose is to reduce the time between:

**a harmful scam pattern appearing in the real world**

and

**the people most vulnerable to it understanding what is happening.**

---

# 2. The outcome we ultimately care about

Our success is not:

- number of articles collected
- number of videos generated
- number of posts published
- number of followers
- number of AI calls
- percentage of the workflow that is automated

The ultimate outcome is:

> **Someone was about to take a harmful action, recognized the pattern, and stopped.**

For example:

> An older person was about to transfer money, but remembered seeing the warning and stopped.

Everything else is a proxy.

---

# 3. Primary users

Scam Radar primarily serves:

### A. Older and middle-aged people in mainland China

Especially people more vulnerable to:

- unfamiliar digital workflows
- authority impersonation
- emotional pressure
- investment promises
- health-related manipulation
- retirement-related financial schemes

### B. Their adult children, relatives and friends

These users often act as:

- information filters
- fact checkers
- warning distributors
- trusted intermediaries

Therefore the product must work both for:

> **“I need to know this.”**

and:

> **“I need to send this to my parents.”**

---

# 4. The fundamental unit is a Scam Pattern, not an article

Scam Radar does not think in terms of news articles.

Ten articles may describe the same scam.

The persistent object is:

# Scam Pattern

Examples:

- 冒充子女紧急事故
- 高价回收老物件
- 百万保障自动扣费
- 假客服屏幕共享
- 养老投资高收益

Articles, police notices, court cases and regulator warnings are:

# Evidence

or:

# Pattern Updates

This distinction is foundational and must not be removed for convenience.

---

# 5. Radar + Memory

Scam Radar has two core jobs.

## Radar

Find:

> **What changed recently that people should care about?**

Radar prioritizes:

- new patterns
- meaningful mutations
- new delivery channels
- new technology
- geographic spread
- increasing harm
- increased relevance to older adults

---

## Memory

Maintain:

> **What do we already know about this scam?**

Memory should be:

- searchable
- persistent
- traceable
- understandable
- updateable

Social media is temporary.

The Scam Database is institutional memory.

---

# 6. Truth and attention are separate systems

Two questions must never be collapsed into one.

### Evidence

> How confident are we that this claim is supported?

### Heat

> How important is it to pay attention to this now?

A scam can be:

**high evidence + low heat**

because it is old and stable.

A claim can be:

**high heat + low evidence**

because it is spreading rapidly but poorly verified.

Therefore:

# Heat must never determine truth.

And:

# popularity must never substitute for evidence.

---

# 7. AI does not own factual authority

AI is an analysis tool.

AI may:

- classify
- extract
- summarize
- compare
- cluster
- rank
- translate complex information into plain language
- detect possible changes
- generate candidate explanations

AI must not independently manufacture factual certainty.

Public claims must remain traceable to evidence.

When information is unknown:

> **Unknown is a valid answer.**

The system must prefer incomplete structured data over fabricated completeness.

---

# 8. Evidence before accusation

Scam Radar must be especially cautious when claims concern:

- named individuals
- named companies
- named products
- named organizations
- commercial disputes
- health products
- financial products

The existence of complaints, viral posts or suspicious behavior does not automatically justify publicly calling something:

> “诈骗”

The product must distinguish where appropriate between:

### Confirmed Scam

### Official Risk Warning

### Corroborated Pattern

### Emerging Signal

### High-Risk Practice

These are not interchangeable.

---

# 9. Automation is the destination

Scam Radar is intended to become a highly automated intelligence system.

The long-term operating model is:

> **machine by default, human by exception.**

Human review in V0.1 is a safety mechanism while the system establishes its reliability.

It is not the permanent product architecture.

The mature system should automatically handle the overwhelming majority of:

- collection
- filtering
- extraction
- deduplication
- pattern matching
- routine updates
- evidence processing
- Heat calculation
- database maintenance

Humans should increasingly concentrate on:

- ambiguous cases
- high-impact allegations
- conflicting evidence
- uncertain new patterns
- policy exceptions
- high-risk distribution decisions

The goal is not:

> AI prepares everything and a human clicks Approve forever.

The goal is:

> **AI handles normal cases; humans receive exceptions.**

---

# 10. Human review is a policy decision, not an architectural dependency

The system should conceptually support:

```text
Scam Intelligence Engine
        ↓
Policy Engine
        ↓
┌───────────────────────┬──────────────────────┐
│ Safe to automate      │ Review required      │
│                       │                      │
│ Auto publish/update   │ Human decision       │
└───────────────────────┴──────────────────────┘
```

V0.1 may deliberately classify most new public Scam Patterns as:

`review_required`

This is a temporary operating policy.

The architecture must preserve the ability to progressively move safe classes of work to:

`auto_publish`

without redesigning the system.

---

# 11. Public database and active distribution have different risk thresholds

Publishing structured information in a searchable database is not identical to actively broadcasting an alert.

Therefore Scam Radar must distinguish:

## Public Database

Primarily serves:

> Search and verification.

Long-term automation should be high.

---

## Distribution

Examples:

- 微信视频号
- 抖音
- 小红书
- notifications

Distribution actively pushes information toward people.

The consequences of error are therefore greater.

Distribution may legitimately have stricter policy gates than database maintenance.

Do not force the two systems to share the same publication rule.

---

# 12. Attention Compression is the core intelligence problem

The system may observe hundreds or thousands of source items.

A human should not need to read them.

The central technical goal is:

# Attention Compression

For example:

```text
400 source items
↓
35 scam-relevant items
↓
9 Scam Patterns
↓
4 material changes
↓
2 things genuinely worth attention today
```

The quality of this compression matters more than the volume collected.

---

# 13. Low frequency and high trust beats content volume

Scam Radar is not obligated to publish every day.

If nothing meaningful has changed:

> publishing nothing is acceptable.

The system should never manufacture urgency to satisfy:

- daily posting schedules
- engagement metrics
- SEO volume
- algorithm demands

Long-term trust is more valuable than short-term content output.

---

# 14. Explain the mechanism, not just the story

Users should not merely hear:

> “Someone lost 170,000 yuan.”

They should learn:

> **How does this scam move someone from first contact to losing money?**

Every useful Scam Pattern should attempt to explain:

### Entry

How does the scammer reach the victim?

### Identity

Who do they pretend to be?

### Hook

What creates interest, trust or fear?

### Pressure

What prevents the victim from thinking or checking?

### Requested Action

What does the scammer ask the person to do next?

### Money / Control Path

How is money, access or information ultimately taken?

### Stop Point

What simple action can break the chain?

Understanding the mechanism makes warnings transferable to future variants.

---

# 15. Plain language is a safety feature

The product should be understandable by someone who:

- does not work in technology
- does not know cybersecurity terminology
- may be stressed
- may be frightened
- may have limited time

Prefer:

> “挂断电话，自己重新拨孩子原来的号码。”

over:

> “通过独立信道进行身份验证。”

Clarity is not merely visual design.

It is part of the safety system.

---

# 16. Respect older users

Scam Radar must never frame older adults as:

- stupid
- backward
- technologically incapable
- gullible

Many scams exploit universal human mechanisms:

- fear
- trust
- authority
- urgency
- greed
- loneliness
- concern for family
- health anxiety

The product should communicate:

> **Someone designed this situation to manipulate you. Here is the pattern to recognize.**

Not:

> **You should have known better.**

---

# 17. Public claims must be traceable

A user should eventually be able to understand:

> Where did this information come from?

Therefore important factual claims should be traceable to:

- police
- regulators
- courts
- prosecutors
- authoritative media
- other appropriate evidence

The public website should distinguish:

### Source facts

from:

### Scam Radar synthesis

Users should not have to trust Scam Radar blindly.

They should be able to inspect the basis for the conclusion.

---

# 18. Public freshness describes information, not workflow

Public wording should describe the state of knowledge.

Use concepts such as:

> 最近核实

> 信息核实至

> Last Verified

Do not make internal operational processes part of the product identity.

For example, avoid prominently presenting:

> Last Human Reviewed

Whether verification involved a person, deterministic code, or AI is an internal implementation detail unless disclosure is necessary.

---

# 19. Social platforms are distribution, not the product

Scam Radar must not become structurally dependent on:

- 微信视频号
- 小红书
- 抖音
- any individual social platform

They are distribution adapters.

The core asset is:

> Scam Intelligence + structured evidence + Scam Patterns.

If one platform disappears tomorrow, the intelligence system should remain intact.

---

# 20. The website is not a media publication

The website primarily exists because social platforms are poor at:

- search
- long-term retrieval
- evidence traceability
- canonical URLs
- maintaining one evolving Scam Pattern
- structured historical updates

Therefore the website should behave primarily as a:

# Public Scam Database

not a conventional news publication.

---

# 21. Search is more important than browsing

The website must support the moment when someone asks:

> “这个是不是骗局？”

Users may search fragments such as:

- 百万保障
- 腾讯会议
- 孙子出事
- 粮票
- 免费体检
- 高价回收
- 安全账户

The system should help map those fragments to known Scam Patterns.

The user should not need to know the official name of the scam.

---

# 22. Do not prematurely build AI chat

Conversational AI may eventually help users describe an uncertain situation.

But AI chat introduces additional risk because users may interpret a conversational answer as definitive judgment.

Before building chat, Scam Radar should establish a trustworthy structured Scam Database.

Search and evidence retrieval come first.

---

# 23. Build evidence infrastructure before content automation

The order matters.

Core intelligence:

```text
Sources
↓
Evidence
↓
Scam Patterns
↓
Evidence Gate
↓
Heat
↓
Policy
```

comes before:

```text
Script
↓
Voice
↓
Video
↓
Social publishing
```

Automatically producing content from weak intelligence only scales mistakes.

---

# 24. Product evolution should follow demonstrated bottlenecks

Do not automate something merely because it can be automated.

For example:

If manually uploading one video takes one minute per day, building a fragile publishing robot may not be justified.

If manually reading fifty police websites takes hours:

automating source intelligence is highly valuable.

Prioritize automation according to:

> **human attention saved × importance of the task**

not technical novelty.

---

# 25. Infrastructure is replaceable

Current infrastructure choices may change.

The product should avoid unnecessary dependence on a particular:

- LLM
- cloud provider
- database service
- hosting platform
- social network

Provider abstraction is valuable where switching is realistically likely.

Do not over-engineer hypothetical portability.

But do not confuse infrastructure with product identity.

---

# 26. V0.1 operating strategy

V0.1 exists to establish whether the intelligence system works.

It should prioritize:

1. trustworthy source ingestion
2. scam relevance filtering
3. structured extraction
4. article deduplication
5. Scam Pattern matching
6. evidence classification
7. Scam Heat
8. short Review Queue
9. searchable public database

V0.1 deliberately uses more human review than the mature product.

That review generates:

- error examples
- Gold Set data
- policy knowledge
- confidence thresholds
- automation rules

Manual review is therefore:

> **a learning mechanism and temporary safety layer.**

---

# 27. What V0.1 is explicitly not optimizing

V0.1 does not optimize for:

- maximum traffic
- maximum SEO pages
- daily social content
- follower growth
- monetization
- number of sources
- fully autonomous publishing
- beautiful branding
- app downloads

It optimizes for:

# Can the system reliably surface the few scam developments that genuinely deserve attention?

---

# 28. The path to automation

Expected evolution:

## V0.1

AI finds and structures.

Humans approve public new patterns and important changes.

---

## V0.2

Routine updates to strongly established Scam Patterns become automatic.

Humans review exceptions.

---

## V0.3

High-confidence new patterns from strong evidence sources may become automatically publishable under explicit policy rules.

---

## Mature system

The overwhelming majority of intelligence operations happen automatically.

Human attention is reserved for exceptional or high-risk decisions.

The mature system should feel closer to:

> **an autonomous radar with human escalation**

than:

> **an AI assistant waiting for an editor.**

---

# 29. Product decision test

Before adding a major feature, ask:

### Question 1

Does this help us detect meaningful scam patterns earlier?

### Question 2

Does this improve evidence quality or traceability?

### Question 3

Does this help distinguish important signals from noise?

### Question 4

Does this help a vulnerable person recognize the scam before taking the harmful action?

### Question 5

Does this improve search or verification when someone is already suspicious?

### Question 6

Does this meaningfully reduce necessary human attention without weakening trust?

If the answer to all six is:

> No

the feature probably does not belong in Scam Radar yet.

---

# 30. Things that may look attractive but can pull the product off course

Be cautious about turning Scam Radar into:

### A generic news aggregator

The product unit must remain Scam Pattern.

### A social media content factory

Distribution is downstream of intelligence.

### An AI-generated-video project

Video is merely one output.

### A viral fear account

Fear may create engagement but destroy trust.

### A general cybersecurity product

Our primary mission is scam and manipulation risk affecting ordinary people, especially older adults and their families.

### A user-report gossip database

Unverified accusations must not become public truth.

### A chatbot that confidently labels anything suspicious as fraud

Evidence remains primary.

---

# 31. Long-term moat

The long-term defensibility is not:

- the website
- the videos
- the prompts
- the crawler
- the LLM

The valuable asset is the accumulated:

# Scam Intelligence Graph

connecting:

- Scam Patterns
- aliases
- tactics
- identities
- channels
- target populations
- geographic spread
- timeline
- evidence
- mutations
- intervention points

Over time this should make Scam Radar increasingly capable of recognizing:

> **a new version of something we have seen before.**

---

# 32. The one sentence North Star

> **Scam Radar continuously turns fragmented trustworthy public information into an evidence-backed, searchable and increasingly automated early-warning system that helps ordinary families recognize dangerous scam patterns before harm occurs.**

Chinese:

> **骗局雷达持续把分散的可信公开信息整理成有证据、可搜索、越来越自动化的骗局预警系统，让普通家庭在损失发生之前认出危险的骗局模式。**

---

# 33. Final principle

When there is tension between:

**more content**

and:

**more trust**

choose trust.

When there is tension between:

**more automation**

and:

**unsupported certainty**

choose evidence.

When there is tension between:

**a clever AI feature**

and:

**helping someone avoid harm**

choose the latter.

That is Scam Radar.