# V0.1 offline launch readiness

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
