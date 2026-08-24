# Stage A：按产品任务重建 RAG 质量地图——执行记录

日期：2026-08-10
分支：`claude/rag-transformation-checkpoints`
计划：`docs/rag-transformation/plans/2026-08-10-stage-a-task-based-evaluation-contract.md`
架构依据：`docs/rag-transformation/plans/2026-08-10-rag-architecture-reassessment.md`
状态：已实施；Gate 结论为 `HOLD`，等待 Conrad 复核后才进入 Evidence Retrieval Gateway

## 1. 本阶段目标与边界

本阶段的目标不是把一个混合分数“调高”，而是建立能支持架构决策的质量地图。它没有修改用户运行路径、LLM、embedding、reranker 或 Graph 模型。

本阶段实现了：

1. 把 32 条题目分为 `item_navigation`、`trend_discovery`、`evidence_research`、`relation_exploration`、`claim_verification` 五类产品任务；
2. 明确每类题的评分合同、标签完备性与人工审核状态；
3. 把尚未具备充分标签或充分性 Gate 的题改为诊断题，避免把“候选检索非空”误判成拒答失败；
4. 为索引快照增加匹配 Gate：数据版本不一致时默认阻断，只有显式方向性运行才允许生成诊断报告；
5. 按任务族独立汇总，而不再把不相同的用户任务混为一个“全产品 F1”。

## 2. 实施内容

### 2.1 评估合同

- `rag/eval_retrieval_quality.py` 新增任务合同分派、诊断题语义、快照检查、分任务汇总与方向性运行标识。
- `docs/rag-transformation/evals/retrieval-quality-dataset-2026-08-10-silver-v2.json` 新增各任务类型的默认合同。
- `claim_refutation` 不再被错误要求“检索必须返回空”；后续应评估能否找到支持、反驳或不足证据。
- `entity_absent` 在证据充分性 Gate 尚未实现时记录为诊断，而非伪造“正确拒答率”。

### 2.2 回归保护

- 新增评估合同、诊断题、快照不一致、方向性运行与 corpus revision 可观测性测试。
- 修复一条既有测试对过滤数组顺序的脆弱假设；测试现在按字段定位日期过滤条件，不限制生产代码添加其他过滤条件。

## 3. 验证证据

### 3.1 自动化测试

```text
.venv/bin/python -m pytest rag/tests -q
413 passed in 6.60s
```

`git diff --check` 通过，无空白错误。

### 3.2 方向性报告

报告：`docs/rag-transformation/evals/retrieval-quality-task-based-directional-2026-08-10.json`

| 项目 | 结果 | 解释 |
|---|---:|---|
| 题目总数 | 32 | 原题全部保留 |
| 可计分题 | 10 | 当前具备 ranked retrieval 标签的题 |
| 诊断题 | 22 | 不是失败题；是尚缺 claim 标签、充分性 Gate 或图关系合同的题 |
| 可计分题 Macro F1@K | 22.65% | 仅作方向性观察，不能代表全产品 |
| item navigation F1 | 41.67% | 导航能力较好但远未稳定 |
| evidence research F1 | 10.96% | 证据检索不足 |
| trend discovery F1 | 8.00% | 当前最优先的产品架构问题 |

### 3.3 快照边界

本次使用的索引观测值为：

```json
{
  "latest_corpus_date": "2026-08-05",
  "document_count": 6098,
  "corpus_revision": ""
}
```

而 Silver v2 标注的目标快照是 2026-08-10，且包含 corpus revision。因此报告状态为：

```text
snapshot_assessment = mismatched_directional
release_gate_eligible = false
```

这意味着：本报告可以用来定位结构问题，**不可以**用于公开宣称召回率、准确率或发布质量达标。

## 4. 质量地图与产品结论

1. “最近有什么热门趋势？”不应继续走普通相似度检索。它应是按时间窗聚合、去重、分散性约束和重要性排序的 `trend_discovery` 路径。
2. “帮我找到某一条内容”应走 `item_navigation`，返回稳定条目 ID 与可跳转位置，而不是先返回日报再让用户翻找。
3. “某公司近期动态 / 某技术证据”应走 `evidence_research`，并先区分候选召回、排序和最终证据充分性。
4. “某说法是否正确”需要 `claim_verification`，其产品结果是 supported / contradicted / insufficient，不是向量 Top-K 是否为空。

## 5. 独立范围审阅

本次改动未改变生产检索逻辑或 Web UI；范围限于评估器、银标合同和测试。代码审阅清单：

- 没有删除低分题来提高分数；
- 没有放宽相关性条件或把 Silver 标注说成 Gold；
- 快照不一致不能进入 release Gate；
- 未观测到 corpus revision 时，即使日期相同也不能成为正式 Gate；
- 所有诊断题在 summary 中与可计分题分开呈现。

## 6. Stage A Gate

### 已通过

- 评估口径不再把五种用户任务混算；
- 快照不一致会被明确标识；
- 测试通过；
- 证据与限制均已落盘。

### 未通过 / 不应声称通过

- 当前索引与标注目标快照不一致；
- `trend_discovery`、`evidence_research`、`claim_verification` 都尚未达到可发布标准；
- 现有指标仍是 Silver 和方向性指标，不能作为公开 Benchmark。

### 下一阶段建议

进入 Stage B 前，需要确认优先级：先落地 `Evidence Retrieval Gateway` 的最小接口，并优先实现 `trend_discovery` 与 `item_navigation` 两条路径；暂不引入 embedding/reranker，以避免在错误的任务路由上做局部调参。
