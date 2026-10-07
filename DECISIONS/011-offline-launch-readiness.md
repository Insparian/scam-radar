# V0.1 offline launch readiness

Approved by Rui with explicit `proceed` on 2026-09-18.

- **What:** 完成 V0.1 的离线上线准备。
- **Why now:** 当前演示可运行，但真实链路和部署仍有占位，阻碍首次上线。
- **Problem it solves:** 用户需要可信、可搜索的骗局数据库；Rui 需要一次验收而非逐项指挥。
- **Alternative considered:** 只润色前端无法证明真实数据能安全进入网站；同时做传播会扩大范围。
- **North Star check:** 优先 Evidence、Radar、Memory 和减少人工负担，保留 V0.1 人工确认与后续自动化架构。

Scope includes local ingestion/persistence/model protocols/review/release export,
family-facing static UX, guarded deployment/recovery implementations, and a single
external activation checklist. Preserve Next.js, Python batch, Supabase and Pages.
When Goal Router is explicitly invoked, Decision 013 governs agent routing and concurrency; otherwise the lead works locally. GLM/Qwen/Gemini remain configurable candidates with no assumed winner.
No distribution, social/video, chat, or architecture migration. No real collection,
model requests, production data access/writes, backup upload, deployment, or DNS.
All application verification is local; official documentation research is allowed.
Maximum 12 evidence-producing rounds; progress and blockers belong only in
docs/PROGRESS.md and docs/BLOCKED.md. Completion requires real local PostgreSQL and
the full acceptance commands, not only fixture tests.
