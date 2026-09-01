# M4：Agentic GraphRAG 检索编排策略

## 目标

让任务证据形状决定关键词、向量、Neo4j 和 Web 通道，而不是所有问题默认执行最昂贵路径。

本模块中的“Agentic”表示复杂任务可动态选取检索工具、检查中间证据并受限纠偏；不表示所有 Query 都进入自由 ReAct 循环。单步可预测任务继续由 Workflow 控制。

## 通道路由

| 路由 | Lexical | Vector | Graph | Web |
|---|---|---|---|---|
| A | 必选 | 标题模糊时降级 | 禁用 | 禁用 |
| B | 必选 | 必选 | 结构趋势时可选 | 明确最新或内部过时时 |
| C | 实体解析/过滤 | 文本证据补充 | 必选 | 外部事实缺口时 |
| D | 必选 | 必选 | 关系属于判据时 | 一手核验或内部不足时 |
| E | 必选 | 必选 | 多跳/全局结构时 | 用户要求或证据不足时 |

## GraphRAG 边界

- Local-style：具体实体邻居、关系和支持文本；
- Global-style：整个语料的主题结构，成本更高；
- DRIFT-style：需要从全局主题展开到局部证据的复杂研究；
- Basic：普通关键词/向量证据研究。

微软官方也按 Local、Global、DRIFT 与 Basic 区分查询方式，说明 GraphRAG 不是一个对所有问题统一开启的开关。[GraphRAG Query Overview](https://microsoft.github.io/graphrag/query/overview/)

## 执行策略

1. 各通道并行并保留独立状态；
2. 任何结果必须带 ATR/content 身份和 provenance；
3. Graph 返回关系/路径/时间结构及支持它们的 ATR，不与文本原始分数直接相加；
4. Web 先过权限、时效、来源角色、官方优先和正文准入；准入后仍是外部 Evidence Candidate；
5. Evidence Grade 不足时最多一次内部 corrective retrieval，再决定是否 Web；
6. required Graph 失败必须显式降级，不能伪装成关系分析成功；
7. 文本候选、Graph 结构和 Web 候选只在“对当前问题承担什么证据角色”的分层阶段汇合，不直接混加原始分数。

## Agent 循环合同

只有满足“多步推理、动态来源选择、查询分解、首轮证据不足”之一时才进入 Agent 循环。循环最多包含：计划一次 → 执行工具 → 检查 Evidence Grade → 必要时纠偏一次 → 停止并交给答案构造。每一步记录工具、输入摘要、状态、耗时、证据 ID 和停止原因，不记录隐藏思维链。

禁止项：对明确导航调用模型、证据已足够仍继续检索、同一失败工具无新参数反复重试、Graph 不可用时伪造关系答案、把模型解析结果直接写成长期事实。

## 评价

通道 Recall、Graph path coverage、错误通道触发率、Web 触发正确率、Agent 进入正确率、工具选择正确率、有效步骤率、停止正确率、预算合规率、每通道 P95、失败可解释率、ATR provenance 完整率。
