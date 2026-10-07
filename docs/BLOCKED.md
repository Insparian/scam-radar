# 离线验收阻塞与外部关卡

## 2026-10-07 Decision 015：Cloudflare 隔离账户与 KV 备份

- 两组离线改动、Worker 账户保护及新账户 ID 配置已在 `codex/supabase-preflight` 验证；完整离线套件通过。提交/推送状态见 `docs/PROGRESS.md` 当日条目。
- Rui 回复 `proceed` 后，已在同一登录下创建专用 `Scam Radar` Cloudflare 账户，账户 ID 已写入版本化配置。Billing 显示 `Workers Free` Active，未绑定付款方式；现有共享账户其他 Workers/KV 未改。现有预览仍在共享账户，尚未迁移或检查线上站点。
- 新 KV 备份协议只在本地合成数据验证；真实路径将是 Supabase → 受保护的 GitHub runner → 加密 → 独立账户 Workers KV。备份 Worker 只负责唤醒 GitHub，不持有数据库或 KV 密钥。没有创建 Worker/KV、读生产数据或上传。
- **上线仍阻塞：** 需另行批准创建 Pages、Worker、KV 等资源与预览迁移。KV 创建表单已备好空命名空间名 `scam-radar-encrypted-backups`；EU 持久存储与 Standard 全球存储的选项和创建授权正在等 Rui 答复，未提交。新账户 Pages 的精确项目名/返回域名要先确定，旧预览工作流仍写死旧账户项目名和 URL，不能直接切换令牌重跑。实测真实密文体积不超过 64 MiB、确定不超过 1 GB 的保留/删除策略、恢复密钥保管、独立数据库完整恢复及备份缺席/容量告警。当前没有自动删除，长期每日备份会耗尽容量。既有共享账户的 Secrets 不能沿用。
- 容量保守上界：14 份各 64 MiB 的备份已占 939,524,096 字节，若按 1 GB=10 亿字节，剩余不足再写一份上限备份；还未计未提交的分块。不能把“每天备份”视为可持续，真实体积测量和获批的保留/删除规则仍是独立上线门槛。
- 真实来源、模型、生产迁移、发布、DNS、大陆访问与 7 天稳定性关卡仍开放。下文 R2 是历史候选，现行计划见 [KV 备份](runbooks/kv-backup.md) 与 [账户分工](runbooks/dedicated-cloudflare-account.md)。

## 2026-10-07 账户创建前只读核查后具体阻塞（历史状态）

- Cloudflare 现有账户还承载 Rui 的其他项目 Workers 与 KV 命名空间，不能把新建 Scam Radar 命名空间误认为账户/权限隔离。Rui 已对独立 Free 账户的 Decision 015 回复 `proceed`；离线实现已本地提交，尚未创建账户、部署、迁移预览、上传或改 DNS。当前共享账户及其他项目未修改。
- 历史评估：Cloudflare Workers KV Free 官方额度为 1 GB 存储、单值 25 MiB、每天 1,000 次写入；超额操作失败而非自动收费。账户控制台曾只读确认共享账户 Workers `Free`，但这不证明新独立账户的最终套餐。Decision 015 已在离线代码中改用 KV 与独立备份 Cron；真实容量、保留期、完整恢复和缺席告警仍未验收，不能宣称备份持续运行。
- 自动监测不能只依赖 GitHub Actions 的定时触发：公开仓库连续 60 天无活动会自动停用计划工作流。Rui 已用 `proceed` 批准 Decision 014 的离线设计：Cloudflare Workers Free Cron → 单来源 GitHub `workflow_dispatch`；本地代码移除 GitHub schedule，Worker 默认关闭。尚未创建 Worker、配置令牌、触发真实任务或验证远端状态；也没有独立的缺席告警，不能宣称长期持续监测已经验收。启用 F10 与真实采集仍需单独最终批准。
- 历史判断：Rui 限定只开真正免费的 Cloudflare 服务；当时考虑沿用现有 Pages。Decision 015 已改为独立 Free 账户。R2 开通须接受按量计费，故不启用。Supabase Free 不含项目定时备份；KV 虽有离线实现，尚无批准的真实保留/恢复方案，真实数据写入与恢复关卡继续阻塞。
- 已核对现有 GitHub Actions artifact 作为免费备份候选：公开仓库的登录读者可下载 artifact，GitHub Free 的 artifact/Packages 共享存储额度为 500 MB，公开仓库 artifact 最长保留 90 天，超额可能计费或在硬预算下停止。它既不是已批准的私有 R2 目的地，也不能在当前约束下保证备份持续成功；未上传任何生产数据。
- Cloudflare 免费全球网络不提供中国境内节点保障；中国网络需 Enterprise 加独立订阅和 ICP 备案。`scamradar.insparian.com` 还没有正式部署/DNS，不能声称大陆可用。先做三网、iOS/Android、微信实测；若大陆稳定性不达标，阿里云内地部署又涉及付费与备案，当前约束下暂不启动。
- Rui 单独授权恢复后，现有 Frankfurt Supabase `scam-radar` Free 项目已显示 Healthy。线上迁移只到 `20260917000100_evidence_resolution_events`（7 个），仓库现有 22 个，后续 15 个仍未应用。恢复项目不等于授权生产迁移或业务读写；执行前须有可验证备份/回退方案、逐项迁移审阅及既有精确确认。
- 待应用的 `20260920000600_irrelevant_text_retention.sql` 会执行一次 `UPDATE`，将所有已标记 `irrelevant` 且仍有正文的旧版本 `clean_text` 置空；后续触发器也会在转为 `irrelevant` 时置空。这是不可逆的生产数据清理，不能与普通新增表/RPC 合并默许。生产 foundation 工作流现在会在迁移前只读核对版本和空库状态，若有旧业务数据/待清理正文则在 `db push` 前停下。非空库须另做迁移计划、统计影响、验证备份/独立恢复并取得 Rui 的精确确认；当前未查询生产行数，也未应用。
- Supabase 的 Free 备份页面明确显示不含项目定时备份。Data API 设置显示 `0 of 24 tables exposed`、`0 of 50 functions exposed`，自动暴露新对象关闭；审核站所需 RPC 在生产环境是否可调用尚未验证。不得以本地 grants/RLS 通过推断云端审核链已可用。
- Cloudflare 公开站及审核站 Pages 项目均无 production 部署；公开站没有 custom domain，目标 `insparian.com` 的 DNS 由 Rui 确认在 Namecheap。须在发布确认前核对 Pages 返回的精确 CNAME，不能预设或修改 DNS。
- R2 尚未开通，开通页要求接受可按量计费的自动续订服务；当前不能做真实离站密文备份/恢复。不要以免费额度推断绝无费用。
- 5 项远端 Dependabot 告警所涉四组包已更新并推送，GitHub 重扫确认 open 0。在线 npm 审计另有 5 个 high，均在 `eslint-config-next` 开发工具链；生产依赖审计为 0。官方自动修复建议降到不匹配的 Next 14 配置，不能为消除数字直接采用。真实上线仍受下列云端与质量关卡阻塞。
- 百炼评测与 worker Key 已由 Rui 填入本地忽略的 `.env`，但尚未核验额度、有效性或调用；真实样本授权/双人标签与模型质量仍未核验。GitHub Actions 凭据须另配 Secrets/Variables，且激活开关维持关闭。

## 2026-10-07 P1 关闭；真实上线关卡仍开放

10 月 6 日暂缓跨来源重复建骗局反例已由前向迁移 `20261006000100_held_approved_matching.sql` 修复并在 22 迁移全新库复跑。未修改独立脚本比较旧批准版本一次、延后另一来源、重试次数 0；新增真实进程/浏览器回归覆盖暂缓未结束时两轮冲突、批准与拒绝两种结局，均续入原模式且不重复发布。九个根命令针对最终离线代码状态通过，见 [OFFLINE-ACCEPTANCE-REPORT.md](OFFLINE-ACCEPTANCE-REPORT.md)。**已知本地代码阻塞为 0；仅代表离线合成验收。** 以下 10 月 6 日 P1 段保留为历史红证据，不再代表当前状态。

**真实上线仍阻塞：** 真实来源的精确栏目/许可/robots，百炼当前模型余额/到期日和 100 个获准历史样本双人标注质量，生产 Supabase 精确配置与真实密文恢复，七天运营负担，大陆三网络及 iOS/Android/微信内置浏览器访问。真实模型调用、采集、生产写入、备份上传、发布、DNS 继续要求独立最终激活批准。Rui 已确认北京工作区免费额度用完即停；账户存在 89 个免费模型不代表本候选质量已达门槛，也不授权调用。模型可在评测后换，不能静默自动回退。


## 2026-10-06 独立复核：早拒绝已修复，暂缓期间跨来源匹配仍阻塞

本节取代下方“已知本地代码阻塞为 0”的整体结论。提交 `f7fa658` 的原始早拒绝
反例已独立复跑通过；不是该修复再次失败。新增反例是合法暂缓状态与另一来源交错。

- **P1 — 暂缓补证使已批准骗局退出匹配，新来源建立重复骗局。** 在从零应用
  21 个迁移的本地合成库，已有批准模式收到追加证据；事务提交后进程退出，
  reviewer 通过真实 Auth/RPC 执行 hold。模式仍有原 approved revision，
  但 lifecycle 变为 `evidence_pending`。另一来源发送同类合成文章时，实际
  模式比较调用为 0，worker 返回 success、review_items=1，并创建了独立
  `new_pattern` 目标，而非对已有模式待审冲突安全延后。
- 根因：迁移 `20260929000100_reviewed_update_recovery.sql` 220–224 行的
  hold 仍改变整个模式 lifecycle；`20260920001000_pending_update_deferral.sql`
  49–50 行只返回 `review_ready` 的批准模式。恢复拒绝后的 lifecycle 不足以
  保证暂缓仍有效期间的匹配。现有暂缓测试在完成批准/拒绝后才进入下一来源，
  未覆盖此交错。
- 实际审核目标：原 `pattern_update` 指向
  `5f52f66a-de66-41f4-9adb-61e649fc5188`；新 `new_pattern` 指向
  `8026be09-5c96-46c9-a37a-004e41b715c2`。均为本次本地合成数据。
- 下一步：明确批准版本的可匹配性与草稿审核状态的关系；暂缓不能使仍有效的
  已批准模式不可见，候选仍须仅来自允许使用的批准版本，另一来源仍须遵守
  待审冲突门槛。补“hold 未结束→另一来源同类证据→延后→原审核解决→续跑”
  真实数据库回归，不能把未批准草稿当作已知事实或放宽自动发布权限。
- 复现脚本/证据：`work/leader06-held-conflict.py`、
  `work/leader06-held-conflict.log`。原早拒绝绿证据：
  `work/leader06-original-repro.log`。栈路径：`work/leader06-stack-path.txt`。

## 2026-09-29 早拒绝反例已修复并通过本地复跑

独立复核发现的“证据提交后中断，人工先拒绝，再重启四次均失败”已用前向迁移 013 和 worker 持久收据状态分流修复。**未修改的独立复现脚本** `work/leader29-early-reject.py` 在最终 21 迁移的全新 joined 栈退出 0：首次重启完成来源、推进游标；其后三次保持原证据/修订/审核 ID、人工拒绝和 Policy 0，不重复处理。红/绿证据分别为 `work/leader29-early-reject.log`、`work/leader29-independent-repro-green.log`。另补暂缓后 Policy/人工批准、旧暂缓后人工拒绝、伪造拒绝无事件、越权与发布/恢复回归；九个根命令对同一最终代码状态退出 0，见 [OFFLINE-ACCEPTANCE-REPORT.md](OFFLINE-ACCEPTANCE-REPORT.md)。**当前范围内已知本地代码阻塞为 0**；真实环境/授权关卡仍按下文保持关闭。以下复核失败段保留作历史记录。

## 2026-09-29 第二次独立复核：当时 P1 重新打开（历史）

本节取代下方执行方“本地代码阻塞已关闭”的结论。对提交 `f9649db` 的独立
复核确认原中断点和仓库新增回归通过，但仍有合法人工操作导致恢复永久失败。

- **复现：** 在本次从零应用 20 个迁移的合成栈，真实证据事务提交后退出 73，
  此时 Policy 尚未写入。审核员通过真实浏览器点击“不公开”并成功完成拒绝。
  模拟原认领到期，连续重启四次，均返回 `degraded` 和
  `existing_recovery_read_failed`；版本从 attempt 1 增至 5，仍为 `error`，
  游标为空；原证据/修订/审核记录各 1、Policy 0，人工拒绝保持不变。
- **根因：** `20260928000100_existing_update_recovery.sql` 在无 Policy 时
  只接受 pending 且仍占用草稿的状态（128–130 行），但现有合法拒绝 RPC
  不要求 Policy 已写入，且会清空草稿。worker 的补录分支也只接受 pending。
  因此已有人类终态决定的原事务无法收尾，012 放开重试上限只会反复报错。
- **为何现有测试漏掉：** `local_existing_crash_e2e.py` 仅在 after_policy
  场景中先人工拒绝；after_submit 场景是先恢复、再拒绝，未覆盖相反次序。
- 本轮进一步发现：旧 `hold_for_evidence` 会改变已批准模式的 row_version 与 lifecycle；审核员随后拒绝虽清掉草稿，却仍留下 `evidence_pending`，使后续来源无法匹配已批准模式。新前向迁移和真实数据库回归正在同时覆盖这条时序；全新最终套件通过前 P1 继续开放。
- **下一步：** 先列明“事务/Policy/人工决定/来源版本”的合法状态与恢复规则，
  基于持久收据和真实人类决定安全完成终态收尾；不要仅增加重试，不得伪造
  Policy、绕过审核或覆盖人类拒绝。补上无 Policy 时人工终态/暂缓操作与中断
  交错的真实数据库回归，再做全套验收。
- 独立脚本与失败证据：`work/leader29-early-reject.py`、
  `work/leader29-early-reject.log`；本次栈路径 `work/leader29-stack-path.txt`。
  未修改产品代码；外部激活仍为 0。

## 2026-09-29 本地代码阻塞已关闭

9 月 28 日独立复核发现的 P1 已用前向迁移 011/012 和 worker 原收据恢复流程修复，并在最终 20 迁移的独立新栈上通过全部根验收。真实进程退出、数据库已提交但响应丢失、Policy 已提交后退出、连续三次退出和人工批准/拒绝后的恢复均保持原证据/修订/审核/Policy 唯一；旧持有者、越权角色、篡改候选及无收据超三次仍被拒绝。红→绿与最终命令见 [OFFLINE-ACCEPTANCE-REPORT.md](OFFLINE-ACCEPTANCE-REPORT.md)。**当前范围内已知代码阻塞为 0**；下列只有需真实环境或 Rui 最终授权的关卡，均未激活。保留以下旧复核段作为历史失败记录。

## 2026-09-28 独立复核：当时离线验收未通过（历史）

本节取代下文 2026-09-27 的“范围内已知代码缺口为 0”结论；历史测试结果仍保留。

- **P1 — 已有骗局追加证据在入库后中断无法恢复。** 独立新建本地栈、从零
  应用 18 个迁移并通过 `make database-test` 后，使用真实 localhost 模型协议和
  PostgREST，在 `submit_existing_pattern_evidence` 已提交、worker 尚未记录
  Policy/完成版本时终止进程（退出 73）。模拟本条合成数据的认领/租约到期后，
  连续两次重新运行均返回 `degraded`、`pending_review_deferred=1`；版本保持
  `pending_ai:pending_review_conflict`，证据收据为 1，关联 Policy 记录为 0。
- 原因：`worker/src/scam_radar/durable.py` 在恢复已有事务收据前，先把自己
  遗留的待审草稿当作其他任务的冲突；因此无法补完剩余步骤。这是代码缺口，
  不是外部授权或真实数据条件。需要区分本版本已提交事务与其他版本的待审冲突，
  安全恢复原收据和后续步骤，并补真实进程中断回归测试；不得放宽冲突/审核门槛。
- 2026-09-28 新隔离栈再次重现（`work/crash-recovery-20260928/red-*.log`）：
  原提交收据 1、Policy 0；租约到期后的重启仍降级。旧 SQL 的重放返回
  缺少首次的 `missing_claim_count`，候选哈希包含会随日期变化的 Heat；
  直接重新提交不足以证明可恢复。修复须先查持久收据及已有 Policy。
- 修复已在旧红灯库的原孤儿收据上探针通过（收据 1、Policy 0→1、版本完成、
  游标推进、模型调用 0），但**尚未达到离线验收**：需要从零应用 19 个迁移，
  跑仓库化全部中断位置/人工决定/跨任务冲突回归及所有根命令。旧库探针
  不能代替全新迁移证据；P1 保持开放。
- 19 迁移的新库数据库契约与四个真实中断/丢响应回归现已通过，包含
  审核批准/拒绝和另一来源待审冲突。**剩余本地工作**是最终代码状态的
  `make check/test/eval/demo/collect-dry-run/database-test/joined-local-e2e/`
  `deployment-local-e2e/recovery-rehearsal` 串行复核及验收报告更新；在此
  之前 P1 不关闭，也不声明离线就绪。
- 扩展故障注入发现三次连续进程中断仍触发旧认领上限，且错误报告 success；
  已新增前向迁移 012 并在同一红灯收据上探针恢复，证明仅已提交事务可越过
  上限，未提交事务上限必须在全新库 SQL 契约中保持。最终完整套件仍待复核。
- 复现脚本与输出：`work/leader-crash-audit.py`、`work/leader-crash-audit.log`。
  专用合成栈路径在 `work/leader-audit-stack-path.txt`；本次未修改产品代码。
  修复并复核通过前，不应把最终授权包标为可激活。

2026-09-27 本地代码与全流程验收已通过，见
[OFFLINE-ACCEPTANCE-REPORT.md](OFFLINE-ACCEPTANCE-REPORT.md)。范围内已知代码
缺口为 0；下列事项都需要真实环境或 Rui 的集中授权。此文件本身不授权执行。

1. **真实来源与许可：** `config/sources.yaml` 的 15 个候选仍全部关闭。
   需要选一个精确栏目/文章入口，核对条款、robots、稳定解析和许可。
   机构首页不能代替文章入口。
2. **真实模型与质量：** 只选一个 provider/model/地区/端点及专用凭据，
   核对数据条款、当前价格/额度与账户硬限。至少 100 个获准历史样本由
   两人独立标注并裁决，锁定 holdout，按真实质量门槛评测严重误判与漏判。
   100 个 recorded 合成案例不代表真实质量；`launch_qualified=false`。
3. **生产数据、备份与稳定性：** 精确核验 Supabase 项目、迁移/角色/RLS，
   在独立库恢复一个实际 R2 密文对象并核对 release、权限与数据；持续
   观测七天来源/模型/审核负担。真实业务读写和备份上传仍关闭。
4. **公众真实访问与发布：** 大陆至少三种网络、iOS/Android、微信内置
   浏览器的关键路径与主观可读性尚未验收。只有这些关卡通过，才能把
   真实审核产生的 `release_id`、commit、manifest/artifact hash 和 Pages
   项目绑定到精确发布对象，并另行确认发布、DNS 及回退操作。

集中审阅对象与既有精确批准门槛的关系见
[ACTIVATION-CHECKLIST.md](ACTIVATION-CHECKLIST.md)。真实来源、模型调用、
生产读写、备份上传、Pages 发布和 DNS 本轮均为 0。

## 范围扩展待决策

无。聊天、传播、视频、付费回退和架构迁移仍不在 V0.1。
