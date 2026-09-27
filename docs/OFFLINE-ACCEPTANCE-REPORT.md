# Scam Radar V0.1 离线验收报告 — 2026-09-27

**结论：离线就绪，待最终集中确认。** 这只证明当前工作区代码与本机合成
数据的全流程。真实来源、模型、生产数据库、备份上传、Pages 发布和 DNS
均未启用；真实质量、七天稳定性及大陆/微信访问未验证，
`launch_qualified=false`。

## 复现边界

- 开始于 `412950d`，保留了开工时 94 项未提交/未跟踪成果；差异和测试清单
  存在 ignored `work/offline-resume-20260927/`。本轮未重置旧库或覆盖他人改动。
- 使用 8 个具名、可丢弃的 `/private/tmp/scam-radar-*` 本机 Supabase 栈，
  当前 18 个迁移均从零应用；最终数据库、joined、发布分别使用独立栈。
  SQL、PostgREST、Auth、浏览器、Pages 协议及本机 S3 均是本地合成环境。
- 代码提交：本报告编写时尚未提交；以最终交付的提交标识为准。
  所有日志和截图均为 ignored 临时证据，复跑会产生新 ID/hash。

## 最终命令及证据

| 命令 | 退出码 | 实测通过/失败/跳过 | 证据 |
| --- | ---: | --- | --- |
| `make check` | 0 | 前端单元 32/0/0；格式、lint、类型、生成类型、workflow pin、公开边界、secret 检查通过 | `work/offline-resume-20260927/final-make-check.log` |
| `make test` | 0 | Python 119/0/0，Chromium 9/0/0；静态产物秘密扫描通过 | `work/offline-resume-20260927/final-make-test.log` |
| `make eval` | 0 | recorded 合成案例 100/0/0；行为 hash `c17b9933…`，`launch_qualified=false` | `work/offline-resume-20260927/final-make-eval.log` |
| `make demo` | 0 | 5 个合成模式、100 个静态文件，产物检查通过 | `work/offline-resume-20260927/final-make-demo.log` |
| `make collect-dry-run` | 0 | 15 个来源全部 disabled；真实请求 0 | `work/offline-resume-20260927/final-make-collect-dry-run.log` |
| `make database-test` | 0 | 真实本机 PostgreSQL 契约、导出和 localhost 新骗局全链通过；0 失败/跳过 | `work/offline-resume-20260927/database-final-state.log` |
| `make joined-local-e2e` | 0 | 新骗局及追加证据两条 PostgREST 链、浏览器批准/拒绝、待审延后、同一新版 release 通过；0 失败/跳过 | `work/offline-resume-20260927/joined-final-state.log` |
| `make deployment-local-e2e` | 0 | 本机 Pages 上传/对账、旧版拒绝、原产物回退、失败 smoke 撤回通过；0 失败/跳过 | `work/offline-resume-20260927/deployment-final-state.log` |
| `make recovery-rehearsal` | 0 | 实际本地 release：26 表、新库权限、精确导出；`pg_dump→age→本机 S3→读回→解密` 通过，0 失败/跳过 | `work/offline-resume-20260927/recovery-final-state.log` |

`make recovery-rehearsal` 内实际调用了 `local_backup_e2e.py`；细报告在
`work/launch-readiness/recovery-d5e4b658a85e/report.json` 和
`work/launch-readiness/backup-e2e-ba700759f3ad/report.json`。现存备份
只在本机，没有上传真实 R2。

## 关键反向验证

- 越权持有者、worker 代替人类批准、伪造证据 span、未审核来源、版本混用、
  旧版覆盖、新版 smoke 失败均被拒绝；进程中断后的过期认领由新持有者
  接管，旧持有者不得完成。
- 模型响应失败不推进来源游标，重跑复用已验证阶段且不重复证据或审核；
  待审冲突连续两轮不消耗重试次数，批准后恢复。无关正文在终态清除。
- 篡改密文被拒绝，恢复库核对同一 release、26 表和 service 无审批权；
  静态页面、详情和搜索锁定同一 release。搜索词不进入请求、URL、历史
  或持久化；截图覆盖 360、390、768、1440 宽度。
- 预算不足在模型请求前拒绝，失败重试也占次数和费用保留上界；真实评测
  入口在未授权时拒绝。来源站外链接及栏目结构变化在本机协议下失败关闭。

## 红→绿与覆盖保存

开工 `make check` 因生成类型过期失败；Python 115 项中 106 通过、4 失败、
5 个 localhost 错误。后续分别修复迁移/类型、审核与回退协议、模拟器 POST
边界和行为清单；最终为 Python 119、前端 32、浏览器 9、recorded 100，
全部 0 跳过。开工测试/规格文件清单 50 项仍全部存在。具体红绿记录见
[PROGRESS.md](PROGRESS.md) 及上述 `work/offline-resume-20260927/` 日志。

手机截图实看 360 详情与 390 搜索，主操作、风险提示、证据和应对动作可定位；
自动检查与这次截图抽查不能证明所有老人都能顺畅使用。真实数据质量、
审阅负担、七天稳定性、大陆网络与微信内置浏览器留在
[最终集中确认包](ACTIVATION-CHECKLIST.md) 中；未过关就不发布。
