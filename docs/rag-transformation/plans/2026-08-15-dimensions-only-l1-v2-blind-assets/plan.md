# Dimensions-only L1 v2 隔离盲测资产计划

- 日期：2026-08-15
- 目标：新增 15 条不可见盲测及相互隔离的 runner、scorer、manifest。
- 冻结边界：不修改 freeze manifest 中任何 artifact；不读取任何旧 sealed、canary、calibration 或 results 数据。
- 运行边界：只做离线结构验证，不调用 DeepSeek 或其他网络 API。

## 阶段

1. 核对放行合同、冻结哈希与公共调用接口。
2. 独立设计 15 条 query-only 样本和 sealed Gold，五个主任务族各 3 条。
3. 实现启动前哈希验证、只读 query 的 runner，以及 predictions-first 的 scorer。
4. 生成 sealed manifest，执行离线结构、隔离、哈希与评分器辨别力测试。

## 验收口径

- Query 文件只有 `case_id`、`query`、`conversation_context`。
- Gold 文件每条只有约定的七类标签字段和 `case_id` 关联键。
- Runner 源码和运行时均不读取 Gold；输出已存在时拒绝覆盖。
- Scorer 在 predictions 缺失时于读取 Gold 之前失败。
- 总体门槛：完整合同准确率 ≥85%，每主任务族路由准确率 ≥80%，关键权限 100%，澄清 precision/recall 均 ≥80%。
