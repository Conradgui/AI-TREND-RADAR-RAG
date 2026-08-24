# Stage 3：结构化证据过滤与分任务评估

日期：2026-08-12

## 本阶段目标

在不全量重建索引的前提下，打通三个可独立验证的纵向切片：

1. 规范化语料中的实体字段能够贯通关键词索引、向量索引、引用和 `EvidenceRetrievalGateway`。
2. 冻结运行评估复用现有的 URL 相关性评分器，按任务族输出指标，不再只支持条目导航。
3. Claim Verification（主张核验）拥有可机器校验的三态结果契约。

## 已确认根因

- `DailyCorpusItem` 已包含 `entities`，但关键词和向量索引的 metadata 丢失了该字段。
- `build_citations()` 支持透传实体，但上游没有稳定提供，所以 Gateway 退化为标题、来源、摘要字符串匹配。
- `eval_retrieval_quality.py` 已实现 Precision / Recall / F1 / MRR / nDCG；`offline_evaluation.py` 却重复实现了只支持导航的评分逻辑。
- Claim Prompt 写了三态要求，但没有机器结果结构，无法测试模型是否真正遵守。

## 公开接口与测试缝

- 检索：`EvidenceRetrievalGateway.retrieve(ResearchRequest) -> EvidenceBundle`
- 冻结评估：`evaluate_frozen_run(dataset_path, run_path) -> report`
- Claim 契约：`compile_task_prompt(...)` 与公开的 Claim 结果解析/校验函数

测试只通过以上接口断言用户可观察行为；内部辅助函数不作为主要测试对象。

## 执行切片

### Slice A：结构化实体链

先写失败测试，证明：

- 标题不含实体、但 `entity_ids` 匹配时，记录应保留；
- 标题包含同名词、但结构化实体明确不匹配时，记录应拒绝；
- 结构化字段缺失时才允许文本降级，兼容旧索引。

然后只修改 ingestion metadata、lexical metadata、citation 透传和 Gateway 过滤。

### Slice B：冻结运行分任务指标

先用 RQ02（趋势发现）固定正确、退化、错误三个 literal fixtures，要求评分满足：

`正确结果 > 退化结果 > 错误结果`

复用 `score_query()` 和 `summarize()`；保留导航 tracer bullet 的兼容输出。RQ01 因缺少趋势簇标签，继续明确标记为 diagnostic，不伪造分数。

### Slice C：Claim 三态契约

定义：

- `supported`
- `contradicted`
- `insufficient`

每个结果必须含理由、证据编号和缺失判据；无直接反证时不得把负面信号判为 `contradicted`。

## Stage Gate

进入下一阶段前必须满足：

- 新增失败测试均由最小实现转绿；
- 现有 ingestion、Gateway、offline evaluator、Prompt tests 全部通过；
- 产出小样分任务指标，不宣称 release-grade；
- 独立质量监管同时复核代码架构和用户流程，不只看单元测试。

## 明确不在本阶段做

- 不全量重建正式索引；
- 不把 6 类任务合成一个总分；
- 不在标签未完成人工复核前宣称 Recall/F1 是正式发布证据；
- 不启动 7–10 次长期稳定性测试，待小样机制通过后单列成本预算。
