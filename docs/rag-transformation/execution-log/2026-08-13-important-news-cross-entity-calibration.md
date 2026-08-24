# 近期重要新闻跨实体校准

日期：2026-08-13
状态：机制小样通过；真实语料质量 Gate 未通过

## 本阶段目标

验证“新闻性 × 重要性”是否能从 OpenAI 五条样本泛化到 OpenAI、Anthropic、Google，而不是继续针对单条结果追加关键词。

## 校准结果

### 机制判别集

- 数据集：`important-news-calibration-v1.json`
- 公司：OpenAI、Anthropic、Google
- 类型：近期重大事件、普通调整、重大调整例外、旧但重要背景
- 结果：12/12 通过
- 边界：这是产品规则判别力，不是真实语料 Precision / Recall / F1。

### 真实语料观察

| 查询 | 主榜数量 | 主要问题 |
|---|---:|---|
| OpenAI 最近有哪些重要动态？ | 4 | 混入视频、观点文章和安全事件，缺少官方重大动态 |
| Anthropic 最近有哪些重要动态？ | 5 | 混入第三方 Claude 工具与兼容性内容 |
| Google 最近有哪些重要动态？ | 1 | 候选覆盖过低 |

## 数据证据

最近窗口共 620 条规范化记录：

| 字段 | 有值数量 |
|---|---:|
| canonical `search-index.json.entity_ids` | 0/620 |
| `entities` | 0/620 |
| `event_type` | 0/620 |
| `content_kind` | 0/620 |
| `summary` | 609/620 |
| `publication_date` | 177/620 |

实体相关候选：

| 实体 | 文本提及 | 官方来源 |
|---|---:|---:|
| OpenAI | 74 | 13 |
| Anthropic / Claude | 80 | 6 |
| Google | 17 | 7 |

## 根因

1. **缺少事件身份**：一条记录没有声明它是发布、合作、诉讼、融资、观点、教程还是配置说明。
2. **缺少实体角色**：无法区分主体公司、被提及公司、兼容对象和比较对象。
3. **时间依据不完整**：多数记录只能使用日报收录日期，旧闻重新入池会被误判为新事件。
4. **候选截断顺序错误**：先截取全局近期候选，再按实体过滤；低频实体会在过滤前被挤出。
5. **上游分数不是新闻重要性**：现有 score 适合选题池优先级，不能直接代表“公司重要新闻”。

补充边界：`LexicalStore` 在构建运行时索引时会根据标题和来源临时推断 `entity_ids`，因此检索并非完全没有实体字段；但规范化源文档没有固化实体身份，而且临时推断无法区分“事件主体”与“正文提及/产品兼容对象”。上述 `0/620` 指规范化源文档层，不是运行时词法索引层。

## 架构判断

当前规则层可以保留为最后一道可解释 Gate，但不能继续承担事件理解。监管复核建议先采用最小事件契约：

- `content_kind`: news_event / research / opinion / tutorial / documentation / product_configuration
- `event_type`: model_release / partnership / leadership / acquisition / funding / litigation / policy / pricing / safety / other
- `subject_entity_ids`: 事件主体
- `mentioned_entity_ids`: 仅被提及或兼容
- `publication_date` + `temporal_confidence`

`impact_scope`、`impact_depth`、`attention_signal` 暂缓，等最小事件字段的提取和人工标签可靠后再决定，避免过度设计。

候选生成必须先按 `subject_entity_ids + 时间窗 + content_kind` 过滤，再进行重要性重排；不能先截断全局 Top N。

## 决策边界

- 不继续追加公司名或标题关键词补丁。
- 不把 12/12 合成集写成真实准确率。
- 不在事件字段缺失时报告 Recall / F1。
- 数据契约应先做单日影子样本，再决定是否迁移全量索引。
