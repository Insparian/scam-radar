# 离线就绪后的最终集中确认包（草案，尚未授权）

这是一份供 Rui 最后一次集中审阅的授权对象，不是执行指令。
当前代码与本地验收的实际状态以 [PROGRESS.md](PROGRESS.md) 和
[BLOCKED.md](BLOCKED.md) 为准；任何红项都不得被本单覆盖。
本次任务只交付离线代码和本包，不执行真实试运行或正式发布。
下列推荐值不是已有授权。

## 一次审阅，分关卡执行

现有方案写作“分两次激活”，与本次“一份集中确认包”并不等于同一时间
放开所有开关。建议 Rui 在一个包里审阅完整试运行及发布边界，但保留仓库
已有的精确批准门槛：

1. **真实试运行关卡**：只选一个来源、一个模型与地区、一个专用凭据组，
   逐条人工审核；不发布、不改 DNS。具体来源栏目、许可、robots、模型
   价格/额度和真实数据范围须先填入本包。预算或来源验证未完成时不开关。
2. **正式发布关卡**：在真实样本质量、连续七天稳定性、真实备份恢复、
   大陆及微信访问验收通过后，另以精确 `release_id`、代码 commit、
   manifest/hash、审核记录和目标域名执行既有发布确认。未知值不得预填；
   未通过任一关卡就保持现有静态站，不启用 DNS。

集中审阅不能代替 `BACKUP APPROVED CIPHERTEXT ONLY`、
`DEPLOY APPROVED IMMUTABLE RELEASE` 等已有精确确认，也不能代替受保护环境
审批。确认后的执行另行开展。

## 集中确认时必须填实的对象

| 对象 | 当前值 | 确认前证据 |
| --- | --- | --- |
| 首个来源 key、精确栏目 URL、robots/条款 | 待选；15 项均关闭 | 逐项许可、解析样本和停止条件 |
| 单一模型 ID、地区、端点、数据条款 | 待选 | 专用 key、价格/配额核验日期、账户硬限 |
| 试运行真实数据与费用上限 | 0 次真实调用、0 美元实际支出 | 获准历史样本范围、≤10 次/≤1 美元评测硬限、后续批次上限 |
| 生产数据库与 reviewer 凭据 | 待现场核验 | 精确项目/角色/RLS、独立恢复通过 |
| 正式发布对象 | `release_id`、commit、manifest/hash 均待真实审核产生 | 人工决定、同一 release 导出/构建/搜索校验 |
| Pages 项目/分支及 DNS 值 | 待现场核验 | 精确项目、回退原产物、Pages 返回的 CNAME |

批准记录须写明以上各项和允许的阶段；缺值时相应阶段保持关闭。
上传前从批准的 `release_id` 导出一次不可变清单，以同一代码 commit 构建
页面、详情和搜索并计算产物 SHA-256；将这组 ID/hash 与人工审核记录绑定到
发布确认。上传及登记必须复用同一产物，回退使用保存的原产物。正式发布前
再运行 `evals/expected/quality-gates.json` 的全部适用真实质量门槛与人工严重
错误审查，不能凭本地 100 个合成案例代替。

不启用自动事实批准，不串联多个模型，不开付费回退。

## 来源范围与推荐

当前注册表只有机构首页，不能冒充已经验证的采集栏目。
推荐首批候选顺序为金融监管总局、公安部、上海公安、消费者协会、新华社；
依据是分别覆盖监管提醒、执法案例、地方案例、消费风险与可信媒体。
真正首个来源须按公开采集许可、可解析栏目、robots 与稳定性择优，不能凭机构级别直接启用。

| 候选 | 当前登记的精确地址 | 是否可激活 |
| --- | --- | --- |
| 金融监管总局 | https://www.nfra.gov.cn/ | 否，具体栏目与条款未核验 |
| 公安部 | https://www.mps.gov.cn/ | 否，同上 |
| 上海公安 | https://gaj.sh.gov.cn/ | 否，同上 |
| 消费者协会 | https://www.cca.org.cn/ | 否，同上 |
| 新华社 | https://www.news.cn/ | 否，同上 |

全部 15 个候选及地址仍以 `config/sources.yaml` 为准。首轮推荐最多 5 篇、
单来源、每请求至少间隔 1.5 秒、20 秒超时、单响应 1 MB，正文最多 50,000 字符；
理由是逐篇复核负担可控。遇到登录、验证码、明确禁采或 robots 拒绝立即停该来源。
执行前须在受保护环境把 `SCAM_RADAR_APPROVED_SOURCE_KEY` 精确绑定到这一个
已验证的注册表 key；工作流拒绝 `all` 和与此 key 不同的手动输入，单批最多
5 篇、10 次模型尝试。超过预算的条目保持待处理，不能自动扩大。

## 外部目的地、字段、权限和停止方式

| 目的地 | 允许候选数据 | 推荐凭据与上限 | 停止方式 |
| --- | --- | --- | --- |
| 批准的来源域名 | URL、联系 User-Agent、请求时间和 runner IP | 无登录凭据；首轮 5 篇，单批 50 HTTP 尝试上限 | collection 开关 false；来源 enabled=false |
| **选定一个**模型端点 | 已脱敏公开正文、固定 prompt/schema、候选模式信息 | 专用 API key；首轮最多 10 次，单输入 10,000 字符、输出 4096 tokens；未核实免费额度前费用预算为 0、禁止调用 | AI 开关 false；不自动换模型 |
| 现有 Frankfurt Supabase | 来源元数据、受限正文、AI 结果、证据映射、Heat、审核/发布状态 | worker 仅狭窄 RPC；禁止直接表写、禁止代替 reviewer；实际地区/配置须激活前再核验 | 停采集/AI；保留旧静态网站 |
| Supabase Auth/reviewer | 登录会话、证据决定、审核理由 | 现有独立 reviewer；Auth 登录不等于角色授权 | 禁用 reviewer、撤销会话；保留审计 |
| Cloudflare Pages | 通过扫描的同一 release 静态产物 | Pages Write，不授 DNS/Workers/R2；令牌影响同账户项目，非单项目隔离 | deploy=false；不影响现有页面 |
| 私有 R2 | age 密文、随机对象名、SHA-256、字节数及时间；不含明文 dump | 独立私有桶，仅对象读/列举/写权限以便回读校验；无删除/桶管理；每日 02:43 UTC 一次，推荐保留 7 日+4 周，删除策略另行明确批准 | backup=false；禁止公共访问 |
| 公众浏览器 → Pages | 页面/静态资产请求、普通访问元数据 | 无用户账户、无跟踪 SDK；关键词仅在内存 | 无搜索上报路径 |

模型目的地分别为智谱 `open.bigmodel.cn`、百炼所选地区的 DashScope/工作区域名、
Google `generativelanguage.googleapis.com`。确认一个不代表授权另外两个。
Qwen 地区绑定 key；当前官方兼容文档正文存在 Beijing 示例地区不一致，
推荐激活时以控制台实际工作区地区和文档迁移说明核对，不照抄错配端点。

## 模型核验记录（2026-09-18）

- GLM-4.7 的模型 ID、聊天端点及结构化输出能力见 [智谱官方文档](https://docs.bigmodel.cn/cn/guide/models/text/glm-4.7)。价格页依赖动态内容，价格和账户额度未完成核验；不能当作免费。
- Qwen Plus 的固定候选版本为 `qwen-plus-2025-09-11`，见 [官方模型页](https://www.alibabacloud.com/help/en/model-studio/qwen-plus)；不同地区与思考模式费率不同，候选地区报价和账户额度未完成核验。兼容协议见 [官方接口页](https://www.alibabacloud.com/help/en/model-studio/compatibility-of-openai-with-dashscope)。
- Gemini 2.5 Flash 官方标准付费文本价为每百万 input/output tokens $0.30/$2.50；也列免费层，但免费层数据可用于产品改进。见 [官方价格页](https://ai.google.dev/gemini-api/docs/pricing)。实际可用额度应查所选项目，不能沿用旧对话中的额度数字，见 [官方限制说明](https://ai.google.dev/gemini-api/docs/rate-limits)。

推荐三者用同一人工标注数据集、同一划分、相同输入与调用上限分别评测；
每次只批准一个候选端点，不并行开通。至少 100 个获准历史样本由两人独立
标注并裁决，锁定 holdout/hash；流程见 [evals/README.md](../evals/README.md)。
评测入口默认仅 localhost，可计算相关性、类别、应对动作、模式匹配、
实质变化、延迟和费用保留上界；单次硬上限 10 次尝试、1 美元，失败及重试
都计入。真实端点还需已核价格、地区、账户硬限、专用 key 和单独开关。
记录失败也计入分母，优先比较严重误判、证据支持、漏判，其次看延迟和费用。
目前没有真实质量赢家；100 个 recorded cases 是合成契约验证，
`launch_qualified=false` 保持不变。

## 备份与恢复验收

推荐 RPO 24 小时、RTO 4 小时作为初始目标，不声称已测到。
恢复 identity 离线两份保管，CI 仅保存 age public recipient；不上传明文。
备份执行器固定 PostgreSQL 17.9 官方镜像摘要、age 1.3.2 与 rclone 1.75.1
校验值，见 [ADR-008](decisions/008-free-tier-continuity-and-encrypted-backups.md)。
它需要 Supabase 直连或 session 连接的**精确主机/用户**、数据库密码、从 Supabase
后台取得的 CA 证书，以 `verify-full` 验证 TLS。推荐先用真实对象恢复一次，
再开启每日定时；当前仅合成库 → 本地 S3 的密文回读和合成库恢复通过。
推荐 R2 凭据仅本桶对象读/列举/写，不能删除，方便核验而不扩大破坏权限。
真实数据写入之前必须完成独立恢复，验证各表计数、RLS、worker 无审批权、
exact release 导出相同。合成演练证据见 PROGRESS；合成密钥不能用于生产。

## 发布、DNS 与失败撤回

- 提交确认的对象必须包含代码 commit、release_id、manifest/artifact hash、来源及人工审核证据；缺任一项不发布。
- 推荐先 preview 检查，再上传完全相同的产物到生产；登记失败按“已上传待对账”处理，不能误报未发布。
- 新版构建或 preview 失败保持当前版本；上传后的 smoke 失败回退到保存的原产物，不能重新查询可变数据构建所谓旧版。
- DNS 仅涉及 `scamradar.insparian.com`；先在 Pages 添加域名，再使用其实际返回的 CNAME。禁止猜记录或修改 apex。
- 紧急错误内容先经 reviewer 生成下架 release，再构建部署；数据库标志不等于网站已下架。旧 preview/CDN 副本的处理另行明确。

## 真实环境必须补测

人工标注 Gold Set；真实模型质量/价格/额度；每个来源条款/robots/解析和七天稳定性；
审核队列实际负担；真实 R2 恢复；大陆至少三种网络、iOS/Android 和微信内置浏览器。
推荐至少 10 次关键路径尝试、成功率 ≥90%，记录中位数/p95；当前均不能用本地 Chromium 代替。
