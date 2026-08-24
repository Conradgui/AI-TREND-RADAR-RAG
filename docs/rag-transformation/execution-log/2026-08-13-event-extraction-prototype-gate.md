# 2026-08-13 事件抽取原型 Stage Gate

## 目标

在不接入正式 ingestion、不写 ChromaDB/Neo4j 的条件下，验证确定性规则能否从规范日报条目自动生成六字段事件契约。

## 已保留的有效架构

- `EvidenceRetrievalGateway` 消费事件主体、内容类型、事件类型、时间可信度。
- 同一 `event_group_id` 只占一个主榜位置，其他记录保留为来源账本。
- `low/unknown` 时间可信记录进入 `unverified_records`，不冒充近期主榜。
- 旧正式索引仍走兼容路径。

## 确定性规则原型结果

### 已见开发集（20 条）

| 字段 | 准确率 |
|---|---:|
| content_kind | 0.60 |
| event_type | 0.35 |
| subject_entity_ids | 0.20 |
| mentioned_entity_ids | 0.70 |
| publication_date | 1.00 |
| temporal_confidence | 0.00 |
| 六字段整条完全正确 | 0.00 |

### 独立盲测（2026-08-04，8 条）

| 字段 | 准确率 |
|---|---:|
| content_kind | 0.00 |
| event_type | 0.00 |
| subject_entity_ids | 0.25 |
| mentioned_entity_ids | 0.00 |
| publication_date | 0.75 |
| temporal_confidence | 0.50 |
| 六字段整条完全正确 | 0.00 |

盲测标注由隔离 Agent 在禁止读取抽取器、Gateway、旧标签和旧结果的条件下完成；主流程在实现冻结后才收到答案，没有根据盲测修补规则。

## 结论

`BLOCK`：停止确定性关键词规则承担开放世界事件抽取。该路线在开发集和盲测均未达到进入生产的最低标准，继续增加词表会提高维护成本并导致过拟合。

保留 `rag/event_extraction.py` 仅作为失败原型和确定性校验参考，不接入正式 ingestion。下一候选路线必须重新经过小样验证。

## 独立监管结论

监管 Stage Gate：`BLOCK` 当前规则抽取器；`CONDITIONAL` 放行下一轮 20 条结构化 LLM 离线小样。

监管同时发现 Schema 漂移：盲测使用 `first_party_news/third_party_news`，而 Gateway 使用 `news_event/tutorial`。这说明“内容是什么”和“来源是谁”被混入同一字段。下一轮必须先冻结统一合同：

- `content_kind`: news / research / tutorial / product_listing / developer_content / pricing_or_configuration / roundup / unknown
- `source_role`: first_party / third_party / unknown
- `event_type`: 约 8–12 个高层类型，并允许 other / unknown

事实字段由源数据锁定，LLM 无权覆盖：ATR 编号、来源、URL、报告日期、发布日期及其 provenance。LLM 只输出语义字段，之后经过 JSON Schema 和确定性一致性校验；失败进入 `needs_review`。

下一轮仍不接 production、不重建索引。最低门槛：JSON 合法率 100%，content_kind ≥85%，subject ≥80%，mentioned ≥75%，非新闻误入率 ≤10%。
