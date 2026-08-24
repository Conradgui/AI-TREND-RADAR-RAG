# M4：Agentic GraphRAG 检索编排策略

## 目标

让任务证据形状决定关键词、向量、Neo4j 和 Web 通道，而不是所有问题默认执行最昂贵路径。

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

## 评价

通道 Recall、Graph path coverage、错误通道触发率、Web 触发正确率、每通道 P95、失败可解释率、ATR provenance 完整率。
