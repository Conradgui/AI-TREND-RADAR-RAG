# Stage 11 执行记录：任务级评估校准

日期：2026-08-12
状态：功能 Canary Gate 通过；完整语义质量 Gate 保持打开

## 评估资产审计

- `retrieval-quality-gold-candidate-v1.json`：`human_review_pending`、`release_gate_eligible=false`。
- RQ01 “最近有什么热门趋势？”：`missing_trend_cluster_labels`，没有合法 Recall/F1 分母。
- 因此当前不得把历史低分直接解释成生产检索质量，也不得宣称优化后 Recall/F1 已提高。

## 最新 active generation 功能 Canary

快照：`gen-20260812T062943-febd908f`，最新日期 2026-08-12。只读 Vector + Lexical；无 LLM、无联网、无图查询、无索引写入。

结果：5/5 通过。

| Case | 任务 | 结果 | 延迟 | 关键事实 |
|---|---|---:|---:|---|
| C01 | 最近热门趋势 | PASS | 63.35 ms | 5 条、唯一 ID、至少 2 来源、单来源最多 2 条 |
| C02 | Apple 精确标题 | PASS | 10.08 ms | 2 个历史候选，规范目标 Top-1，站内链接稳定 |
| C03 | OpenAI Research Exchange | PASS | 9.37 ms | 规范目标 Top-1 |
| C04 | AgentSky | PASS | 3.67 ms | 规范目标 Top-1 |
| C05 | OpenAI 重要动态 | PASS | 2567.07 ms | evidence_research 非空且路由正确 |

机器可读结果：`evals/gateway-canary-results-2026-08-12.json`。

## 证据边界

这 5/5 只允许声明“核心 Gateway 功能没有在当前正式代回归”。它不验证：

- 结果是否覆盖所有人工认为相关的新闻；
- 每条结果是否语义相关；
- Graph 关系、LLM 回答或联网证据质量；
- Precision、Recall、F1 或长期生产稳定性。

## 下一步建议

先补最小人工相关性标签和评估器判别力测试，再决定是否继续调检索。没有合法尺子时继续改算法，无法区分真实提升与指标噪声。

## 独立质量监管结论

结论：**CONDITIONAL**。

- 功能不回归 Gate：可关闭，但只覆盖固定快照下 Vector + Lexical Gateway 的 5 条契约。
- P0：0。
- P1：缺少经人工复核、覆盖各任务族的相关性标签；完整检索质量 Gate 不得关闭。
- C02 返回两个历史候选但正确目标 Top-1：非 P0/P1。
- C05 单次约 2.57 秒：没有 SLO 与重复分位数证据，暂记 P2。
- 下一步必须先验证评估器能稳定满足“正确结果 > 退化结果 > 错误结果”，再修改检索算法。
