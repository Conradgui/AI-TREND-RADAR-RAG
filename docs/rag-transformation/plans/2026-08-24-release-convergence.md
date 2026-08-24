# 2026-08-24 发布收敛计划

## 目标

停止新增功能，把当前已实现但分散在实验、shadow 与正式运行路径中的能力收敛为一个可验证的用户闭环：

```text
用户 Query
  -> Ordered Query v3.5 / Route Contract
  -> Route Contract 驱动检索与证据分层
  -> task-owned Prompt
  -> 结构化回答元数据
  -> Markdown/UI 与精确引用
```

## 证据判断

- 原子日报语料、ATR 唯一编号、浏览搜索索引、筛选器、Graph/Vector 数据层均已实现并有定向测试。
- Hosted sync、规范化、ATR 编号、PR 发布出口已通过本地合同 Gate；仓库 Actions 创建/批准 PR 权限已获得用户授权并开启。
- Ordered Query v3.5 与 Route Contract 驱动检索均已分别通过 Gate。
- 当前正式 `build_chat_response()` 仍只把 `question` 交给 Gateway，未提供 v3.5 Route Contract，因而回退到旧 `analyze_query()`。这是当前最高优先级缺口。
- 工作区包含大量跨阶段实验资产，不能未经筛选整体提交。

## Gate 1：正式垂直接线 Canary

只选择五类任务各一个代表问题，比较旧正式路径与候选路径：

1. 路由是否符合任务；
2. 检索结果是否保持或提升；
3. 引用是否回到具体 ATR 条目；
4. 超时或 Query 理解失败时是否明确降级；
5. 不进行全量索引重建，不新增语料。

通过后才切正式流量。失败时只定位责任模块，不继续扩测试集。

## Gate 2：正式链路接通

- 请求级生成一次 v3.5 Route Contract；禁止下游再次分类。
- 同一合同驱动 Gateway、联网权限、task-owned Prompt 与回答元数据。
- 保留旧路径作为显式降级，而不是静默混用。
- UI 继续消费 Markdown 与结构化 trace，不显示原始 JSON。

## Gate 3：发布验收

- Python、TypeScript、Playwright 定向与完整回归。
- Docker 现有容器真实用户路径：状态、检索、Agent、引用跳转。
- 在 GitHub Runner 上手动触发一次 dry-run，再验证发布权限与 PR 行为。
- 按正式代码、测试、决策文档、必要评估证据分类提交；用户已明确授权验收后直接提交并 push 到 `main`。

## Docker 运维边界

每日语料更新不得重建镜像，因此不得把 Docker prune 接到语料入库链路。后续维护脚本只允许：

- 定期测量；
- 仅在可回收 BuildKit 缓存超过阈值时清理悬空缓存；
- 永不自动删除容器、镜像和数据卷；
- 记录清理前后占用。

## 停止条件

- 不再新增数据源、UI 大改、Router 框架或评估体系；
- 若 Canary 不优于旧路径，停止正式接线并回到对应责任模块；
- 未完成真实 GitHub Action 与 Docker 用户路径前，不宣称 Production Ready。
