# Route Contract v2 影子理解器实施计划

- 日期：2026-08-13
- 状态：影子实现完成；进入全新封存盲测
- Stage Gate 前提：Route Contract v2 资产已获独立监管 `APPROVE`

## 目标

实现一个纯函数 seam：

```text
understand_query_v2(original_query, conversation_context=None) -> RouteContractV2
```

它负责保留原问题、提取可共存 Intent Signals、选择一个主路线和可选辅助路线、选择 answer mode 与版本化合同 ID。首轮以确定性规则覆盖高置信路径；不确定问题保留歧义，不伪装成完整理解。

## 本阶段允许

- 新增独立的影子理解模块和离线评估器；
- 使用 25 条开发小样 TDD；
- 计算路线、answer mode、联网权限、合同 ID 和保真词指标；
- 记录旧 QueryPlan 与 V2 的差异，但不把旧结果当 Gold。

## 本阶段禁止

- 不接 `chat_service`、`server`、Neo4j、向量检索、Prompt Registry 或 Web UI；
- 不覆盖现有 `analyze_query`；
- 不调用 DeepSeek 或联网服务；
- 不用开发集成绩宣称真实用户质量；
- 不评价尚未标注的实体、主题、时间和来源抽取质量。

## TDD 垂直切片

1. A：精确 ATR / 完整标题 / 模糊标题消歧；
2. B/C：新闻发现 vs 演变关系；
3. D/E：可判定主张 vs 解释比较研究；
4. 复合任务：一个 primary + 零到多个 supporting；
5. 统一合同：Schema、语义 validator、保真 token 和合同 ID。

## Stage Gate

- 分路线报告，不使用一个总体 Accuracy 掩盖弱项；
- B/C 对照样本必须全部通过；
- A 路由不得产生 Prompt Contract；
- D/E 不得因“是否”二字简单混淆；
- 正式链路保持零改动；
- 质量监管 Agent 同时检查产品任务成功标准、成本和后续可维护性。

## Stage Gate 结果

- 最终裁决：`APPROVE`（2026-08-13）。
- 可进入：冻结影子资产，创建一次性 query-only sealed blind test。
- 仍禁止：接入 `chat_service`、正式检索、Prompt Registry、DeepSeek 和 Web UI。
- 盲测口径：`docs/rag-transformation/specs/route-contract-v2-annotation-guide.md`。
