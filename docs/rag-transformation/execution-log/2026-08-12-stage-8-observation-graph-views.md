# Stage 8 执行记录：Observation Graph 纵向链与横向视图

## 结论摘要

当前写入层已经具有 Observation，但查询仍读取旧的标题型 Topic，且来源关系存在写入/读取错位。本阶段以稳定 `contentId` 为中心补齐 Content、分类、来源、日报和相邻观察关系，并把图推理切到 Observation-first 口径。

## 数据事实

运行库只读统计：

- Observation：3663
- 稳定 contentId：1691
- 跨日重复内容：295
- 重复内容覆盖观察：2267
- 单内容最长观察跨度：66 条
- OpenAI：105 条观察、41 个日期、3 个来源

## 实现

- 新增 Content 与 Category 唯一约束。
- 新写入产生 `OBSERVES`、`ABOUT`、`FROM`、`PUBLISHED_IN`。
- 相同 contentId 按 `reportDate/date` 形成确定性的 `PREVIOUS_OBSERVATION` 相邻链。
- 日报重跑前读取旧 contentId；条目被移除时重建剩余链并清理孤立 Content。
- 提供已有 Observation 的幂等回填方法。
- 图推理改为读取 Observation 的内容、日期、来源和分类。
- 旧 `topic_count` 暂作为稳定内容数兼容字段，不再对用户称为“趋势主题”。
- 补齐事务绑定 driver 的读接口，保证日期级原子重建可在同一事务内读取旧状态。

## 验证

- GraphRAG、图推理、Prompt、TrendBrief、入库事务、混合检索相关测试：71 passed。
- `git diff --check`：通过。
- 真实 Neo4j 回滚小样：66 observations、65 previous links、1 source、1 category，日期 2026-05-20 至 2026-08-12。
- 回滚确认：Content=0、PREVIOUS_OBSERVATION=0，无正式数据残留。

## 待 Stage Gate 决定

- 是否允许对正式 Neo4j 执行一次性幂等回填。
- 正式回填后验证 Content、关系数量、OpenAI 图推理结果与服务健康。
- 通过后再接 Prompt Registry，不提前扩大范围。
