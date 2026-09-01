# Stage 1：确定性路由边界收敛执行记录

- 日期：2026-08-25
- 状态：Gate 通过
- 范围：Query 路由，不修改索引、不重建 Docker、不调用真实模型

## 产品入口覆盖

首页三个推荐问题已经进入 `PRODUCT_QUERY_CASES`：

1. `最近有什么热门趋势？` → `trend_discovery / trend_clusters`
2. `推荐值得深挖的选题` → `evidence_research / deep_research`
3. `Claude 最近有什么动态？` → `trend_discovery / important_news`

目录同时覆盖 A–E 五类常见问题，共 15 条产品回归用例。目录用于高价值入口匹配与回归，
不是穷举用户表达的关键词字典；未逐字命中的问题仍由确定性 Query Signals 泛化。

## 正式链变化

- 新增 `QueryRouteResolver`：产品目录命中和高置信信号均零模型生成 Route Contract；
- 只有低置信、含歧义的问题才允许调用一次 DeepSeek 语义兜底；
- 无 Provider Key 时仍保留确定性 Resolver，不再退回“无 Route Contract”的旧链；
- 移除热门趋势绕过 Route Contract 的临时旁路；
- Route Contract 补充检索主体、主题和来源，供后续 Query 改写与 Retrieval Gateway 使用。

## Gate 证据

```text
126 passed, 5 subtests passed in 2.79s
```

覆盖：产品问题目录、25 条 A–E 开发集、Query Signals、Route Contract、Retrieval Gateway、
Prompt Registry、聊天链和流式端点。测试使用公共 Resolver 与聊天 seam，不调用真实 DeepSeek。

## 证据边界

- 已证明：路线合同选择、首页问题零路由模型调用、合同向 RAG Gateway 传递正常。
- 尚未证明：真实 Neo4j 主动预检、各路线运行时延、真实语料检索质量和最终回答质量。
- 下一阶段：RouteExecutionPolicy 与 GraphReadinessProbe；通过后再进行一次运行时验收。
