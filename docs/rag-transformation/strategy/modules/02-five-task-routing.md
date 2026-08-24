# M2：五类任务路由策略

## 目标

消费 Intent Signals，只裁决一次主任务与可选辅助任务，并生成版本化 Route Contract。

## 五类路线

| 路由 | 语义名 | 进入条件 | 禁止误用 |
|---|---|---|---|
| A | `item_navigation` | ATR ID、精确标题、明确单条定位 | 不生成长分析，不默认 Graph/Web |
| B | `trend_discovery` | “最近发生了什么、什么值得关注”；最近动态、重要新闻、热点簇 | 单条新闻不能直接称趋势；不负责解释结构如何演变 |
| C | `temporal_relation_exploration` | “如何演变、彼此有什么关系、形成了什么结构”；时间线、跨日变化、实体关系 | 共现不能表述为因果；不能退化成普通新闻榜 |
| D | `claim_verification` | 验证可判定主张或来源真实性 | 负面信号不能自动等于反证 |
| E | `evidence_research` | 解释、比较、深挖、指定证据研究 | 不能成为无约束的垃圾 fallback |

## Route Contract

必须包含：版本、原始 Query、主/辅任务、answer mode、实体/主题、时间与来源约束、联网权限、歧义、rewrite/retrieval/output/budget 合同 ID。B–E 必须携带 `prompt_contract_id`；A 的该字段为不适用，并必须携带版本化 `answer_builder_contract_id`。

## 分类策略

1. A 是强确定性优先路径；
2. 其余按用户成功标准分类，不按底层工具分类；
3. “最近有什么趋势”默认按新闻发现进入 B；只有用户明确要求演变、关系、跨时间或跨实体结构时才进入 C；该边界已于 2026-08-13 获得产品确认；
4. C 的 `answer_mode` 是必填枚举：`timeline / relation / longitudinal_trend / cross_sectional_trend`；输出 Schema 保留对应分支；
5. B 可以使用 Graph 补充趋势簇，但不会因为使用 Graph 自动变成 C；
6. 复合问题使用主路线 + 辅助路线，不复制流水线；
7. 置信度不足时允许一次小模型结构化裁决，或提出一个必要澄清；
8. 所有后续模块只读 Route Contract，不再次猜 route。

## 评价

- 主任务准确率；
- 辅助任务召回率；
- A 路由零模型调用率；
- Route Contract 交叉字段有效率；
- rewrite、Prompt 和 output schema 版本一致率。

接口可参考 LlamaIndex RouterRetriever 的“按 Query 与检索器元数据选择一个或多个检索器”，但当前项目无需引入该依赖。[官方接口](https://docs.llamaindex.ai/en/stable/api_reference/retrievers/router/)
