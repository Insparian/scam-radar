# 离线就绪后的外部关卡

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
