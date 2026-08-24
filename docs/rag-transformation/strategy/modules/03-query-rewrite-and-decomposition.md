# M3：Query Rewrite 与问题拆解策略

## 目标

为检索生成多个保真 Query Variant，而不是润色或替换用户原问题。

## 输出视图

```text
QueryVariantSet
  exact_query
  lexical_queries[]
  semantic_queries[]
  graph_queries[]
  web_queries[]
  subquery_dependencies[]
```

## 共同原则

- 原 Query 始终参与召回和最终语义重排；
- ATR ID、引号、实体名、数字、日期、否定词和指定来源不得丢失；
- 关键词变体补充别名、规范名和高信息量名词；
- 向量变体补充任务语境和同义表达；
- 图变体转成实体 ID、关系类型和时间约束，不让模型拼接 Cypher；
- Web 变体只有在 Web 获准时生成，并携带时间窗口与官方域名偏好。

## 按路线差异

- A：不改写 ATR ID；标题模糊时只做有限规范化；
- B：拆出主体、时间和“新闻/趋势”要求；
- C：拆实体、关系和时间片；
- D：拆支持证据、直接反证与缺失判据；
- E：比较时为各主体生成对称子查询，解释题一般不拆。

## 预算

首版最多 3 个内部子查询；只有复合问题和第一轮证据不足才拆解。禁止无界 fan-out 和默认 HyDE；官方案例显示 HyDE 可能因歧义产生完全错误的假设文档。[LlamaIndex 失败示例](https://docs.llamaindex.ai/en/v0.9.48/examples/query_transformations/HyDEQueryTransformDemo.html)

## 评价

- preserve token 违规率；
- Query Variant 独立有效率；
- 候选 Recall 增益；
- rewrite 偏航率；
- 子查询数量、延迟和模型成本。
