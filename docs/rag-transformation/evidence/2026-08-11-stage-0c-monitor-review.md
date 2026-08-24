# Stage 0C 独立阶段门审查

- 日期：2026-08-11
- 审查角色：独立决策监控 Agent（Lorentz）
- 审查范围：Stage 0 章程、32 条资产审计、12 条 Gold Candidate、当前 retrieval evaluator 与测试
- 结论：`BLOCK`

## 1. 阻断结论

当前不能直接进入“正确结果 > 退化结果 > 错误结果”的 TDD 实现。阻断原因不是 12 条任务方向错误，而是数据集声明的产品指标与当前评估器能力不一致；此时由同一执行方构造 fixture、实现 scorer、再证明严格递减，存在按构造必然通过的循环论证。

## 2. 关键事实

1. 数据集仍为 `human_review_pending` 且 `release_gate_eligible=false`；它可校准评估器，不能判断架构优劣。
2. 数据集声明 `source_coverage`、`topic_coverage`、`hit_at_1`、`verdict_accuracy`，当前评估器未实现这些合同。
3. 当前 evaluator 将 `answerable=false` 简化为“零检索结果才正确”，会把“检索到近邻证据但正确判断证据不足”误判为失败。
4. RQ01 仍是一组文章 URL，没有趋势簇、趋势强度或跨来源支持定义，因此只能测文章排序，不能完整测趋势发现。
5. RQ02、RQ04、RQ06 存在相关性或“值得关注”阈值争议，尚不能晋级 Gold。

## 3. 解除阻断条件

1. 分开 `Retrieval Ranking Evaluation` 与 `Evidence Sufficiency Evaluation`；
2. 建立离线 `dataset + frozen run -> report` interface，不依赖 ChromaDB、Neo4j 或 LLM；
3. 先用干净的 RQ08 完成最小导航 tracer bullet；
4. 趋势暂缓 `topic_coverage`，先实现 NDCG、来源覆盖和 canonical content 去重；
5. 争议标签由独立审阅者处理，Conrad 只确认产品语义；
6. fixture 必须是独立字面样本，不能由 scorer 反向生成。

## 4. 建议的后续顺序

1. 独立审阅争议标签；
2. 固定两个评价层及离线 run schema；
3. 监控 Agent复审；
4. 通过后只实现 RQ08 Red -> Green；
5. 再分别扩展趋势和证据充分性，禁止一次性横向铺开。
