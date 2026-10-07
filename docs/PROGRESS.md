# V0.1 offline launch readiness

## 2026-10-07 免费版与中国大陆访问决定

- Rui 明确只开 Cloudflare 真正免费的服务，不开通其他服务。现有 Cloudflare Pages Free 项目不需另建；R2 虽有月度免费额度，开通仍接受按量计费，故未启用、未创建桶、未上传。此约束使当前真实密文离站备份/恢复关卡继续阻塞。
- [Cloudflare 中国网络](https://developers.cloudflare.com/china-network/get-started/)要求 Enterprise 方案、独立订阅及 ICP；Pages Free 不能据此获得境内节点或可用性保证。[阿里云内地托管](https://www.alibabacloud.com/help/en/icp-filing/basic-icp-service/product-overview/icp-filing-requirements-for-a-regular-website)需备案且属于另行付费选项。未检查既有预览站；正式域名尚未发布，须按 `docs/BLOCKED.md` 的三网/设备/微信关卡实测后再决定是否迁移。
- 只读调研现有 GitHub Actions artifact 备份候选：[GitHub 费用说明](https://docs.github.com/en/billing/concepts/product-billing/github-actions)列出 GitHub Free 共享 artifact 存储 500 MB；[公开仓库下载与保留规则](https://docs.github.com/en/actions/how-tos/manage-workflow-runs/download-workflow-artifacts)允许登录且有读权限者下载，最长保留 90 天。硬预算可停超额使用，但也会让备份失败。未改架构、未上传；不能用它默默替代私有 R2。

## 2026-10-07 Supabase 项目恢复与线上配置核查

- Rui 明确授权操作后，恢复现有 `scam-radar` Free 项目；控制台显示 Healthy，地区仍为 `eu-central-1`（Frankfurt），项目 URL 为 `https://eswsxqgsdwsovuapvtld.supabase.co`。未读取密钥、业务数据或执行 SQL。
- 线上迁移清单只有首批 7 个，最新为 `20260917000100_evidence_resolution_events`；仓库有 22 个前向迁移，故 15 个待应用。仅作只读比较，未运行生产迁移。
- Free 备份页面明确显示不含项目定时备份。Data API 控制台显示 0/24 张表、0/50 个函数对 API 暴露，自动暴露新对象关闭；这使审核站 RPC 可用性成为待验证项，不能凭本地测试宣称生产可用。未改 API/grants/RLS 配置。
- 生产迁移、数据库读写、真实来源/模型调用、备份上传、Pages 发布和 DNS 均保持关闭。具体阻塞见 `docs/BLOCKED.md` 顶部。
- 生产迁移 workflow 的 `scripts/supabase_foundation.py` 原来只查首批 7 个迁移，漏装后续版本仍可能报绿，且成功文案误写 6。已改为从仓库迁移文件读取完整版本集合，要求数据库版本集合精确相等。新增回归测试；在本机合成 PostgreSQL 上实际执行相同 SQL，22 个版本返回 true，故意去掉 1 个期望版本返回 false。`make check`、`make test` 通过（141 Python、9 浏览器）；首次测试因沙箱拒绝 localhost bind 失败，获准本机回环后通过。未连接生产数据库。
- 复查公开导出时确认 `worker/src/scam_radar/storage/public_export.py` 与 `docs/public-export-mapping.md` 已提供数据库 v2→网页展示的确定性映射，`make database-test` 覆盖真实本地 SQL 导出及缺字段负例；`supabase/README.md` 的“尚待选择映射”是过期说明，已更正。当前公开网页仍展示合成 fixture；真实审核 release 尚未产生，不能据此发布。
- 修复提交 `85db490` 已推送；[GitHub Offline CI 37566854221](https://github.com/Insparian/scam-radar/actions/runs/37566854221) 的应用与从零 PostgreSQL 两个作业均通过。

## 2026-10-07 远端离线 CI 恢复绿色

- 提交 `ae0f101` 的 GitHub Offline CI 应用作业通过，数据库作业因未安装锁定 Python 依赖而报 `ModuleNotFoundError: pydantic`。`c52d859` 给数据库作业补 Python 3.13、uv 锁定依赖和网页端锁定依赖后，真实 SQL/公开导出通过，但合成流水线测试把 Docker 固定到 macOS Rancher Desktop 路径，Linux runner 报 `FileNotFoundError`。
- 提交 `f79ffc0` 让合成流水线测试优先使用 `DOCKER_BIN` 或 PATH 中的 Docker，默认容器名与 `supabase/config.toml` 一致。GitHub [Offline CI 运行 37555107222](https://github.com/Insparian/scam-radar/actions/runs/37555107222) 两个作业均通过，包括从零启动本地 Supabase、数据库契约、审核与静态构建。`make check` 与本地配置检查通过。真实生产项目仍暂停；远端 CI 不代表真实模型、来源、备份或发布已激活。

## 2026-10-07 云端填写项与上线反馈复核

- 再次只读确认 Supabase `scam-radar` 仍暂停，Cloudflare 公开 Pages 项目仍只有 preview、没有 production 部署；未点击恢复、上传或 DNS。
- 只检查本地忽略的 `.env` 字段状态，未展示或输出密钥值：百炼评测与 worker Key 已填，六个激活开关均为 false；Supabase、Cloudflare、R2 与公开 reviewer 字段仍未填。`.env` 不会自动进入 GitHub Actions。
- `docs/runbooks/initial-setup.md` 已按实际 workflow 列出各阶段 GitHub Variables/Secrets 及其存放位置，提醒采集使用 repository-level 凭据且激活开关保持关闭。
- 生产迁移工作流原报告写死旧迁移版本号，现改为显示实际迁移步骤结果并要求核对 Supabase 已应用版本；迁移与 reviewer 报告的旧 Gemini 字样改为通用 live AI。未改变任何云操作、请求或权限。
- `make check`、修改过的 workflow YAML 解析与 `git diff --check` 通过。外部激活仍为 0；恢复 Supabase、核对百炼账户额度和 Namecheap DNS 的权限/登录答复仍待 Rui。

## 2026-10-07 凭据与 DNS 续查

- 本地忽略的 `.env` 中 `SCAM_RADAR_EVAL_API_KEY`、`SCAM_RADAR_MODEL_API_KEY` 已非空；仅检查字段是否存在，未输出密钥内容，真实模型调用仍为 0。
- Rui 提供 Namecheap 作为 DNS 登录入口；登录页已打开，当前仍未登录。待登录后只读核对 `insparian.com` 与 `scamradar` 记录，不修改 DNS。Cloudflare Pages 尚无 production 部署，当前没有可执行的正式 CNAME 变更。
- 已请求百炼北京控制台只读核对实际额度/到期日；Supabase 恢复项目需另获授权。以上请求均不视为真实调用或生产激活许可。
- 复核[百炼官方模型页](https://help.aliyun.com/zh/model-studio/qwen3-8-flash)与[免费额度规则](https://help.aliyun.com/zh/model-studio/new-free-quota)：`qwen3.8-flash` 北京区支持结构化输出；标价非零，实际免付费依赖账户内有效剩余额度与用完即停，不能只凭模型页判断。

## 2026-10-07 云端只读核查与提交

- Rui 授权只读查看已登录的 Supabase、Cloudflare 控制台；未恢复项目、开通服务、读取密钥、访问站点预览或修改云资源。
- Supabase `scam-radar` 为现有 Free 项目，地区 `eu-central-1`（Frankfurt），当前 paused。暂停状态下不能核验真实迁移、角色、RLS、连接及恢复；恢复项目仍待单独授权。
- Cloudflare 同一账户已有 `insparian-scam-radar` 和 `insparian-scam-radar-reviewer` 两个 Pages 项目，均只有旧 preview 部署、没有 production 部署；公开项目 production branch 为 `main`，没有 custom domain。账户 Domains 清单只有 `wellphases.com`、`withguan.com`；Rui 确认目标 `insparian.com` 的 DNS 由 Namecheap 管理。没有打开现有预览或生产网站。
- R2 进入开通订阅页面，尚未启用；页面说明超过免费额度会计费，故未点击开通。真实密文备份与恢复关卡仍无法执行。
- 忽略的 `.env` 已留北京百炼评测/worker 两个 Key 填写位，均空，所有真实调用开关为 false；本地 `.env` 不会自动配置 GitHub Actions 的 Variables/Secrets。
- 提交 `04edac9` 已推送 `origin/main`。推送响应提示默认分支 5 项 Dependabot 漏洞（1 critical、2 high、2 moderate）；Rui 随后授权只读查看告警。四组受影响包为 Next.js、sharp、source-map-js 和两个版本段的 brace-expansion，均有补丁；已只更新现有依赖及锁文件至修复版本。Next.js 16.3.6、sharp 0.35.5、source-map-js 1.2.2、brace-expansion 1.1.21/5.0.12 均已在本地解析。
- `make check`、`make test`（140 Python、9 浏览器）、`make demo`（100 文件静态导出）通过；第一次 `make test` 被沙箱拒绝 localhost bind，获准本地回环后同一套件通过。完整 npm 在线审计仍显示 5 个 high，均为 `eslint-config-next` 的开发工具依赖链；`npm audit --omit=dev` 对生产依赖为 0。`npm ci --offline` 重建锁文件成功，但离线审计缓存显示 0 不代表在线 5 个开发告警消失。
- `.env.example` 原有 Gemini/旧 Supabase/R2 名称与当前运行入口不符，现已改为北京 Qwen 评测/worker 和 GitHub workflow 实际变量名，保持假值与全部激活开关关闭。静态产物秘密名扫描增加当前私密变量名。
- 安全修复提交 `5bba76b` 已推送；GitHub 随后重扫显示 Dependabot open 0、closed 16，本轮 5 项告警已关闭。工作区与 `origin/main` 一致。

## 2026-10-06 亲自推进上线准备

- Rui 要求由当前助手亲自执行；不派子代理。先关闭暂缓期间跨来源重复建模式的 P1，再跑完整离线验收；保留开工时已有差异。
- 状态边界：可匹配事实来自仍有效的 approved revision；`evidence_pending` 只说明补证工作流，不能隐藏旧批准事实。候选只允许 review_ready/evidence_pending，仍排除 archived/rejected/candidate；草稿不作为匹配事实，待审冲突继续延后。
- 模型选择经 Rui 澄清：没有 Gemini API 项目，已有百炼北京区，确认开启免费额度用完即停；选 qwen3.8-flash、北京端点、非思考 JSON 模式。真实调用、生产和发布继续等精确激活授权。

- 旧 21 迁移库新 SQL 回归报 `held_approved_fact_not_matchable`；未修改独立脚本也重现 comparison=0、新建 new_pattern。证据 `work/readiness-20261006/red-database.log`、`red-original.log`。
- 前向迁移 `20261006000100` 只扩大批准版本匹配到 evidence_pending；保留暂缓工作流、草稿冲突与 inactive 排除。22 迁移新库 database-test 通过；原脚本绿色：comparison=1、pending_review_deferred=1、无新审核、attempt=0。证据 `database.log`、`green-original.log`。
- 仓库真实进程/审核回归通过：暂缓时另一来源两次延后，原审核批准和拒绝两分支解决后都续入同一模式，重复运行无模型调用、无新增收据。独立 joined 栈的全部根流程通过，四宽度 release 浏览器通过；`crash-green.log`、`joined.log`。
- 26 表独立恢复与密文回读通过：`recovery.log`，细报告 `work/launch-readiness/recovery-8ab4581f37ab/report.json`、`backup-e2e-6789c59a10da/report.json`；外部上传 false。
- 免费预算原实现拒绝 0 费率/0 上限，已修复且重试仍计数；非零报价零预算在请求前拒绝，免费账户须显式确认。Qwen 北京候选配置非思考 JSON，参数进入缓存指纹；未调用真实模型，未增加依赖或修改 prompt。
- 最终九个根命令均通过，完整结果见 OFFLINE-ACCEPTANCE-REPORT；P1 已关闭，仅离线代码就绪。启动合成栈曾遇 Documents 挂载拒绝及多栈资源超时，改用 /private/tmp、串行停启本轮自建栈；用户原有栈保留。
- Rui 说明账户有 89 个免费模型，测试阶段型号可灵活选择。为可复现固定当前 qwen3.8-flash 候选；后续换模型须使用同一真实 holdout 重测，生产模型仍 null、live_enabled=false。当前剩余项是外部授权、凭据、真实样本与环境验证。

## 2026-10-06 leader 独立复核 — 原反例通过，整体仍有阻塞

- 提交 `f7fa658`；保护原有 AGENTS、next-env、决策等未提交内容，本次未改产品代码。
- 独立 `make check/test/eval/collect-dry-run` 均退出 0：119 Python、32 前端单元、
  9 浏览器、100 recorded；15 来源关闭、`launch_qualified=false`。
- 专用 `scam-radar-audit06-db` 从零应用 21 个迁移，`make database-test` 退出 0，
  包含新增伪造拒绝与越权反向契约。证据 `work/leader06-{start,database}.log`。
- **未修改**原独立脚本 `work/leader29-early-reject.py` 本次退出 0：首轮重启
  processed、游标推进，随后三轮原 ID/计数/人工拒绝不变，Policy 保持 0。
  证据 `work/leader06-original-repro.log`，确认早拒绝 P1 修复有效。
- 额外 hold/跨来源交错失败：已有批准模式处于 needs_evidence 时，另一来源
  同类文章没有进行模式比较，直接创建第二个 new_pattern；原审核仍未解决。
  证据 `work/leader06-held-conflict.log` 与最新 BLOCKED 段。需修复批准模式
  可匹配性与待审工作流的边界；整体离线就绪暂不签字。
- 发现阻塞后未继续复跑 demo、完整 joined/deployment/recovery 根目标，
  不把执行方历史日志算作本次独立通过。未启用真实采集/模型/生产读写/
  上传/发布/DNS，未提交或推送本次复核记录。

## 2026-09-29 P1 再开工：审核先于恢复的时序

1. 独立红灯 `work/leader29-early-reject.log`：证据已提交、Policy 0、浏览器先拒绝后，四次重启均 `existing_recovery_read_failed`，游标空；保留 `AGENTS.md`、`docs/BLOCKED.md`、`docs/PROGRESS.md`、`web/next-env.d.ts` 等原有未提交差异。
2. 状态规则：无 Policy 且审核 pending/in_review、草稿有效 → 依据持久候选补录 shadow Policy；无 Policy 且 needs_evidence → 暂缓并归还认领，不消耗重试；无 Policy 且有可核验人工 rejected 终态 → 不伪造已不允许写入的 Policy，完成来源处理并推进游标。已有 Policy 的合法审核终态照原决策收尾；其他状态拒绝恢复。
3. 待验证：拒绝终态须核对审核事件、草稿/证据终态及旧批准版不变；暂缓后人工拒绝可恢复，重复运行无重复记录。先把独立红灯加入仓库回归，再做前向迁移、worker 修复与新库全套验收。
- 仓库回归在独立复核旧栈先得到目标红灯 `work/leader29-repository-early-reject-red.log`。前向迁移 013 在这套可丢弃旧红栈应用后，早拒绝场景已恢复；探针随后因测试仍错误地预期“早拒绝后存在待审冲突”失败，已修正该测试条件并通过真实浏览器清理探针留下的合成草稿。证据 `work/leader29-early-reject-probe.log`、`leader29-probe-cleanup.log`；完整回归与全新 21 迁移库仍待跑。
- 第一套全新 21 迁移库的早拒绝与暂缓后拒绝恢复已通过，但完整回归末尾发现旧 `hold_for_evidence` 把已批准模式 lifecycle 留在 `evidence_pending`，暂缓后拒绝未恢复 `review_ready`，后续来源无法匹配而落入新模式路径；红证据 `work/leader29-reviewed-regression-fresh.log` 及该库只读状态查询。前向迁移 013 现补充暂缓时保持既有模式 row_version、拒绝时恢复 review_ready，并在回归中显式断言状态；更新后的迁移须另建全新库从零验证。
- 第二套全新 21 迁移库 `scam-radar-reviewed-final` 从零建库后，`make database-test` 退出 0；仓库真实进程/浏览器回归退出 0。早拒绝在 Policy 0 时完成且保留人工决定；新暂缓状态可补 shadow Policy 后由浏览器批准；模拟旧暂缓状态两轮归还认领不耗重试，人工拒绝后完成并恢复旧批准模式 `review_ready`；三次中断、丢响应及原有审核边界仍通过。证据 `work/leader29-final-stack-start.log`、`leader29-final-database-test.log`、`leader29-final-reviewed-regression.log`。下一步把新增 SQL 反向断言补全并跑最终串行套件。
- 新增 SQL 反向断言：未暂缓时不能调用归还认领 RPC；伪造 reviewer 身份直接改成 rejected、却无 append-only 人工事件时，恢复 RPC 必须拒绝；匿名/审核员无恢复或归还权限。单独在上述新库运行 rollback 型 existing-pattern 契约退出 0，证据 `work/leader29-existing-contract-negative.log`。尝试在已被根验收写入数据的同一库重跑整个 `make database-test` 因旧契约的可变基线报 `policy_decision_input_stale`，并非最终状态；最终根套件须换新库一次性执行。
- 修正静态契约漏列新恢复/暂缓 RPC 并重生数据库类型后，最终源码状态的 `make check/test/eval/demo/collect-dry-run` 依次退出 0：119 Python、32 前端单元、9 浏览器、100 recorded、100 静态文件，0 跳过；15 来源仍 disabled、`launch_qualified=false`。`make test` 首次沙箱内 localhost bind 被拒且静态 RPC 清单过期，已分别用获准本地 socket 权限和补全权限断言解决；绿证据 `work/leader29-final21-{check,test,eval,demo,collect}.log`。后续须用最终迁移文本从零建库，跑 database/joined/deployment/recovery。
- 最终迁移文本的独立 `scam-radar-reviewed-accept-db` 栈从零应用 21 迁移，`make database-test` 与 `make recovery-rehearsal` 各退出 0：SQL 越权/伪造审核反向测试、本地新骗局持久化、26 表恢复/权限/同一 release、密文回读/篡改拒绝通过；外部上传 false。证据 `work/leader29-accept-db-start.log`、`leader29-accept-database-test.log`、`leader29-accept-recovery.log` 及 `work/launch-readiness/recovery-87745a7474fc/report.json`、`backup-e2e-c97ec4ef1fdc/report.json`。仍待独立 joined、deployment 栈。
- 独立 `scam-radar-reviewed-accept-joined` 栈从零应用同一 21 迁移，`make joined-local-e2e` 退出 0：新骗局、已有骗局追加证据、Policy 前后进程退出、早拒绝、暂缓后批准、旧暂缓后拒绝、连续三次中断、待审冲突、不可变 release 与 360/390/768/1440 浏览器均通过。证据 `work/leader29-accept-joined-start.log`、`leader29-accept-joined.log`；还差独立发布/回退栈及最终报告。
- 独立 `scam-radar-reviewed-accept-deploy` 栈从零应用同一 21 迁移，`make deployment-local-e2e` 退出 0：本地 Pages 协议上传未登记对账、旧版拒绝、失败后原产物回退及 smoke 撤回通过。证据 `work/leader29-accept-deploy-start.log`、`leader29-accept-deploy.log`。九个根命令现已针对同一最终代码/迁移状态退出 0；待同步报告、阻塞状态与提交核查。
- 在保留的最终 joined 新栈上，直接运行独立复核留下的**未修改** `work/leader29-early-reject.py`，退出 0：同一真实进程退出→浏览器人工先拒绝→四次重启时，第一次即 processed/游标推进，后续三次证据/修订/审核 ID、Policy 0、attempt 2 均不变。原红 `work/leader29-early-reject.log` 对应新绿 `work/leader29-independent-repro-green.log`。这是针对用户指出的精确反例的独立脚本复跑。

## 2026-09-29 leader 第二次独立验收 — 未通过

- 核对提交 `f9649db`，保护原有未提交文件；本次没有修改产品代码。
- 独立复跑 `make check/test/eval/demo/collect-dry-run` 全部退出 0：
  Python 119、前端单元 32、浏览器 9、recorded 100、静态文件 100；
  15 来源仍关闭、`launch_qualified=false`。日志 `work/leader29-*.log`。
- 新建 `scam-radar-audit29-db`，20 个迁移从零应用；`make database-test`
  退出 0，随后独立执行仓库 `local_existing_crash_e2e.py` 退出 0，原四种
  中断/响应丢失场景、三次连续中断及跨来源冲突均通过。
- 额外时序抽查失败：after_submit 退出后、Policy 尚无记录时，浏览器人工
  拒绝成功；之后四次重启均 `existing_recovery_read_failed`，attempt 2→5，
  版本 error、游标空、Policy 0；原收据及人类拒绝未变。新迁移把这一合法
  终态当成非法恢复状态；P1 重新打开，详见 `docs/BLOCKED.md` 最新段。
- 证据 `work/leader29-early-reject.log`；未在发现阻塞后继续复跑完整 joined、
  deployment 和 recovery 根目标，不以执行方旧日志代替本次独立通过结论。
  外部采集/模型/生产/上传/发布/DNS 均未激活，本次未提交或推送。

## 2026-09-29 最终联合与发布验收

- 全新 20 迁移隔离栈 `scam-radar-crash-final-joined` 上，`make joined-local-e2e` 退出 0：新骗局、已有骗局追加证据、四个真实中断/丢响应点、连续三次中断、待审冲突、浏览器批准/拒绝、不可变 release、360/390/768/1440 宽度均通过。证据 `work/crash-recovery-20260928/final20-joined-local-e2e.log`。
- 全新 20 迁移隔离栈 `scam-radar-crash-final-deploy` 上，`make deployment-local-e2e` 首次在沙箱内 Docker inspect 容器时退出 2，尚未执行发布逻辑；获准访问本地 Docker 后重跑退出 0，实际验证上传未登记对账、旧版拒绝、原产物回退、失败上传撤回。首次错误由工具调用输出记录，绿证据 `work/crash-recovery-20260928/final20-deployment-local-e2e.log`。下一步新库恢复验收及报告。
- `scam-radar-crash-final-db20` 重启原全新库后，`make recovery-rehearsal` 退出 0：26 表、新库权限、同一 release 核对通过；`pg_dump→age→本地 S3→读回→解密` 和密文篡改拒绝通过，外部上传 false。证据 `work/crash-recovery-20260928/final20-recovery-rehearsal.log`、`work/launch-readiness/recovery-93263df2160d/report.json`、`work/launch-readiness/backup-e2e-163ed1910dd4/report.json`。
- 最终九个根命令对同一 20 迁移代码状态均退出 0；P1 现可关闭。下一步同步验收报告、核对 git 差异及提交本轮范围内文件；不会触及外部激活。

## 2026-09-28 P1 修复开工回执
1. 基线 `6836f67`；保留原有 AGENTS/决策和 2026-09-28 复核文档未提交差异。
2. 第九个具名隔离栈 `scam-radar-crash-red` 从零应用 18 迁移，`make database-test` 退出 0，证据 `work/crash-recovery-20260928/`。
3. 事务提交后注入进程退出 73：版本 `processing:1`、收据 1、Policy 0；租约到期后重启仍 `degraded/pending_review_deferred=1`，原版红证据 `red-*.log`。
4. 根因已证实：`durable.py` 在寻找本版本持久收据前先把其待审草稿视为跨任务冲突；SQL 重放还少 `missing_claim_count`，候选哈希含随日期变化的 Heat，不能靠重新提交代替恢复。
5. 方案：前向新增仅 service 可读、受当前认领约束的恢复收据 RPC；优先恢复原事务、核对已有 Policy，缺失时从持久候选资料补录，再按正常认领完成版本。
6. 顺序：仓库化真实进程中断回归红→绿 → 新库 SQL/权限负例 → 最终全部根命令串行复验。
7. 最大风险：Policy 响应丢失后新 run 重放形成重复决策，或人工已批准/拒绝时覆盖原结果；回归必须断言原 ID/计数和审核状态不变。

### 仓库化中断回归红灯

- 新增 `worker/tests/integration/local_existing_crash_e2e.py`，以真实子进程在 PostgREST 事务提交后退出并读取数据库 ID/计数、游标与状态。首跑时旧红库的待审草稿影响新来源，已隔离重建；随后发现测试模拟的租约时间违反数据库 `expires_at > acquired_at` 约束，已修正注入时间顺序，没有改业务断言。
- 在第二个从零迁移的具名库 `scam-radar-crash-regression-red` 上，回归同一子进程/快照断言得到目标红灯：重启前 `processing:1`、收据/证据/修订/审核各 1、Policy 0；重启后仍 `degraded/pending_review_conflict`、游标空、Policy 0。证据 `work/crash-recovery-20260928/repository-target-red.log`。接下来实施收据恢复。

### 原中断收据补全的第一项绿证据

- 新前向迁移 011 在一次性红灯库应用：旧事务写入函数移到私有 schema，公开 wrapper 补齐首次/重放回执字段；新增只对当前 service 认领可见的收据/Policy 恢复 RPC。worker 在匹配候选前优先恢复自己已提交的收据，Policy 已在库则不重写，缺失才从持久候选内容补录。
- 用上述红灯库的**原始孤儿收据**验证：重启从 `pending_ai`、收据 1/Policy 0 自动转为 `processed`、收据 1/Policy 1，游标推进且模型调用 0；证据 `work/crash-recovery-20260928/recovery-migration-probe.log`、`orphan-recovery-probe.log`。此为旧库探针，最终全新 19 迁移根验收仍待执行。

### 全新 19 迁移数据库根验收

- 具名隔离栈 `scam-radar-crash-green` 从零应用 19 个迁移；`make database-test` 退出 0。新增 SQL 断言确认外来持有者不能读取恢复收据、首次与精确重放字段一致、日期变化的 Heat 重放被拒绝，而受限恢复收据仍能读取原事务；基础 RLS/Auth/发布和 localhost 模型链照常通过。证据 `work/crash-recovery-20260928/green-stack-start.log`、`green-database-test.log`。下一步跑四个真实进程/响应中断场景。

### 四个真实中断/丢响应回归通过

- `local_existing_crash_e2e.py` 在同一全新库退出 0：证据提交后进程退出、Policy 已提交但版本未完成时进程退出并在人工批准/拒绝后恢复、以及数据库已提交但客户端丢失成功响应，均自动续完。每条校验原证据/修订/审核 ID、Policy 恰好 1、版本 processed、游标推进，随后重复运行数据库快照与模型调用均不变。
- 另一个来源在本来源待审时仍被延后、重试次数保持 0，人工拒绝后自动恢复；浏览器审核的原批准/拒绝决定和已批准旧版本均保持。证据 `work/crash-recovery-20260928/green-crash-regression.log`。回归已接入 `make joined-local-e2e`，最终根命令和独立新栈复跑仍待完成。

### 最终静态/浏览器/合成套件第一段

- 按最终修复代码顺序运行 `make check`、`make test`、`make eval`、`make demo`、`make collect-dry-run`，均退出 0：119 Python、32 前端单元、9 浏览器、100 recorded、100 静态文件，0 跳过；15 个真实来源仍关闭，`launch_qualified=false`。证据 `work/crash-recovery-20260928/final-{check,test,eval,demo,collect-dry-run}.log`。行为清单 hash 未变，因为本轮未改其覆盖的 prompt/schema/model 等文件；下一步在独立新栈复跑根数据库、joined、deployment、recovery。

### 连续中断仍会卡死的第二层根因与修复

- 在新合成库对同一已提交事务连续注入三次“完成版本前进程退出”，原 `attempt_count < 3` 使第四轮连版本都无法认领；worker 却报告 success，版本继续 processing。目标红证据 `work/crash-recovery-20260928/repeated-crash-red.log`。这是同一 P1 的残留，不把先前四场景绿灯冒充完成。
- 前向迁移 012 仅对 `source_version_updates` 已有持久收据的版本允许超过旧认领上限；无收据的版本仍保留三次上限。将 012 只应用到上述红灯库后，原版本从 attempt 3 自动恢复为 processed/attempt 4，证据、修订、审核、Policy ID 全部相同且模型调用 0。证据 `retry-cap-migration-probe.log`、`repeated-crash-orphan-green.log`。最终需从零建立 20 迁移库并重跑所有根命令。

### 最终 20 迁移代码的串行套件前五项

- `make check`、`make test`、`make eval`、`make demo`、`make collect-dry-run` 依次退出 0：119 Python、32 前端单元、9 浏览器、100 recorded、100 静态文件，0 跳过；15 来源 disabled、`launch_qualified=false`。证据 `work/crash-recovery-20260928/final20-{check,test,eval,demo,collect-dry-run}.log`。后四个数据库/发布/恢复根命令仍待全新 20 迁移库。
- 第六项 `make database-test` 在新建 `scam-radar-crash-final-db20` 栈（20 个迁移从零）退出 0：原权限/审核/导出与新“已提交事务超过 3 次仍可认领、未提交事务仍封顶”的 SQL 反向断言全部通过。证据 `final-db20-start.log`、`final20-database-test.log`。后续 joined/deployment/recovery 按顺序待执行。

## 2026-09-28 leader 独立复核 — 未通过

- 复核提交 `6836f67` / `f13dc08`；保护原有 AGENTS/决策/工具未提交文件，未改产品代码。
- 独立复跑 `make check`、`make test`、`make eval`、`make demo`、
  `make collect-dry-run` 均退出 0：32 前端单元、119 Python、9 浏览器、
  100 合成评测、100 静态文件；15 个真实来源全部关闭。
- 专用 `scam-radar-audit-20260928` 栈从零应用 18 个迁移；
  `make database-test` 与 `make recovery-rehearsal` 退出 0，恢复 26 表并核对
  同一 release/权限，本机 S3 回读/篡改拒绝通过。日志 `work/leader-re*.log`。
- 额外独立抽查：篡改搜索 release 被拒绝，恢复后通过且原产物未变；
  两次 localhost 模型超时均预留费用，第三次在网络请求前因调用上限拒绝。
- **新增 P1：** 追加证据事务已提交后立即结束进程，认领过期后重启两次，
  均被自己的待审草稿挡住；版本保持 pending_ai、关联 Policy 记录 0。
  证据 `work/leader-crash-audit.log`，根因与修复验收要求见 `docs/BLOCKED.md`。
  现有明卷全绿不足以证明中断恢复完成；本次未重跑 joined/deployment 根目标，
  未对完整离线就绪签字。下一步应修复此恢复路径后再完成复核。
- 所有验证仅在本地合成数据上进行；未启用真实采集、模型、生产访问、外部
  备份上传、发布或 DNS，未提交或推送本次复核记录。

## 2026-09-27 续工开工回执
1. 目标：代码与本地全流程离线就绪；外部试运行和正式发布留待集中确认。
2. 顺序：冻结基线 → 全新隔离库/追加证据 → 两条持久化链 → 运行与评测 → 网页 → 发布恢复 → 串行总验收。
3. HEAD `412950d`；开工有 94 条工作区变更，已存差异、未跟踪文件和测试清单于 `work/offline-resume-20260927/`。
4. 当前 `make check` 因生成数据库类型过期退出 2；Python 共 115 项：106 通过、4 失败、5 因沙箱拒绝 localhost 报错。
5. `make eval` 已通过 100 项且 `launch_qualified=false`；较 9 月 23 日清单失败基线有变化，须审阅实际行为差异。
6. 前端 `npm run check` 通过；`make collect-dry-run` 确认 15 个真实来源仍关闭。
7. 最大风险：暂停前迁移 008 最终修改和现有模式 worker 未在全新库验证；旧库绿灯不可继承。
8. 根数据库、joined、deployment、recovery 入口已核参数；尚待隔离栈和实际执行，SQL/备份覆盖待补全。

### 全新迁移与静态契约（2026-09-27）

- 已建仅用于本任务的 `/private/tmp/scam-radar-offline-20260927-yghfv1ki`；所有 16 个当前迁移从零应用成功，旧栈未重置。日志 `work/offline-resume-20260927/fresh-stack-start.log`。
- 从迁移重新生成数据库类型，未手改生成文件；`make check` 退出 0，证据 `work/offline-resume-20260927/check-after-types.log`。下一步运行真实 SQL 和 joined 验收。

### 首条持久化链及迁移 008 契约（2026-09-27）

- 首次 `make database-test` 的真实 SQL/导出检查通过，随后暴露旧断言：首次恢复后模型调用数为 4，第三次重复运行应保持 4；原断言错误地要求变为 5。规格是重复运行不调用模型、不重复审核，现改成对第三次前后调用数相等的更强比较。红证据 `work/offline-resume-20260927/database-test-first.log`。
- 在全新隔离栈实际运行 localhost 来源/模型 → PostgREST/数据库 → 本地 Auth 审核员拒绝和批准 → 不可变 release → 静态站，退出 0；服务凭据冒充人工批准被拒绝。证据 `work/offline-resume-20260927/pipeline-full-review-first.log`。
- 迁移 008 追加证据 SQL 契约在该批准模式上退出 0：越权认领、错误同一模式判断拒绝；证据集合/内容哈希、不可变旧版及精确重复运行通过。证据 `work/offline-resume-20260927/existing-pattern-contract-first.log`。真正第二条 worker/browser 联合链仍待实现。

### 第二条持久化链与浏览器审核（2026-09-27）

- 新增 `local_existing_pattern_e2e.py`：第二条 localhost 来源/模型经真实 PostgREST 写入一条 `pattern_update`、一条待定证据；重复运行模型调用数和审核数均不增加。首次合成模型回包用了不在既有 schema 的原因码，红证据 `existing-worker-probe.log`；改成合法原因码后绿证据 `existing-worker-first.log`。
- 浏览器以本地 Auth 审核员实际批准追加证据，旧批准版哈希保持不变；随后再建一条合成更新并由浏览器拒绝，旧批准版仍不变。证据 `existing-browser-approve-second.log`、`existing-browser-reject-first.log`，截图在 `work/launch-readiness/joined-update-*-browser.png`。
- 拒绝路径暴露旧 RPC 会留下待审草稿，导致下一条证据无法提交；前向迁移 009 让拒绝的草稿/证据明确终结并释放草稿槽。新迁移已在具名隔离栈应用，拒绝后状态检查通过；最终仍需从零重建验证。

### 待审冲突延后与重试（2026-09-27）

- 前向迁移 010 让已批准模式在待审时仍可被匹配，新增狭窄的 service-only 延后 RPC：认领归还 `pending_ai`、不消耗三次重试、保留旧来源游标；越权持有者被拒绝。回滚型 SQL 红/绿证据 `work/offline-resume-20260927/existing-contract-defer.log`。
- 真实 localhost 第二来源连续两轮遇到待审冲突，均没有新增审核、模型重比对或重试损耗；浏览器批准前一条后，下一轮自动恢复并生成审核，浏览器再拒绝该条，旧批准版保持不变。证据 `pending-review-e2e-green.log`。
- 第一次浏览器序列失败于本地 Next 开发服务器残留锁，而非业务断言；已让测试进程组完整退出并在确认无持有进程后清除其一次性锁，后续完整复跑通过。红证据 `pending-review-e2e-first.log`。`make test` 在生成类型再次过期时 114/115 Python 通过；待迁移稳定后重生类型和串行总验收。

### 追加证据的新版 release（2026-09-27）

- 已批准追加证据经真实 PostgreSQL `prepare_public_release` 形成第二个不可变 release，静态网页与搜索绑定该精确 ID；旧 release 的导出和站点哈希保持不变。localhost Pages 协议登记了新版，浏览器在 360/390/768/1440 宽度完成首页、搜索、详情、空结果、键盘和隐私检查。证据 `work/offline-resume-20260927/update-release-e2e-second.log`、`work/launch-readiness/update-release/*/browser/`。
- 首次运行在第一版已成功部署时误期待模拟登记响应丢失；改为新栈时显式故障注入、已部署恢复时只续跑，未放宽发布哈希/精确版本检查。红证据 `update-release-e2e-first.log`；从零新栈仍待完整复跑。

### 从零数据库验收诊断（2026-09-27）

- 新建第二个具名隔离栈 `scam-radar-dbtest-20260927`，18 个迁移从零应用；首次启动因本地容器资源导致 storage 健康检查超时，停止已完成的旧栈（保留卷）后重试成功。未触碰 9 月 23 日实例。
- 首次 `make database-test` 由精确迁移白名单缺 009/010 拒绝；补上两项后，基础 SQL、真实导出、Auth 人工批准和静态站通过，末尾重跑全部基础 SQL 时触发 `policy_decision_input_stale`。根因是基础合成 fixture 契约不可在已经批准的持久库上重复执行；现将末尾入口限定为追加证据 SQL 契约，单独运行退出 0。红证据 `database-test-fresh.log`、`database-test-fresh-second.log`；绿证据 `dbtest-existing-only.log`。完整根目标仍待另一个全新栈一次跑通。

### 从零数据库根验收通过（2026-09-27）

- 第三个具名隔离栈 `scam-radar-dbtest-final` 从零应用 18 个迁移；修正后的 `make database-test` 一次退出 0。基础权限/审核/发布 SQL、真实导出负例、localhost 模型失败恢复、Auth 人工批准、静态站、追加证据与待审冲突 SQL 全部执行。证据 `work/offline-resume-20260927/dbtest-final-start.log`、`database-test-final-green.log`。
- 运行错误现在按来源/模型/缓存/入库阶段记录固定原因码与计数，失败正文不进入日志。合成模型失败的数据库版本与运行摘要都断言为 `extraction_model_failed`；该断言随上述根链通过。`make check` 退出 0，证据 `check-stage-codes.log`。下一步用新的独立栈执行 joined、deployment 和恢复。

### 实际本地 release 备份与新库恢复（2026-09-27）

- 旧恢复脚本会先复制数据库、再重复插入审核 fixture；已改为直接备份当前隔离库已批准的实际本地 release，在新库恢复后核对同一 release 导出、26 张 public 表行数、RLS 与 service 无人工批准权。`make recovery-rehearsal` 退出 0；证据 `work/offline-resume-20260927/recovery-actual-release.log`、`work/launch-readiness/recovery-89c20c8d0a28/report.json`。首次旧脚本失败证据 `recovery-fresh.log`。
- 同一根命令实际执行 `local_backup_e2e.py`：`pg_dump → age → localhost S3 → 读回 → 解密归档检查`，重复上传不产生新收据、篡改密文拒绝、无明文 dump 文件。报告 `work/launch-readiness/backup-e2e-92f40bce4bb6/report.json`；没有外部上传。

### 全新联合浏览器根验收通过（2026-09-27）

- 第四个具名隔离栈 `scam-radar-joined-final` 从零应用 18 个迁移；`make joined-local-e2e` 退出 0。新骗局的来源/模型/真实库/浏览器拒绝与批准，以及已有骗局的两轮待审延后、批准后恢复、浏览器拒绝、不可变新版 release 和 localhost Pages 均连续通过。
- 新版公众首页→私密搜索→详情、证据和应对动作，在 360/390/768/1440 宽度通过；截图在 `work/launch-readiness/update-release/*/browser/`。根证据 `work/offline-resume-20260927/joined-final-start.log`、`joined-final.log`。旧版导出与产物哈希在新版之后仍相同。

### 全新发布回退根验收通过（2026-09-27）

- 第五个具名隔离栈 `scam-radar-deploy-final` 从零应用 18 个迁移；`make deployment-local-e2e` 退出 0。真实本地 Auth 浏览器批准后，localhost Pages 协议验证上传后登记响应丢失与对账、旧版拒绝、原产物与数据库指针回退、失败 smoke 上传撤销；原始 release 导出未变。证据 `work/offline-resume-20260927/deploy-final-start.log`、`deployment-final.log`。

### 休眠真实评测入口与预算边界（2026-09-27）

- `evals/run_live_eval.py` 现在能对人工标签计算相关性、分类、应对动作、模式匹配、实质变化及延迟指标，报告仅保留 ID/计数/分数且固定 `launch_qualified=false`。运行说明和双人标注、锁定数据集流程见 `evals/README.md`；没有启用真实模型或定时任务。
- HTTP 协议每次尝试前预留最多 4096 输出 token 与保守输入费用，失败重试也占调用/费用硬上限；本机注入错误和额度不足测试分别确认 3 次计数及请求前拒绝，真实入口无授权时拒绝。`worker/tests/integration/test_http_protocols.py` 7 项通过，证据 `work/offline-resume-20260927/live-eval-local-gates.log`；格式复查后同组再通过。

### 最终套件首轮反馈（2026-09-27）

- `make check` 退出 0，含 32 个前端单元测试；证据 `work/offline-resume-20260927/check-final-candidate.log`。
- `make test` 首轮 Python 116 通过、1 失败，浏览器尚未进入。失败发生在 localhost Pages 协议模拟器未读取 rollback POST 正文，macOS 连接复位；生产适配器无变更。模拟器补读请求正文后该单例退出 0，红/绿证据 `test-final-candidate.log`、`pages-protocol-fixed.log`。下一步重跑完整套件。
- 数据库编排 SQL 增加“旧进程认领后到期，新进程接管，旧持有者不得完成”的真实库故障注入断言，待全新栈根验收。
- 修正后 `make test` 退出 0：Python 117 通过、浏览器 9 通过、静态产物秘密扫描通过，无跳过；证据 `work/offline-resume-20260927/test-final-second.log`。
- 第六个具名隔离栈 `scam-radar-final-sql` 从零应用 18 个当前迁移；`make database-test` 退出 0，包含新增“进程中断、认领到期、新进程接管、旧持有者拒绝”的真实 PostgreSQL 故障注入，以及来源/模型、人工审核和 release 全链。证据 `final-sql-start.log`、`database-final-state.log`。
- 同一库的 `make recovery-rehearsal` 退出 0：26 张 public 表、精确 release/RLS/审批权在独立新库核对；本机 `pg_dump→age→S3→回读→解密` 与篡改拒绝也通过。证据 `recovery-final-state.log`、`work/launch-readiness/recovery-d5e4b658a85e/report.json`、`backup-e2e-ba700759f3ad/report.json`，外部上传为 0。
- 审查三个实际工作流与适配器：收集、备份、发布各自要求独立开关，凭据只在需要的步骤注入；静态产物扫描在 Pages 上传前。将收集工作流首轮限定到一个精确批准 source key、5 篇/10 次模型尝试，拒绝 `all`，与集中确认包的首轮边界一致。`check_workflows_pinned.py`、公开边界与 `git diff --check` 退出 0；没有启用开关或外部请求。
- 第七个具名隔离栈 `scam-radar-final-joined` 从零应用 18 个迁移，`make joined-local-e2e` 退出 0：新骗局与追加证据两条 PostgREST 持久化链、浏览器批准/拒绝、两轮待审延后、不可变新版 release、本机 Pages，以及 360/390/768/1440 公众路径均通过。证据 `final-joined-start.log`、`joined-final-state.log`、`work/launch-readiness/update-release/*/browser/`。抽查 360 详情与 390 搜索截图，主操作和证据区可读；老人实际使用仍需真实环境主观抽查。
- 第八个具名隔离栈 `scam-radar-final-deploy` 从零应用 18 个迁移，`make deployment-local-e2e` 退出 0：本机 Pages 上传后登记丢失→对账、旧版拒绝、原产物回退与失败 smoke 撤回均通过。证据 `final-deploy-start.log`、`deployment-final-state.log`。
- `make eval` 首轮 100 个合成案例及各指标仍全通过，但行为清单因新增模型尝试前预算钩子而按预期拒绝旧 hash；审阅差异确认只影响调用前预算、没有放宽分类/证据/公开门槛后，将清单改为实际运行算出的 `c17b9933…`。重跑 `make eval` 退出 0，`launch_qualified=false`；红/绿证据 `eval-before-manifest.log`、`eval-final-state.log`。
- `make demo` 在当前代码状态退出 0：5 个合成模式、100 个静态文件、完整产物扫描通过；证据 `demo-final-state.log`。该命令只证明演示产物，不替代上述持久化 release 验收。
- 来源离线协议补强了两个失败关闭测试：发现站外文章 URL 时在文章请求前拒绝、栏目结构变动缺少正文时不生成证据；该组 5 项通过。真实栏目、条款、robots 与解析仍未访问，保留在集中授权包。
- 最终同一代码状态的静态/浏览器/合成套件按顺序退出 0：`make check`（32 前端单元）、`make test`（119 Python、9 浏览器、0 跳过）、`make eval`（100 recorded、`launch_qualified=false`）、`make demo`（5 模式、100 静态文件）、`make collect-dry-run`（15 来源全部关闭）。日志分别为 `work/offline-resume-20260927/final-make-{check,test,eval,demo,collect-dry-run}.log`。
- 汇总为 [离线验收报告](OFFLINE-ACCEPTANCE-REPORT.md)，开工 50 项测试/规格文件均仍存在；[BLOCKED.md](BLOCKED.md) 已仅保留真实来源、模型、生产备份、七天稳定性与大陆/微信访问等外部关卡。集中确认包保留现有精确批准门槛与未知 release/hash 空位；本轮外部激活为 0。
- 已将白名单内 97 个经过验收的文件提交为 `f13dc08`（`Complete offline launch readiness paths`）。范围外开工遗留的根 `AGENTS.md`、`.codex/`、`DECISIONS/`、`web/AGENTS.md` 与 `web/CLAUDE.md` 原样留在工作区；没有 push、部署或外部激活。

## 开工回执（2026-09-18）
1. 目标：全部离线上线准备；外部试运行与发布另行集中确认。
2. 基线：412950d，开始时工作区干净；Decision 011 与任务授权已保存。
3. 顺序：基线 → 数据库/真实链路 → 家庭网站 → 发布恢复 → 集中验收。
4. 已复跑 check/eval/demo/collect-dry-run 通过；22 网页用例、100 recorded cases、5 模式、15 来源关闭。
5. test 的 100 Python 用例通过；浏览器服务器被沙箱禁止监听，已申请本地执行重跑。
6. database-test 确认缺本地实例；已有容器清单为空，正在启动隔离 Supabase，无重置。
7. 主要代码缺口：模型仅禁用壳、存储仅内存、数据库公开导出缺网页展示映射、发布备份占位。
8. 最大风险：演示通过掩盖真实链路未实现；不以合成评测替代上线质量证据。

## Round 1 / 12 — baseline and authorization

Evidence: `work/launch-readiness/baseline-*.log`.
The first database startup failed because the installed Docker executable is not on
PATH; retry uses its existing Rancher Desktop path. No dependency added.
Next: complete isolated database baseline, then database-to-public mapping.

## Round 2 / 12 — real database export and strict public fields

- Isolated stack: `scam-radar-readiness`, copied under `/private/tmp`; exact path in
  `work/launch-readiness/local-stack-path.txt`. Existing instances were absent.
- Baseline recovered: 100 Python tests and 4 browser tests passed; real database
  contract passed after the documented temporary-directory mount workaround.
- Added deterministic SQL-v2 presentation mapping and one shared web validator.
  Production requires explicit release path/ID and rejects fixture release IDs.
- `make database-test` now additionally runs real reviewer/policy/release SQL,
  maps its actual export and validates every web presentation field.
- Evidence: `round2-database.log`: 1 real SQL pattern; RED rejects release mismatch,
  missing actions, missing mechanism and invalid Heat; GREEN accepts restoration.
- `round2-check.log`: passed including 32 web tests (22 prior retained).
  `round2-demo.log`: static demo passed. No production service contacted.

## Round 3 / 12 — bounded HTTP and model protocols (in progress)

- Added standard-library transport with destination allowlist, loopback rehearsal,
  no redirects/proxies, response/request limits and bounded retry delays.
- Added OpenAI-compatible and Gemini protocol adapter, existing prompts/schemas,
  PII masking, structured validation, source-span checking and per-attempt cap.
- Real localhost protocol tests running; no model configuration or prompt changed.
- Next: persist source/AI state through narrow database RPCs, integrate orchestration.

## Round 4 / 12 — durable intake and AI artifacts

- Added forward migration `20260918000100`: service-only narrow intake/cache RPCs;
  no new table grants or publication authority. Generated TS types regenerated.
- Disabled sources and foreign URLs rejected; content hashes checked; repeat items
  return one version; mirrored URLs retain provenance; successful AI result cached.
- Actual PostgreSQL tests pass (`round4-database-fixed.log`), including all prior
  review/approval/immutability tests. `round4-schema.log`: 17 schema tests passed.
- Remaining A: registry synchronization, leases/cursors, durable orchestration and
  extraction-to-reviewed-draft integration are not yet implemented.

## Round 5 / 12 — mobile path and search privacy

- Found and fixed URL/history query leakage in homepage and search-page handlers.
  Search handoff is in-memory, cleared on mount; refresh does not retain query.
- `round5-private-search.log`: 104 Python tests and 9 browser tests passed; original
  100/4 retained. Four widths (360/390/768/1440), keyboard search, detail, 404,
  no horizontal overflow, and request/storage query checks pass.
- Screenshots in `work/browser/`; visually reviewed mobile home/search.
  This is local Chromium, not mainland/WeChat acceptance.

## Round 6 / 12 — real exported static build and artifact boundary

- `scripts/build_public_release.py` built the actual SQL-derived release with an
  allowlisted environment, no database/model/reviewer credentials and no fixture fallback.
- Artifact: `work/launch-readiness/database-site`; build output in
  `round6-production-build.log`. Synthetic content remains local and is not uploaded.
- Artifact validation now binds home/search/detail/index release IDs. Secret scanner
  fixed to scan explicitly selected artifacts even when their parent is `work/`.
- `round6-negative.log`: RED search-release mismatch and simulated backend secret;
  GREEN after restoring the disposable artifact copy. Original artifact untouched.
- Existing minimal artifact unit fixture now includes mandatory search page, so its
  file-count assertion increased from 4 to 5; no prior scenario removed or skipped.

## Round 7 / 12 — real publication lifecycle failure cases

- Added transaction-only local SQL coverage of actual deployment RPCs after the
  existing human approval/release contract. No fake database object is substituted.
- Verified mismatched upload receipt rejected, correct receipt retried idempotently,
  failed next build retains current deployed release, authenticated takedown freezes
  a new release, and older release cannot overwrite its successor.
- `round7-database.log`: complete database checks and public mapping pass.
- Still missing: actual upload adapter/orchestrator, live reconciliation and rollback
  of original artifact. SQL lifecycle passing is not a Pages upload rehearsal.

## Round 8 / 12 — dormant model configuration and protocol eval entry

- Official docs verify GLM-4.7, Qwen Plus version and Gemini 2.5 Flash candidates;
  no production model selected. Candidate prices/quotas are not assumed equivalent.
- Configuration change only adds dormant candidates; expected behavior remains
  recorded-only, no automatic provider fallback, live_enabled=false.
- Added local-only configured adapter/eval entry with same dataset hash, call limits,
  validation and latency measurement; report always launch_qualified=false.
- 100 recorded cases passed; behavior manifest updated after running eval.
- Real provider quality, live eval workflow, region-specific Qwen pricing and GLM
  pricing remain unverified/unimplemented; official references retained in config.

## Round 9 / 12 — registry source collector

- Added non-fixture source collector for RSS/sitemap/reviewed list selectors, with
  robots denial before fetch, origin boundaries, content limits, markup failure,
  text masking and stable content identity. Sitemap lastmod is not publication time.
- `round9-collector.log`: 3 new collector tests passed. Existing fixture pipeline
  remains separate and is not presented as the production implementation.
- Source-specific selectors and exact collection permissions remain unverified;
  all 15 real source entries remain disabled. Durable orchestration still missing.

## Round 11 / 12 — integration audit and concentrated activation draft

- Added `docs/ACTIVATION-CHECKLIST.md` with recommended initial caps, data flows,
  credentials, stopping, backup goals, release/DNS rollback and explicit unverified
  items. It is marked not ready for approval because code gaps remain.
- All three configured protocol eval CLI runs used one local server/dataset; tests
  verify equal dataset hash, capped calls, no body in report and no launch claim.
- Audited partial integration honestly in BLOCKED; no FixturePipeline relabeling,
  fake database, test skips or external activation. Updated HANDOFF resume links.
- Next: finish synthetic recovery (Round 10 pending download), then Round 12 serial
  acceptance and report actual unfinished state at the user-specified round limit.

## Goal Router checkpoint — 2026-09-20

- Mission ID: `scam-radar-offline-readiness-decision-011`; original brief/Decision 011
  and completion gate unchanged. Existing PROGRESS/BLOCKED files are canonical;
  no second state directory is created.
- Rui subsequently clarified that goal-router may override the single-agent
  constraint. One bounded workhorse subagent implemented localhost deploy protocol
  rehearsal in disjoint paths; root audited/fixed its GET framing and workflow
  fail-closed exit. Runtime model tier is not reliably detected, so no claimed saving.
- Same-task heartbeat created by app as
  `goal-router-scam-radar-offline-readiness`, every 10 minutes. It would resume only
  on a confirmed quota interruption; it was PAUSED at the 12-round handoff.
- Current slice: Round 10 synthetic encrypted recovery, then Round 12 final serial
  commands and original-criterion audit. No external activation authorized.


## Round 10 / 12 — encrypted recovery rehearsal (diagnosis)

- Verified the official age v1.3.2 darwin/arm64 archive against its published
  SHA-256 `e2020b...f2f5`; extracted only age and age-keygen under ignored work/.
- Three synthetic pg_restore attempts failed before encryption. The first copied
  Supabase's populated template; the second used template0 but dropped `public`;
  third diagnostic recorded `schema "public" does not exist`.
- At the three-attempt stop rule, switched to a fresh template0 database retaining
  its default public schema. No existing instance/database was reset or deleted.
- Evidence: `round10-recovery*.log` and synthetic-only `recovery-*/failure-reason.txt`.
- Official age binary is available locally; failure is now in PostgreSQL restore,
  before encryption or comparison. The isolated container's `postgres` is not
  superuser; its `supabase_admin` can restore, but a full managed-schema dump has
  a missing GraphQL wrapper grant. Narrowing to auth/extensions/private/public/
  migrations exposed a second issue: schema-filtered pg_dump omits extension
  definitions needed by public defaults (`extensions.gen_random_uuid`). After
  three attempts at this changed approach, stop recovery retries per task rule.
  No recovery success is claimed. See latest `recovery-*/failure-reason.txt`.
- Next: finish Round 12 serial acceptance and report the actual code/restore gaps.

## Round 12 / 12 — final serial acceptance, negative gates, honest handoff

- Final commands ran in the required order after the last code/test changes:
  `make check` passed (32 web unit); `make test` passed (112 Python/SQL-related,
  9 Chromium); `make eval` passed 100 synthetic recorded cases with
  `launch_qualified=false`; `make demo` built 5 fixture patterns; isolated
  `make database-test` passed; `make collect-dry-run` kept all 15 sources off.
  Exact logs: `work/launch-readiness/final-{check,test,eval,demo,database-test,collect-dry-run}.log`.
- SQL negative test rejects a draft revision even with a matching synthetic
  review event; exact release/field/Heat mutation checks reject bad exports.
  Disposable site-copy checks reject mismatched search release and simulated
  backend secret, then pass after restoration. Evidence:
  `round12-negative-database.log`, `round12-negative-artifact.log`.
- Localhost-only deploy protocol against the SQL-derived static artifact passed
  build-failure preservation, upload-receipt retry, older-release refusal and
  original-artifact rollback (`final-deploy-rehearsal.log`). Its initial GET
  framing caused an intermittent local connection reset; fixed and rerun green.
- Remaining material gaps are in BLOCKED: durable real-data orchestration and
  joined human UI e2e, actual Pages activation code, encrypted restore/backup
  automation, live model quality/budget, and first exact source permissions.
  Six green commands do not satisfy original completion criteria. No external
  collection/model/production write/upload/deploy/DNS occurred.
- Reached the brief's 12-round stop; Goal Router heartbeat is PAUSED. Do not
  describe this as launch ready or an approval request until code gaps close.

## Decision 011 resumed — 2026-09-20

- Rui explicitly removed the 12-round total cap without changing the objective,
  acceptance standard, or external activation boundary. Historical Round 1–12
  entries remain evidence of prior work, not a new stopping condition.
- The three-failure rule now mandates root-cause review or a changed safe plan;
  unresolved work remains in scope. The prior goal `blocked` status was caused
  only by the former round cap and is superseded by this authorization.
- Continue with durable source → model → database orchestration and joined local
  end-to-end verification first; then complete publishing, encrypted recovery,
  live-evaluation preparation, and the concentrated activation checklist.
- No real source/model/production-data/backup-upload/deploy/DNS activation is
  authorized. Current code gaps remain in BLOCKED until implemented and verified.

### Durable run state and source queue

- Added forward migration `20260920000100_worker_orchestration`: reviewed-source
  activation constraint, service-only registry sync, run records, operation lease,
  source-version claim/retry/finish, and cursor checkpoint. Claims use row locks;
  a failed source run leaves its prior cursor intact. The source-version retry cap
  is three attempts, after which the item needs intervention.
- Real isolated PostgreSQL contract verifies unreviewed source rejection,
  exclusive ownership, wrong-holder rejection, retry, cursor retention/commit,
  idempotent run finish and grants. Evidence:
  `work/launch-readiness/resume-orchestration-db.log` (green after two test/code
  diagnoses). Generated TS database types updated; 17 schema tests and web
  typecheck pass. The new migration was applied only to the named isolated stack.
- Next: connect the collector and model adapters to these durable RPCs, persist
  draft/evidence/Heat/Policy/review in a narrow transaction, then run the joined
  local Auth → release → site path.

### Durable candidate transaction and local protocol chain

- Added service-only transactional candidate intake: one claimed source version
  yields one draft, proposed evidence, exact source spans and claim mappings,
  Heat snapshot and review item. It cannot approve evidence or publish. SQL
  rejects foreign claims, forged offsets and changed replays; a repeat returns
  the original IDs. Generated database types and schema contract updated.
- Added `DurablePipeline` using the existing registry collector, local-capable
  HTTP model provider, narrow Supabase RPC store, Evidence Gate, Heat and Policy
  Engine. Successful AI stages are cached by behavior/input hash. Failures keep
  the prior source cursor and the database caps version claims at three tries.
- The real local HTTP source/model → PostgREST → PostgreSQL run now passes a
  model-failure/recovery/duplicate sequence. First pass fails twice at extraction;
  second reuses stored relevance, completes three-stage analysis and creates one
  draft/evidence/Heat/Policy/review; third creates nothing. The SQL review-list
  contract was made robust to unrelated pending rows while still verifying its
  exact fixture and rejecting candidate payload leakage across every row.
- Evidence: `work/launch-readiness/resume-durable-database-test.log`; direct
  E2E output: `RED→GREEN local model failure retained cursor; resumed from cached
  relevance ... third run no duplicate`. `make database-test` passed with the
  isolated stack after the review-list test correction. No external API called.
- Next: add the fail-closed production batch CLI/workflow, real local Auth login
  and human decision on this new candidate, exact immutable release export and
  static site build in one joined rehearsal; retain all external switches off.

### Joined Auth, release and browser proof

- The production batch CLI and collection workflow now have separate reviewed
  registry, chosen-model, bounded-call, credential and explicit activation gates.
  All current sources and the production model remain disabled/unselected; no
  live job ran. Tests verified the CLI refuses both default and unreviewed
  flagged configurations. New outbound paths are still only dormant code.
- A fresh second local Supabase stack applied all 11 migrations from zero. The
  first joined Auth attempt found `email_provider_disabled`: global signup was
  correctly closed, but the email provider was also disabled. Kept global
  signup closed, enabled email login for admin-created confirmed reviewers,
  restarted only the newly created test stack, and authenticated by password.
- The first human release rehearsal reached an immutable SQL release, then the
  strict mapping rejected missing short name/material date and Heat shape.
  Corrected candidate fields from explicit source/model evidence and added a
  publication-change gate requiring an exportable revision/Heat. The second
  clean-stack run passed: source → model failure/cache resume → PostgreSQL
  evidence/Heat/Policy/review → real Auth login → rejection and human approval
  → exact release export → secret-free static Next.js build. Service-role human
  approval was rejected. Evidence: `work/launch-readiness/joined-full-e2e.log`;
  artifact: `work/launch-readiness/joined-e2e/94122521-83e1-4614-8df7-b18ab0d3988c/`.
- Real Chromium on the SQL-derived artifact passed home/search/detail/no-result/
  404, keyboard submission, private query checks, no horizontal overflow and
  WCAG A/AA automated scan at 360, 390, 768 and 1440 px. Screenshots under
  `work/launch-readiness/joined-browser/`; output in `joined-browser.log`.
  Automated browser checks do not substitute for mainland phone/WeChat review.
- Next: strengthen reviewer UI/browser proof, complete deploy/reconcile/rollback
  state, encrypted backup/restore, live evaluation preparation and final serial
  commands. Current green joined run is offline readiness evidence, not launch.

### Encrypted recovery root-cause repair

- After quota recovery, the prior schema-filtered restore failure was traced to
  omitted extension declarations; a full archive restored them. Replaying no
  ACLs made the service role able to execute the human approval function, so
  that approach was rejected by the actual policy contract. A full archive
  with business ACLs and original object ownership retained all gates; only
  the obsolete managed `graphql_public.graphql` wrapper ACL is excluded from
  the restore TOC. The second dump has no such entry and is accepted.
- `make recovery-rehearsal` passed against the explicitly named isolated local
  stack: age-encrypted synthetic archive, decrypt hash, fresh-database restore,
  25 public-table row counts, exact release export and RLS/service-role approval
  boundary. No upload or real key. Evidence:
  `work/launch-readiness/resume-recovery-green.log` and
  `work/launch-readiness/recovery-3b199ae414a3/report.json`.
- Next: automate the ciphertext-only backup workflow with activation gates,
  then finish deployment state and reviewer UI proof.

### Browser reviewer joined acceptance

- On a newly created isolated `scam-radar-review-ui` stack, the first real
  browser run reached and wrote the final approval but exposed a UI bug: the
  success notice vanished as the queue became empty. The empty state now keeps
  success/error feedback; reviewer copy describes the configured database
  accurately in local and production contexts.
- After resetting only that named disposable stack, the root
  `make joined-local-e2e` target passed. It uses local source/model HTTP,
  actual PostgREST/PostgreSQL, denies public Auth signup, creates a confirmed
  reviewer via local Auth admin, rejects service impersonation, signs in through
  the browser, rejects the seed candidate, accepts each proposed evidence item,
  approves the new candidate, exports the exact immutable release and builds
  the static site. Browser requests remained localhost-only.
- Evidence: `work/launch-readiness/joined-local-e2e-make.log`, initial red
  `joined-browser-review-e2e.log`, and visual screenshot
  `work/launch-readiness/joined-review-browser.png`. `make check` passed after
  the UI and test changes (`resume-ui-check.log`). Generated public fixture
  files were restored after the synthetic build.
- Next: complete deployed/unrecorded reconciliation and real Pages workflow
  behind the existing activation gate, then ciphertext-only backup automation.

### Deployment state and rollback migration

- Added forward migration `20260920000400_deployment_reconciliation`: a private
  current-deployment pointer and append-only receipts separate the currently
  served Pages artifact from immutable public release contents. Service-only
  `note_release_uploaded` records the ambiguous upload-before-registration
  state; `record_deployed_release` reconciles it; explicit
  `record_release_rollback` restores a previously deployed artifact and records
  the new receipt without changing its original manifest or first upload ID.
  A post-upload state cannot be mislabeled as a pre-upload build failure.
- Real SQL contract now rejects wrong upload/rollback hashes and stale active
  expectations, verifies idempotent registration, old-version protection,
  build-failure preservation, and exact rollback pointer/receipt. The migration
  applied to the named readiness stack; a separately created reviewer stack
  was rebuilt from all 12 migrations and `make database-test` passed there.
  Evidence: `work/launch-readiness/resume-deployment-db.log`,
  `deployment-fresh-reset.log`, `deployment-fresh-database-test.log`.
  Generated database types and `make check` pass (`resume-deployment-check.log`).
- Next: connect Pages upload to real release RPCs in a localhost protocol
  rehearsal and implement the production workflow behind final activation
  gates. No Pages request or production database write occurred.

### SQL-backed localhost deployment and empty-release safety

- `make deployment-local-e2e` now joins the already real browser reviewer path
  to real local PostgREST deployment RPCs and a localhost-only Pages protocol
  service. It simulated a lost registration response after successful upload:
  PostgreSQL held `deployed_unrecorded`, then idempotent reconciliation set the
  active pointer. An authenticated local admin made a second immutable release;
  an ordinary older-release upload was rejected, and explicit rollback restored
  the original artifact, pointer and append-only receipt. Original release
  export bytes remained identical. Evidence:
  `work/launch-readiness/deployment-real-local-e2e-green.log`.
- The first second-release build exposed a real empty-release defect: Next
  static export requires one generated dynamic route. A reserved build-only
  route now satisfies Next and is removed from the final artifact, so a
  legitimate full takedown produces home/search/404 without invented content.
  Build preservation also restores prior `web/public` inputs after each exact
  release build. Red failure: `deployment-real-local-e2e.log`; green build:
  `empty-release-build-verified.log`.
- The empty mobile homepage previously showed a blank “recent changes” area;
  it now explains the absence and directs families to pause and verify.
  Category shortcuts previously placed fixed search terms in URLs and no longer
  worked after the private-search change; they now use the same ephemeral
  browser handoff as typed search. Current one-pattern and empty-release
  Chromium checks passed at 360/390/768/1440 px, including private category
  navigation, no overflow, no-result safety text and no dummy detail route.
  Evidence: `one-release-current-browser.log`,
  `empty-release-current-browser.log` and corresponding screenshot directories.
  `make check` passed (`resume-empty-search-check.log`).
- Next: implement actual dormant Pages workflow and backup automation,
  then live-evaluation preparation and final serial acceptance. No external
  upload, production write or DNS change occurred.

### Dormant Pages adapter and guarded workflow

- Added a Cloudflare Pages Direct Upload adapter using the already reviewed
  Wrangler 4.130.0 version and official Pages API deployment receipts. Its
  live destination is fixed to `api.cloudflare.com`; protocol tests inject
  only a localhost endpoint. It validates the exact static artifact, release,
  branch and commit marker, refuses HTTP redirects and ambiguous receipts,
  and never retries an uncertain upload or repeats a previously seen artifact
  without reconciliation. Production rollback checks the current deployment
  and the prior artifact marker before invoking the official rollback API.
- Replaced the disabled deploy placeholder with a manual, exact-release
  workflow. It remains inert unless the separate deployment and activation
  switches, exact confirmation, main-branch commit and production environment
  approval are present. It requires offline CI on that commit, exports the
  immutable release, builds with no credential, scans the artifact, checks a
  preview, uploads the identical artifact once to production, stores the
  uploaded-but-unrecorded receipt, checks the Pages URL, then records the
  deployment. Credential-bearing steps are isolated; the workflow retains
  nonsecret receipt IDs for failure reconciliation. DNS is separate.
- Local HTTP protocol test passed (`test_pages_upload_protocol.py`): receipt,
  smoke, rollback/current-pointer guard, redirect refusal, uncertain upload
  and duplicate-upload refusal. `make check` passed after these changes. No
  Cloudflare, production Supabase or public site was contacted. Official
  protocol reference: https://developers.cloudflare.com/api/resources/pages/subresources/projects/subresources/deployments/methods/list/
  and https://developers.cloudflare.com/api/go/resources/pages/subresources/projects/subresources/deployments/methods/rollback/.
- Next: harden the post-upload reconciliation/rollback runbook and workflow
  checks, then ciphertext-only backup automation and remaining A/D gaps.

### Post-upload failure closure

- The release workflow now performs read-only `inspect` when an upload receipt
  is uncertain and preserves any recovered nonsecret ID for manual
  reconciliation; it never retries the upload. Local Pages HTTP protocol test
  verified exact receipt inspection and prior-upload refusal.
- Found and fixed a real gap in the database recovery path: an upload that
  failed public smoke before becoming active could not be marked resolved.
  Forward migration `20260920000500` adds `upload_rolled_back` plus a
  service-only transactional withdrawal RPC. It verifies the failed upload,
  expected active pointer, restored Pages receipt and original artifact hash;
  records append-only withdrawal and rollback receipts; leaves the previously
  active release intact. Wrong hashes and stale pointers fail, while exact
  replay is idempotent. The deploy runbook now distinguishes this path from
  rolling back an already active release.
- Rebuilt only the named disposable local Supabase review stack from all 13
  migrations. `make database-test` passed, including the new negative SQL
  cases, exact public export mapping and local source/model → PostgreSQL
  review path. Generated database types and `make check` passed. No production
  database or Pages endpoint was contacted.
- Next: exercise the updated withdrawal through a joined local upload-failure
  scenario, then complete the ciphertext-only backup workflow and A/D gaps.

### Joined withdrawal retry diagnosis

- First joined run after migration failed because `make database-test` had left
  a third synthetic reviewer candidate in the same local stack; reset only
  that named disposable database before repeating the browser path. The next
  joined run reached withdrawal and found a real schema defect: restoring the
  same prior Pages deployment twice collided with a uniqueness rule on
  `(release_id, deployment_id, action)`. Those are separate rollback events,
  so the rule represented the wrong identity. Migration 005 now drops that
  tuple constraint while retaining append-only event UUIDs and exact RPC
  replay guards. The SQL contract now exercises two rollback receipts to the
  same original deployment ID.
- Rebuilt the same named synthetic database from all 13 migrations. The real
  SQL deployment/export contract passed, including wrong-restoration-hash and
  stale-pointer rejection. `make deployment-local-e2e` then passed from a
  clean stack: localhost source/model → real database → authenticated browser
  review/rejection/approval → exact static site → Pages protocol upload,
  unrecorded receipt reconciliation, older-release refusal, original-artifact
  rollback, a second upload with failed smoke, and transactional withdrawal
  back to the same original Pages deployment ID. Output ended:
  `GREEN real local PostgreSQL + localhost Pages: upload-unrecorded → reconcile → new release → older-version rejection → original artifact rollback → failed smoke upload withdrawal`.
  The earlier red was a real receipt uniqueness defect and is now green.
- Next: finish ciphertext-only backup automation, then existing-pattern intake,
  operational reporting, live-eval budget, source verification and final suite.

### Ciphertext-only backup automation

- ADR-008 now records official immutable tool pins and SHA-256 checksums:
  PostgreSQL 17.9 Docker image index, age 1.3.2, rclone 1.75.1 (Linux CI and
  macOS rehearsal). No new website/runtime dependency or paid fallback.
- Replaced the disabled backup placeholder with a daily/manual workflow that
  remains inert until separate backup/activation variables and exact
  confirmation are set. The runner downloads checksum-verified tools, pins
  the PostgreSQL client image, requires TLS `verify-full` with a supplied
  Supabase CA, streams `pg_dump -Fc` directly into age without a raw dump
  file, then gives only the age ciphertext and minimal hash manifest to a
  separate R2 step. Database password and R2 keys occupy different steps;
  transient ciphertext and CA are removed after the job. No deletion policy
  or real upload was enabled.
- The R2 adapter restricts live endpoints to the exact Cloudflare account,
  verifies local ciphertext/manifest before network use, lists objects to
  avoid overwriting a prior key, and reads back ciphertext/manifest to compare
  SHA-256. A lost upload response is checked once without a blind retry.
  Official protocol and checksums were verified from PostgreSQL, Supabase,
  age, rclone and Cloudflare documentation.
- Real local `pg_dump` → age → short-lived localhost S3 → readback →
  decryption/archive-inspection rehearsal passed twice after the final shared
  backup change. Repeated upload returned the same receipt; tampered
  ciphertext was rejected before storage. Latest report:
  `work/launch-readiness/backup-e2e-d46f3cec0201/report.json`. Earlier
  `make recovery-rehearsal` independently restored synthetic ciphertext into
  a fresh database and compared 25 public tables, exact release and RLS.
  `make check` passed with the new scripts/workflow.
- Next: finish source/update operational behavior and live-eval budget, then
  final serial commands and activation handoff.

### Quota recovery — 2026-09-20 22:38 UTC

- Work attempt `decision-011-recovery-20260920T2238Z`: the immediately preceding
  task attempts reported a usage-limit stop; fresh five-hour and weekly windows
  were available, with no intervening pause. Existing local artifacts and the
  uncommitted change set were preserved; no external action was repeated.
- Continue with existing-pattern evidence/update intake and local PostgreSQL
  verification. The existing monitor remains active; all activation switches
  stay off.

### Irrelevant-source privacy boundary

- Added forward migration 006: an irrelevant version loses `clean_text` after
  terminal classification while retaining identity/hash for dedupe and the
  recorded classifier result. The prior immutable-content guard initially
  rejected this one-way redaction; it now permits only processing→irrelevant
  nullification (plus backfill of already irrelevant text), not edits to
  processed evidence. No source or model network call was made.
- Real local PostgreSQL contract: RED `source_item_version_content_is_immutable`
  on initial redaction attempt; GREEN irrelevant body purged, processed-body
  tampering rejected, retry/lease/cursor behavior retained. Next: build
  bounded existing-pattern candidate lookup and reviewed evidence updates.

### Quota recovery and existing-pattern transaction — 2026-09-21

- Work attempt `decision-011-recovery-20260921T0338Z`: the prior attempt ended
  with a confirmed quota-limit error. Fresh ordinary quota was available and
  no user pause intervened, so work resumed at the unfinished local contract.
- Approved-pattern lookup is service-only, returns at most ten human-approved
  public-field summaries, and rejects unbounded or reviewer calls. The update
  transaction cannot alter an approved revision: it adds one proposed evidence
  row, creates a supported draft copy, and queues `pattern_update` for human
  review. Wrong claim ownership and `same_pattern=false` are rejected; exact
  replay creates no duplicate. Rollback-only real PostgreSQL contract passed.
- Next: connect this transaction to durable orchestration, add a joined repeat
  run, then finish operational reason codes and the D acceptance work.

### Paused handoff — 2026-09-21 12:34 Asia/Shanghai

- Rui explicitly paused the task. No more implementation, database mutation or
  verification was run after the pause request; external activation remained off.
- Last verified safe boundary: migrations 006/007 and their local PostgreSQL
  contracts passed; the first version of migration 008 passed a rollback-only
  real PostgreSQL contract with foreign-owner/false-match rejection and exact
  replay dedupe.
- Work after that boundary is **unverified**: durable orchestration now supplies
  approved candidate summaries one at a time, proposes an existing-pattern
  review, and records Policy; migration 008 was then changed to recompute the
  future accepted evidence-set hash and update conservative dates/content hash.
  These edits have not been executed after the change.
- Resume at `docs/HANDOFF.md` section “Paused Decision 011 state”. First run the
  narrow existing-pattern SQL/protocol tests, fix them without weakening gates,
  regenerate database types/behavior manifest, then add the joined repeat-run.
- No commit or push was made. Branch remains `main` at `412950d`; the complete
  Decision 011 change set is intentionally preserved in the working tree.
- Goal Router heartbeat `goal-router-scam-radar-offline-readiness` is PAUSED;
  `/root/offline_deploy` was interrupted from `pending_init`. Resume neither
  automatically nor in a new task.

### Decision 012 bounded diagnostic — 2026-09-21

- Rui authorized one 10–15 minute local diagnostic slice without changing the
  Decision 011 mission or external activation boundaries. This run temporarily
  resumes only the bounded existing-pattern verification/repair slice; the wider
  mission remains paused after this slice.
- Goal Router route: Sol/Medium coordinator assumption (runtime tier not reliably
  detected), Terra/Medium workhorse for the implementation/repair outcome,
  Luna/Low only for mechanical verification if time remains, and no frontier pass
  unless a new consequential evidence-backed question appears.
- This ephemeral harness cannot own the recurring heartbeat. Monitor status is
  unavailable for this run; automatic recovery is not enabled, and no scheduler,
  automation, diagnostic hook, routing logic or diagnostic log will be changed.
- Selected slice: execute the narrow migration-008/existing-pattern tests, repair
  only failures within that path, and return exact changed paths and command results.
  No real collection, provider/model call, production access, upload, deployment,
  DNS or other external activation is authorized.
- Bounded Terra workhorse run corrected one stale SQL contract assertion in
  `supabase/tests/local_existing_pattern_contract.sql`: the proposed revision now
  expects recomputed evidence/content hashes and conservative dates while asserting
  that the approved base revision remains immutable. `git diff --check` passed.
- Dynamic migration-008 proof did not run. Existing named stacks predate the final
  migration edit; this harness had no usable local Supabase CLI/fresh-stack path,
  and initial Docker socket access was sandbox-blocked. No old stack was reset or
  mutated. Static database contract tests reported 13 passes and four broader stale
  expectations; generated database types and behavior manifest remain stale.
- Diagnostic log shows Terra owned post-dispatch shell work, SQL edit and static
  verification. Sol performed coordination waits/messages, then read-only evidence
  integration and this checkpoint after Terra stopped; no post-dispatch Sol
  implementation takeover was observed. Diagnostic hook/log and routing logic were
  not changed. Decision 011 returns to paused state after this slice.

### Baseline receipt — 2026-09-23

- Target: resume offline readiness only after a fresh named local database baseline; external activation remains zero.
- Order: static/unit baseline → fresh database contracts → joined browser path → deployment → recovery.
- Start state: `main` at `412950d`; 38 tracked files modified and 58 untracked, preserved without reset.
- Current result: `make demo` passed (5 patterns, 100 static files); `make test` failed 7 / passed 103 / errors 5 before Playwright.
- Database/combined/recovery commands were not run against existing stacks; their required fresh disposable stack is absent from this slice.
- Biggest risk: stale migration 006–008 contracts/types and sandbox localhost binding failures mask the unverified existing-pattern path.

### Recovery cache root-cause review — 2026-09-23

- Fresh-stack artifact inventory shows one relevance artifact for the recovered source-version ID and a distinct seeded fixture artifact; the persisted relevance key itself was reused.
- The coupled model-call assertion still failed, so this is not evidence for changing `durable.py` cache behavior. A subsequent narrow rerun hit the fresh stack's degraded local API (`transient_retries_exhausted`), blocking reliable stage-count isolation.
