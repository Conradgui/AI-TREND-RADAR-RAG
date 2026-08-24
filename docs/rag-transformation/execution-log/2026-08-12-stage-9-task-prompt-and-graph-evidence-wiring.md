# Stage 9 执行记录：任务 Prompt 与 Graph Evidence 接线

## 结论

Stage 9 Gate 已重新打开。原实现完成了任务路由、Prompt Registry、Observation Graph 单实体聚合证据和请求级证据台账，但独立质量审查随后确认两项产品级缺口：精确条目导航仍绕经 LLM；多实体关系仍以两份单体聚合摘要代替成对关系证据。

Prompt Registry 的规则已经进入实际 system prompt，因此审查建议的 `PromptEnvelope` 类不作为单独目标；本轮只修复会改变用户结果、成本或证据真实性的缺口。修复计划见 `plans/2026-08-12-stage-9-gate-remediation.md`。

## 实现范围

- `EvidenceRetrievalGateway` 接收当前 retriever 对应的 Neo4j driver。
- `timeline` / `relation_exploration` 追加 Observation-first 图谱证据。
- 多实体关系为每个规范实体生成独立图谱证据，不再静默只处理第一个实体。
- 图谱聚合服务成功时，可恢复普通图检索通道的局部退化，但 trace 仍保留故障事实。
- 图谱聚合服务失败或问题无法规划时，required graph 请求 fail closed。
- Prompt Registry 的任务契约进入实际 system prompt；基础 Agent Prompt 不再鼓励绕过任务契约的自由工具编排。
- 证据预算为时间线/关系任务保留 `graph_reasoning` 记录。
- 证据完整性校验要求最终答案使用所有必需图谱证据；漏用时只允许一次有界修复。

## 测试证据

### 定向自动化测试

- Stage 9 相关回归：`82 passed`
- 最终图谱/证据关键路径：`32 passed`
- `git diff --check`：通过

覆盖：

- 单实体时间线规划；
- 多实体关系规划；
- GraphRAG Evidence Record 进入证据台账并获得 `E#`；
- Graph provider 故障时 fail closed；
- 聚合图证据成功时不误报 Neo4j 整体不可用；
- 时间线证据预算不裁掉图谱证据；
- 最终回答漏用必需图证据时触发一次修复。

### 真实 DeepSeek 用户路径

1. `最近有什么热门趋势？`
   - task family：`trend_discovery`
   - 5 条内部引用
   - direct composer
   - total：约 18.9 秒

2. `OpenAI 的发展历程和变化是什么？`
   - task family：`timeline`
   - graph trace：105 observations / 4 repeated contents
   - 最终可见引用包含 `graph-reasoning/openai`（E6）
   - required graph evidence：无缺失
   - total：约 68.2 秒

3. `请分析 OpenAI 与 Apple 的跨日关联`
   - task family：`relation_exploration`
   - entities：OpenAI、Apple
   - graph trace：2 个实体 / 109 observations
   - 最终可见引用同时包含 `graph-reasoning/openai`（E3）和 `graph-reasoning/apple`（E4）
   - required graph evidence：无缺失
   - total：约 32.9 秒

## 测试中发现并修复的问题

1. 多实体关系最初只为第一个实体生成图证据。
2. 图聚合成功但普通图检索通道退化时，上层会误报 Neo4j 不可用。
3. 图证据虽进入 Gateway，但模型可能不引用，UI 随后会正确隐藏未引用证据。
4. recent-trend 证据预算按顺序截断，可能把最后追加的图证据裁掉。

以上问题均先以失败测试复现，再实施最小修复。

## 残余风险

- 独立质量监管 Agent 未完成审查；原因是子代理额度限制，不是项目通过。
- 时间线真实请求约 68 秒，正确性已达标，但性能仍需在后续性能阶段优化。
- 当前实体识别是保守字典与规范 ID 结合，不应把模糊字符串自动扩张为实体；长尾实体覆盖需要以评估集驱动扩充。

## 独立质量审查补录

独立质量监管已完成。结论为：Web UI 路径没有代码级 P0；Stage 9 因上述两个缺口暂不通过。该结论推翻了本记录早先的“功能 Gate 通过”，属于正常的 Gate 纠偏，不以已有测试数量代替产品行为验证。

## Gate 判定

两项定向修复已完成，见 `execution-log/2026-08-12-stage-9-gate-remediation.md`。

最终功能 Gate：**通过**。

最终独立审查 Gate：**APPROVE（P0=0，P1=0）**。
