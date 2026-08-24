# Stage A：按产品任务重建 RAG 质量地图

日期：2026-08-10
状态：已实施并完成本地验证；Stage A Gate 等待 Conrad 复核
上位决策：`2026-08-10-rag-architecture-reassessment.md`

## 1. 本阶段目标

本阶段不优化检索算法、不更换 embedding、不安装 reranker，也不追求把当前 F1 做高。

唯一目标是建立一个不会误导后续架构决策的质量地图：

1. 不同产品任务分别评分；
2. 被测索引和标注快照不一致时阻止正式结论；
3. 区分“可评分检索题”和“只有诊断价值、尚无充分标签的题”；
4. 明确候选召回、最终排序、证据充分性和最终回答是四个不同层级；
5. 为下一阶段 Evidence Retrieval Gateway 提供稳定测试 seam。

## 2. 五类任务合同

| task_family | 当前题目 | 用户成功标准 | 本阶段评分 |
|---|---|---|---|
| `item_navigation` | RQ07、RQ08、RQ09、RQ11 | 第一条结果就是目标条目，且能跳到具体位置 | Hit@1、MRR、NDCG |
| `trend_discovery` | RQ01、RQ05 | 最近时间窗内结果新鲜、重要、去重且来源/类别不过度集中 | NDCG、Freshness、来源/类别覆盖、重复率；银标 Recall 只作诊断 |
| `evidence_research` | RQ02、RQ03、RQ04、RQ06 | 相关证据进入候选池，并在最终证据中靠前 | Recall@5/10/20/50、MRR/NDCG、P95 |
| `relation_exploration` | RQ10；后续新增真实关系题 | 关系结论有图路径和原始证据支持 | 本阶段只建立空合同，不把普通 URL 命中冒充图推理质量 |
| `claim_verification` | RQ12、HN01–HN20 | 输出 supported / contradicted / insufficient，并附相应证据 | 本阶段 diagnostic only；等充分性 Gate 和反驳标签存在后评分 |

## 3. 关键评分纠偏

### 3.1 不再把“底层检索返回空列表”当作拒答

向量/词法检索器的职责是生成候选，通常总会返回最近邻。真正的拒答发生在 Evidence Sufficiency（证据充分性）判断之后。

因此：

- `entity_absent`：当前只记录它召回了什么、是否出现危险的伪精确匹配，不计入 retrieval Macro F1；
- `claim_refutation`：必须先补充可用于反驳的相关证据标签，再评估能否检索并反驳；不能要求零召回；
- 当前报告中的“正确拒答率 0%”保留为历史数据，但标记为无效口径，不作为 Gate。

### 3.2 不再跨任务汇总单一 Macro F1

保留逐题原始指标，但正式 summary 改为：

```text
by_task_family
  item_navigation
  trend_discovery
  evidence_research
  relation_exploration
  claim_verification
diagnostics
unscored_reason_counts
```

可以提供“可评分 ranked retrieval 汇总”用于观察趋势，但必须明确 `not_a_release_gate=true`，不能再把它解释为整个产品的准确率。

### 3.3 标签完备性进入合同

每道题增加：

- `relevance_set_status = complete | sampled | missing`
- `evaluation_contract = ranked_retrieval | discovery_ranking | diagnostic_only | future_claim_classification`
- `review_status = ai_proposed | human_reviewed`

`sampled` 相关集不能把未标注结果自动当成绝对错误；其 Precision/Recall 只作方向性参考。

## 4. 快照 Gate

正式评估前比较：

- 标注目标的 `latest_corpus_date`；
- 被测 vector/lexical generation 的最新日期；
- generation manifest 中可用的 corpus revision / document count。

规则：

1. 一致：`snapshot_status=matched`，允许形成正式分任务报告；
2. 不一致：默认退出并说明缺口；
3. 只有显式 `--directional` 才允许继续，输出必须带 `snapshot_status=mismatched_directional`，不能用于发布 Gate。

当前 2026-08-10 银标对 2026-08-05 本地索引的结果只能属于第 3 类。

## 5. 候选召回与最终证据分离

对于 `evidence_research`，一次生成足够大的候选池，再计算多个 cutoff：

- Recall@5
- Recall@10
- Recall@20
- Recall@50
- MRR@10 / NDCG@10

判读逻辑：

- Recall@50 仍低：优先检查数据、解析、query representation、embedding 和索引；
- Recall@50 高但 NDCG@10 低：优先检查融合和 reranker；
- 两者都高但最终回答差：问题在 EvidenceBundle 或生成层，不再修改 retriever。

注意：本阶段先使评估器支持该合同；若当前生产接口会在进入评估前截断候选，则明确记录 `candidate_observability=blocked`，不伪造 Recall@50。

## 6. 计划改动范围

### 数据集

- 为 Silver v2 增加 task family、evaluation contract、relevance set status；
- 保留全部原题，不通过删除失败题提高结果；
- HN 题继续保留，但 diagnostic only；
- 不将 AI 标注升级为 Gold。

### 评估模块

- 将评分从单一 `score_query` 分派为任务合同；
- summary 按 task family 聚合；
- 未评分题输出明确原因；
- 加快照匹配检查和 `--directional`；
- 保留历史报告，不覆盖旧 JSON。

### 测试

新增以下回归测试：

1. claim-refutation 不再被判定为“检索必须为空”；
2. entity-absent 在缺少 sufficiency gate 时为 diagnostic only；
3. 不同 task family 不混算发布指标；
4. sampled relevance set 带方向性警告；
5. snapshot mismatch 默认阻断；
6. directional 模式允许运行但不能产生发布 Gate；
7. item navigation 只按首位导航质量评分；
8. legacy 数据集仍可读取，并被映射为明确的 legacy 合同。

## 7. 本阶段明确不做

- 不调整生产 Top K、RRF 或 boost；
- 不安装 embedding/reranker 依赖；
- 不重建 Neo4j 模型；
- 不修改 Web UI；
- 不把 Silver 自动变成 Gold；
- 不对缺少反驳证据标签的题计算虚假的 claim F1。

## 8. 验证表

1. 数据合同重构 → 验证：32 题均有 task family、合同、标签完备性和审核状态。
2. 评分分派 → 验证：claim-refutation 与 entity-absent 不再污染 retrieval Macro。
3. 分任务 summary → 验证：导航、趋势、研究、关系、核验独立展示。
4. 快照 Gate → 验证：8 月 10 日标签对 8 月 5 日索引默认失败；显式 directional 才运行。
5. 回归测试 → 验证：focused tests + Python 全集通过。
6. 新报告 → 验证：报告明确哪些是有效结果、哪些只是诊断，不再输出误导性的“全产品准确率”。

## 9. 自审结果

### 通过项

- 先修评价尺，不先追分，符合当前架构重估目标；
- 没有删除失败题或放宽相关标签；
- 把检索、排序、拒答和最终答案拆成不同层级；
- 保留旧报告，保证历史可追溯；
- 对未来 Gateway 只建立测试合同，没有提前锁死具体框架或 reranker。

### 风险与约束

1. 当前 Silver 相关集仍由 AI 提议，分任务指标只能指导工程，不能作为公开 Benchmark 结论。
2. `trend_discovery` 的相关集合天然难以完备，后续需要 Conrad 对“什么算重要趋势”做小样本人工判断。
3. `relation_exploration` 尚缺真实图关系标注，本阶段只能显式暴露缺口，不能制造分数。
4. Recall@50 是否能从当前生产调用链观察，需要实施时验证；若被 admission/rerank 截断，应在 Gateway 阶段建立候选层测试 seam，而不是从测试中绕过生产逻辑。

### 自审结论

`APPROVE`：Stage A 已按本计划实施。该阶段只重构评估合同，不改变用户当前运行路径；执行证据见 `../execution-log/2026-08-10-stage-a-task-based-evaluation-contract.md`。完成后按约定暂停，由 Conrad 审阅质量地图，再进入 Gateway 接口设计。
