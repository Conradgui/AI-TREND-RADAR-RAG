# Stage 11 计划：任务级评估校准

日期：2026-08-12
状态：功能 Canary Gate 通过；语义质量 Gate 等待人工相关性校准

## 决策

本阶段先判断评估器能否区分好坏，不再直接修改检索算法。原因是现有 Gold Candidate 明确标记 `human_review_pending`、`release_gate_eligible=false`，RQ01 还没有趋势簇相关性标签；在这种数据上报告整体 Precision、Recall 或 F1 会制造虚假精确度。

## 两层 Gate

1. **功能 Canary**：路由正确、结果非空、精确条目 Top-1 正确、站内链接稳定、趋势结果去重且来源不过度集中。
2. **语义质量 Gate**：在人工确认的分任务相关性集合上，分别报告 navigation、trend、research、timeline、relation、verification 指标；不同任务不得强行平均成一个总分。

## 当前只执行第一层

- 数据集：`gateway-canary-2026-08-12.json`
- 快照：`gen-20260812T062943-febd908f`
- 调用模型：否
- 联网：否
- 修改索引：否

## 下一 Stage Gate 前置条件

- 先对少量查询补齐人工可解释的 relevant / graded relevant / contradiction 标签；
- 做评估器判别力测试，证明正确结果 > 退化结果 > 错误结果；
- 再以该小集比较新旧检索，不先全量重建或调参。

## 独立监管判定

`CONDITIONAL`：允许关闭本计划定义的功能 Canary，但不允许关闭完整检索质量 Gate。P0=0；P1 为缺少经人工复核、覆盖任务族的相关性标签；C02 的第二历史候选和 C05 单次 2.57 秒延迟均暂记 P2。
