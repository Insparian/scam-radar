# 骗局雷达 / Scam Radar

骗局雷达把经过选择的可信公开报道压缩成少量、可验证、可追溯的 **Scam Patterns**。它不是诈骗新闻站，也不会让 AI 判断某个人、公司或产品“就是诈骗”。确定性 Policy Engine 处理可证明安全的常规类别，只有例外才交给人决定。

[North Star](docs/North%20Star.md) 是本项目最高层级的产品方向；功能、自动化和基础设施决策都不得以牺牲证据、信任或用户避免伤害的结果为代价。

## 当前状态

仓库目前是一个采用 Apache-2.0 的 **offline-first V0.1** 公益项目：默认只使用 fixtures、recorded AI responses 和本地文件/数据库测试。公开代码不包含生产数据；完整边界见 [open-source boundary](docs/open-source-boundary.md)。公开的 [fixture preview](https://preview.insparian-scam-radar.pages.dev/) 只演示测试数据，并非实时诈骗数据库。Frankfurt Supabase 中只有空生产 schema 和一个 reviewer 身份；专用 reviewer preview 已部署，并由 Cloudflare Access 和 Supabase Auth 两层保护。它与公开 fixture preview 分离，尚未接收真实 evidence。所有真实来源都在 `config/sources.yaml` 中保持 `enabled: false`，以下功能尚未获准启用，也不能视为已完成线上验证：

- 真实网站采集；
- Gemini API 调用；
- 真实 evidence 的 production Supabase 读写；
- 加密 R2 数据库备份；
- 真实数据的 production Pages 发布或 DNS 修改；
- 任何 analytics、telemetry 或用户搜索词上传。

离线构建的目标是先证明核心链路：来源条目 → 去重 → AI proposal → Evidence Gate → Scam Heat → Policy Engine → safe/review/blocked 分流 → 不可变修订与同一 `release_id` 的静态页面和本地搜索。

V0.1 的 `safe_to_automate` 只运行影子模式：系统记录固定规则“本可自动处理”的结果，但不会授予自动发布权限，仍需人工确认。模型置信度永远不能提权；低或未知置信度只能把原本安全的候选降级为 `review_required`。数据库的 live-policy allowlist 当前为空；未来也必须用 forward migration 绑定获批的精确 policy version/hash 和 Evidence Gate version，不能靠一个布尔开关放行。

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
| `make open-source-audit` | 扫描当前文件、完整本地 Git 历史和公开仓库边界，不输出发现的密钥值 |

这些命令是仓库对人的稳定入口。内部工具可以变化，但不要让 Rui 记住多套子目录命令。

## 安全边界

- Public pages 和 search index 必须来自同一个 immutable `release_id`。
- Public search 只在浏览器本地运行，不发送或保存搜索词。
- AI 只提出建议；Evidence Gate 与确定性 Policy Engine 决定发布边界，登录的人只处理例外及 V0.1 影子确认。
- `evidence.last_verified_at`、`revision.verified_at` 和 `release.published_at` 各有独立含义；最后一个表示内容冻结进入不可变 public-release manifest 的时间，Cloudflare 部署另有时间。公开“信息核实至”取当前修订所有 claim-support 证据核实时间的最小值。证据可能在修订判定后再次核实，所以前两个时间没有固定先后，但都必须存在且不晚于 release freeze。
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
| `config/` | Reviewed sources、taxonomy、models、scoring 和 publication policy behavior |
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

## Open source

软件和项目原创文档默认使用 [Apache License 2.0](LICENSE)。品牌、第三方来源材料、生产数据库、未发布候选、审核记录和备份不在该授权范围内；详见 [NOTICE](NOTICE) 和 [公开/私有边界](docs/open-source-boundary.md)。参与前请阅读 [贡献指南](CONTRIBUTING.md)、[行为准则](CODE_OF_CONDUCT.md) 和 [安全报告方式](SECURITY.md)。

External paths are activated independently. Before enabling one, show Rui that path's exact destination, outbound data, purpose, limits, credentials, and stop control. Before live collection and the complete production launch, this expands to the first five exact source URLs, Supabase region, bounded Gemini payload, all required secrets, Cloudflare account-level token scope, and encrypted-backup recovery-key custody and retention.
