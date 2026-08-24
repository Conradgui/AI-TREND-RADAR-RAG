# 2026-08-21 Route Contract 驱动检索影子 Gate

## 目标

在固定 generation `gen-20260821T074117-404548ad` 上，证明同一份 Route Contract 能直接驱动
检索，而不会在 Gateway 内再次被旧 `analyze_query()` 改写或重新分类。

## 公共 seam

```text
EvidenceRetrievalGateway.retrieve(
  ResearchRequest(question, route_contract, latest_corpus_date, limit)
) -> EvidenceBundle
```

调用方只需知道原问题、已解析 Route Contract 与运行边界。合同校验、兼容投影、元数据过滤、
通道选择和审计轨迹都属于 Gateway 的实现。

## 本轮最小垂直切片

1. `ResearchRequest` 可携带可选 Route Contract；不携带时保持现有正式路径不变。
2. 合同路径在检索入口执行 Schema 形状与产品语义校验。
3. `primary_task_family` 决定 A–E 检索视图，不再调用旧问题分类器。
4. `absolute_range` 必须含合法 `start/end`；旧合同缺失边界时返回
   `route_contract_reunderstanding_required`，不得静默降级为无时间过滤。
5. 绝对时间边界进入 metadata filter；EvidenceBundle trace 标明合同版本、路由与 shadow 状态。
6. 评估结果必须按五类 task family 分层；本轮不接正式 Agent、不改索引、不调全局排序公式。

## TDD 顺序

1. 红灯：合同指定 `claim_verification` 时，即使问题文本会被旧规则误判，Gateway 仍返回该路由。
2. 绿灯：加入最小合同入口与内部兼容投影。
3. 红灯：缺少绝对时间边界的旧合同在检索前失败。
4. 绿灯：加入检索入口合同校验。
5. 红灯：合法绝对范围没有进入检索过滤器。
6. 绿灯：把机器可读边界投影为 Chroma 过滤条件。
7. 运行 Gateway、时间规划、Route Contract 与分层评估相关回归。

## Gate

- 三个行为测试通过，且测试只经过 Gateway 公共 seam；
- `question-only` 既有 Gateway 回归不退化；
- 无 Docker、Neo4j、Chroma 数据写入；
- 无 DeepSeek 调用；
- 质量监管确认方向与用户流程一致后，才进入候选分层与 route-specific rerank。

## 明确不做

- 不接 `chat_service` 正式回答链；
- 不创建新语料、不重建索引；
- 不修改 Prompt Registry、Answer Envelope 或 Web UI；
- 不引入第三方 Router/RAG 框架；
- 不用聚合指标掩盖单一路由退化。
