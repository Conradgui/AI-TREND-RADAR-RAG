# Offline Evaluation Contract v1

- 日期：2026-08-11
- 状态：G2 分层评估合同已用于最终收口；通用 URL scorer 保留，ATR 分层 scorer 已通过 12 条真实任务验收；G3 自动更新评估另行执行
- 目标：在不启动 ChromaDB、Neo4j 或 LLM 的情况下，独立评分一份冻结运行结果

## 1. 外部 seam

### Dataset Auditor

```text
audit_evaluation_dataset(dataset_path) -> DatasetAuditReport
```

interface 包含：

- 输入 JSON 路径；
- 结构/合同/标签/快照/指标支持检查；
- 明确的可发布资格；
- `0` 表示合同完整，`2` 表示数据无效，`3` 表示仅可开发校准、不可进入发布门。

### Offline Evaluation Runner

```text
evaluate_frozen_run(dataset_path, run_path) -> EvaluationReport
```

interface 包含：

- 数据集与冻结运行结果；
- 按 task family 分离的报告；
- 不跨任务生成单一总分；
- 数据集未晋级时，报告强制标记 `release_gate_eligible=false`。

## 2. Frozen Run schema

```json
{
  "schema_version": "1.0",
  "run_id": "literal-fixture-or-observed-run-id",
  "dataset_id": "retrieval-quality-gold-candidate-v1",
  "corpus_revision": "frozen-revision",
  "origin": "literal_fixture | observed_system_run",
  "selected_query_ids": ["RQ08"],
  "results": [
    {
      "query_id": "RQ08",
      "retrieved": [
        {
          "identity": "url:https://example.com/item",
          "url": "https://example.com/item",
          "source": "OpenAI",
          "topic": "",
          "canonical_content_id": ""
        }
      ],
      "evidence_judgment": null
    }
  ]
}
```

约束：

1. literal fixture 必须手写固定结果，不能由 scorer 或 gold 标签自动生成；
2. observed run 必须记录产生它的检索 adapter 与 corpus revision；
3. scorer 只读取 frozen run，不调用检索器；
4. 未知 query ID、重复 result、快照不匹配均明确失败。
5. 开发校准 run 必须显式列出 `selected_query_ids`；只评价被选择的问题。
6. 未选择的问题不计失败，报告必须返回相同的 `evaluated_query_ids`。

## 3. 两个评价层

### 任务合同优先

同一份运行快照不能用一个指标解释所有任务。G2 的 ATR 扩展按以下方式报告：

- `item_navigation`：目标 ATR 排名、Recall@5；
- `recent_trend`：Primary 覆盖、主答案精度、Supporting 命中；
- `relation_comparison` / `timeline`：期望 ATR 的精确率与召回率，同时检查关系/时间边界；
- `evidence_insufficiency`：澄清是否发生在检索前、是否零模型调用，或未找到时是否披露语料边界。

这些指标不做跨任务全局 F1。RAGAS/LLM-as-a-Judge 可以作为未来抽样的生成层审计，但不是 G2 放行前置条件，也不能替代人工确认的 ATR 标签。

### Agentic RAG 执行评估

检索分数之外，复杂任务的 frozen run 还应保留：是否应进入 Agent、计划步骤数、实际工具序列、每步状态、纠偏次数、停止原因、模型/工具调用数、耗时和最终使用的 Evidence ID。首轮按任务报告：

- `agent_entry_accuracy`：该进 Agent 的进入、不该进的保持快路径；
- `tool_selection_accuracy`：必要通道是否调用、禁止/无关通道是否避免；
- `useful_step_rate`：产生新证据或完成必要转换的步骤占比；
- `stop_correctness`：证据足够时停止，证据不足时明确澄清/降级；
- `grounded_task_completion`：用户任务完成且核心结论均有 Ledger 证据；
- `budget_compliance` 与端到端延迟。

这些指标与 Hit@K、MRR、Faithfulness 分层呈现：检索失败、Agent 编排失败和生成失败不能互相代偿。简单任务零 Agent 调用是成功，不是能力缺失。

### Retrieval Ranking Evaluation

适用：`item_navigation`、`trend_discovery`、`evidence_research`。

首轮支持：

- navigation：Hit@1、MRR；
- trend/research：NDCG@K、来源覆盖；
- URL/canonical content 去重；
- 每个任务独立报告。

暂缓：

- topic coverage，直到趋势簇标签经独立复核；
- Graph relation quality；
- 跨任务宏平均分。

### Evidence Sufficiency Evaluation

适用：`evidence_sufficiency`。

`evidence_judgment` 最小字段：

```json
{
  "verdict": "supported | contradicted | insufficient",
  "used_evidence_identities": [],
  "claim_evidence_relationship": "direct | near_neighbour | unrelated",
  "forbidden_inference_triggered": false
}
```

首轮只评分：

- verdict 是否与 expected verdict 一致；
- 是否把 near-neighbour 当成 direct evidence；
- 是否触发 forbidden inference。

检索到近邻证据但 verdict=`insufficient` 可以正确；零检索并拒答可以接受，但不被定义为唯一正确路径。

## 4. 最小 tracer bullet

第一条仅使用 RQ08：

| fixture | 目标位置 | Hit@1 | MRR |
|---|---:|---:|---:|
| correct | 1 | 1 | 1.0 |
| degraded | 5 | 0 | 0.2 |
| wrong | 缺失 | 0 | 0.0 |

它只证明 navigation scorer 能识别排序退化，不证明趋势质量、整体 RAG 质量或新架构优于旧架构。

RQ08 使用两个不同参数：

- `hit_cutoff=1`：只判断第一名是否命中；
- `evaluation_depth=10`：MRR 最多观察前十名，因此 Rank 5 必须得到 0.2，而不是被 Hit@1 截断。

## 5. 停止条件

1. Dataset Auditor 不能发现数据集声明了未实现指标；
2. scorer 需要连接生产依赖；
3. literal fixture 由 scorer 反向生成；
4. 结果被跨任务聚合为一个总分；
5. candidate dataset 被错误标记为发布证据；
6. 监控 Agent仍给出 `BLOCK`。
