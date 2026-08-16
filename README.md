# 骗局雷达 / Scam Radar

骗局雷达把经过选择的可信公开报道压缩成少量、可人工审核、可追溯的 **Scam Patterns**。它不是诈骗新闻站，也不会让 AI 判断某个人、公司或产品“就是诈骗”。

## 当前状态

仓库目前是 **offline-first V0.1**：默认只使用 fixtures、recorded AI responses 和本地文件/数据库测试。所有真实来源都在 `config/sources.yaml` 中保持 `enabled: false`，以下功能尚未获准启用，也不能视为已完成线上验证：

- 真实网站采集；
- Gemini API 调用；
- production Supabase 连接；
- Cloudflare Pages 部署或 DNS 修改；
- 任何 analytics、telemetry 或用户搜索词上传。

离线构建的目标是先证明核心链路：来源条目 → 去重 → AI proposal → Evidence Gate → Scam Heat → 人工审核 → 同一 `release_id` 的静态页面与本地搜索。

## 最短使用路径

需要 Node.js、Python、`uv`、npm 和 `make`。首次运行：

```bash
make bootstrap
make check
make test
make eval
make demo
```

打开 fixture 网站：

```bash
make web
```

终端会显示本地地址；停止时按 `Ctrl+C`。不要把 `.env.example` 里的假值替换成真实密钥，除非已经到达并通过 external activation checkpoint。

## 稳定命令

| Command | Purpose |
|---|---|
| `make bootstrap` | 安装并锁定本地 Node/Python 依赖；只允许访问官方 package registries |
| `make check` | 格式、lint、type、schema/config 和生成文件一致性检查 |
| `make test` | 离线 worker、web 和数据库 contract tests |
| `make eval` | 使用 recorded responses 跑 Gold Set；不需要 Gemini key |
| `make demo` | 跑完整 fixture 链路并生成可检查的本地结果 |
| `make web` | 启动 fixture/static web preview |
| `make collect-dry-run` | 运行不访问真实来源、不写 production 的采集演练 |

这些命令是仓库对人的稳定入口。内部工具可以变化，但不要让 Rui 记住多套子目录命令。

## 安全边界

- Public pages 和 search index 必须来自同一个 immutable `release_id`。
- Public search 只在浏览器本地运行，不发送或保存搜索词。
- AI 只提出建议；Evidence Gate 和登录的人工 reviewer 决定可否发布。
- Scam Heat 表示“现在是否值得注意”，不表示“真假”。
- Raw HTML 只可短暂处理，不能永久存储或提交。
- 密钥只放在 ignored local env 或 GitHub Encrypted Secrets；任何 `NEXT_PUBLIC_` 值都会进入公开网页。
- 日志只记录 counts、IDs、versions、hashes 和 reason codes，不记录正文、PII、prompt payload 或环境变量。

完整边界见 [architecture](docs/architecture.md) 和 [data flow](docs/data-flow.md)。依赖理由记录在 [dependency ADR](docs/decisions/006-dependency-review.md)。

## 目录

| Directory | Responsibility |
|---|---|
| `web/` | Next.js static public site 和 client-only reviewer UI |
| `worker/` | 短生命周期 Python batch pipeline 和 tests |
| `supabase/` | Forward-only migrations、seed 和 database contract tests |
| `config/` | Reviewed sources、taxonomy、models 和 scoring behavior |
| `prompts/` | Provider-neutral prompt prose |
| `contracts/schemas/` | Versioned AI JSON Schemas |
| `evals/` | Gold Set、recorded responses、expected results 和 reports |
| `docs/` | Architecture、ADRs 和 operator runbooks |
| `scripts/` | Thin repository-level automation |
| `work/` | Ignored、可随时重建的本地输出，不是 durable state |

## 改动规则

先读 [AGENTS.md](AGENTS.md)。新增 feature、architecture、dependency 或行为变化需要 Decision Checkpoint；prompt/schema/model/taxonomy/scoring 改动还必须同步 eval 与 behavior manifest。改完运行相称的验证，完整交付前运行全部 offline suite。

不要自动 push、deploy、create cloud projects 或修改 DNS。需要跨设备同步时，由 Rui 明确决定是否 push。

## Operator runbooks

- [Initial setup](docs/runbooks/initial-setup.md)
- [Collection failure](docs/runbooks/collection-failure.md)
- [False positive / urgent unpublish](docs/runbooks/false-positive.md)
- [Quota exhaustion](docs/runbooks/quota-exhaustion.md)
- [Deploy and rollback](docs/runbooks/deploy-and-rollback.md)
- [Key rotation](docs/runbooks/key-rotation.md)
- [Database recovery](docs/runbooks/database-recovery.md)

External activation 需要再次向 Rui 展示所有 outbound data flows、首批五个 exact source URLs、配额、Supabase region、所需 secrets 和 Cloudflare token 的账户级权限范围，并获得明确批准。
