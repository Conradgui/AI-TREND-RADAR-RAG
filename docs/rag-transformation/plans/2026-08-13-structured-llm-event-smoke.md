# 结构化 LLM 事件语义抽取冒烟测试

## 决策问题

在相同 `event-contract-v2` 和 5 条高置信新日期样本上，结构化 LLM 是否明显优于规则基线，从而值得扩大到 20 条开发集？

## 公开测试边界

`extract_semantic_event(document, client) -> SemanticEventResult`

输入为单条规范日报记录；输出仅包含：

- `content_kind`
- `event_type`
- `subject_entity_ids`
- `mentioned_entity_ids`
- `extraction_status`
- `diagnostics`

LLM 无权输出或覆盖 ATR ID、来源、URL、报告日期、发布日期及日期 provenance。

## 成本和安全边界

- 只调用 DeepSeek 5 次，每条独立请求；不传整库或其他用户数据。
- temperature=0；JSON object 模式；每条超时 45 秒，至多一次调用，不自动重试。
- 输出先过枚举、实体格式、主体/提及互斥校验；失败进入 `needs_review`。
- 不写 ChromaDB、Neo4j，不重建正式索引，不读取 16 条密封盲测答案。

## 冒烟通过标准

- JSON 合法率 100%；
- content_kind ≥80%（至少 4/5）；
- event_type ≥60%（至少 3/5）；
- subject ≥80%（至少 4/5）；
- mentioned ≥60%（至少 3/5）；
- 非新闻误入率 ≤20%；
- 四个语义字段中至少三个明显优于同组规则基线。

5 条样本过小，只用于路线选择，不能作为生产质量声明。通过后才扩大开发集；失败则先修合同/输入设计，不消耗密封盲测集。
