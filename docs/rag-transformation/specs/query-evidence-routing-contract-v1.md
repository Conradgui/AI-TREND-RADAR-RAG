# Query Evidence Routing Contract v1

- 日期：2026-08-13
- 产品语义状态：已确认
- 实现状态：提案；尚未接入正式检索链和索引
- 决策依据：ADR-0005

## 1. 产品原则

系统不再回答“这条内容全局上是否重要”，而是回答两个依次发生的问题：

1. 这条内容对当前用户问题承担什么角色？
2. 在承担相同角色的内容中，哪一条更重要、更新鲜、证据更可靠？

因此，相关性负责准入和分层；重要性、新鲜度和证据质量只负责层内排序，不能跨层把背景内容推成主答案。

## 2. 稳定事实与动态判断

### 入库后保持稳定的事实

- `daily_item_id`、`content_id`、观测日期和原始发布日期；
- 标题、摘要、正文、规范 URL、来源及来源角色；
- 主体实体、提及实体、主题、事件类型和内容类型；
- 当次录入时固化的热度快照；
- 字段来源、内容完整度、日期置信度和质量诊断；
- 同一内容的纵向观测关系及有证据支持的图关系。

这些字段描述“内容是什么、来自哪里、何时被观察到”，不得偷偷表达它对未来任意问题的重要性。

### 每次请求动态计算的判断

- 与当前问题的语义相关性；
- Primary / Supplementary / Background / Unverified / Excluded 层级；
- 对当前任务的 Dynamic Importance；
- 对当前时间要求的 Query-relative Freshness；
- 对当前结论的 Evidence Quality；
- 最终展示顺序、是否进入主答案以及是否需要联网补证。

## 3. Query Frame

```text
QueryFrame
  question                 用户原问题
  task_families[]          一个或多个稳定任务族
  subjects[]               用户明确询问的主体
  topics[]                 主题约束
  temporal_expectation     最新 / 时间段 / 历史 / 无明确时间要求
  evidence_need            导航 / 新闻 / 趋势 / 解释 / 关系 / 核验
  requested_sources[]      用户指定来源（如有）
  web_permission           禁止 / 按需 / 明确要求
  ambiguity                歧义与低置信判断，不能静默覆盖
```

约束：

- Query Frame 是多信号结构，不允许用后出现的关键词覆盖前面的任务信息；
- 精确 Daily Item ID 和精确标题导航优先走确定性路径；
- “最近”“重要”“趋势”是不同约束，不得折叠成同一个 intent；
- 无法可靠判断时要保留歧义，交由有限的澄清或并行小检索解决。

## 4. Evidence Candidate 与分层

每个候选至少保留以下请求时字段：

```text
CandidateJudgment
  identity
  retrieval_channels[]
  semantic_relevance
  subject_match
  temporal_match
  relevance_tier
  importance_factors
  freshness_factors
  evidence_quality_factors
  exclusion_reasons[]
```

层级合同：

| 层级 | 含义 | 可否决定主答案 |
|---|---|---|
| Primary | 直接回答当前问题 | 可以 |
| Supplementary | 相关但次要、间接或适合作为补充 | 不单独决定 |
| Background | 用于解释历史、背景或上下文 | 不可以，也不能伪装成最新动态 |
| Unverified | 可能相关但证据不足或来源尚未通过 | 不可以，需补证 |
| Excluded | 不相关、重复、越界或质量不合格 | 不展示 |

同一条观测可以在不同 Query Frame 下进入不同层级，但在同一次请求中只能有一个最终层级。

## 5. 层内排序

只有同层候选可以相互比较。首版不提前冻结一个虚假的万能公式，而采用可解释的因子组：

- Dynamic Importance：影响范围、影响深度、主体显著性、事件新颖度、公共讨论价值；
- Query-relative Freshness：事件时间、发布时间、用户时间窗口、是否只是旧闻回流；
- Evidence Quality：一手来源、字段完整、跨来源佐证、是否直接支持当前结论；
- Diversity：防止同一事件、同一来源或同一主题重复占位。

热度快照可以作为 Dynamic Importance 的一个输入，但不能替代相关性，也不能跨层晋级。

## 6. 深模块接口

合同版本：`query_evidence_routing/1.0`。

现有外部 seam 保持为一个入口，避免调用方理解内部路由细节。正式方法名沿用代码中的 `EvidenceRetrievalGateway.retrieve`，不另造同义入口：

```text
EvidenceRetrievalGateway.retrieve(ResearchRequest) -> EvidenceBundleV2
```

`EvidenceBundleV2` 是影子阶段的新合同；旧 `EvidenceBundle` 暂时由兼容适配器读取 V2 的字段生成，调用方迁移完成后才删除。必填字段如下：

```text
EvidenceBundleV2
  schema_version = "query_evidence_routing/1.0"
  status
  primary_task_family
  supporting_task_families[]
  primary_records[]
  supplementary_records[]
  background_records[]
  unverified_records[]
  query_frame
  evidence_grade
  trace
```

`primary_task_family` 决定输出合同；`supporting_task_families` 只表达复合问题中的附加证据需求，不能覆盖主任务。所有记录列表必须存在，允许为空；一个证据身份在同一次请求中只能出现在一个层级。

召回通道、RRF、语义重排、图谱和联网搜索是该模块内部实现。调用方只需要理解分层结果、证据状态和错误语义。

### 6.1 两个不可合并的内部步骤

```text
assign_relevance_tier(QueryFrame, EvidenceCandidate) -> TierJudgment
rank_within_tier(QueryFrame, TierJudgment[]) -> RankedTier
```

`assign_relevance_tier` 只决定层级并返回理由、置信度和缺失信号；它不产生最终排名。`rank_within_tier` 只能排列已经属于同一层级的判断结果，没有修改、晋级或降级层级的权限。

因子缺失时必须保留 `unknown` 和诊断，不得默认为零后用乘法把候选清空。Diversity 是层内初排完成后的列表约束，用于限制同事件、同来源和同主题占位，不参与层级判断。

## 7. 路由边界

- 精确条目导航：结构化索引直接返回，不调用生成模型；
- 普通证据研究：关键词与向量并行召回，再做语义重排；
- 最新/重要新闻：在相关性分层后，使用动态重要性和问题相关新鲜度排序；
- 趋势：要求跨事件或跨来源的结构信号，单条重大新闻只能作为趋势候选；
- 时间线与关系：图谱提供纵向和横向关系证据，不与普通文本结果争夺同一个原始分数；
- 核验：以结论—证据关系为中心，相关近邻不能冒充直接证据；
- 联网搜索：用于补足时效、核验或证据缺口，不用于掩盖内部召回失败。

## 8. 小样验证合同

正式实现前先建立两个相互隔离的数据切片：

- 开发/校准集：12–20 条，允许实现者查看，用于检验接口、调试规则和校准排序；
- 冻结盲测集：来自不同日期，在实现和调参期间不可见，不少于 10 个 Query Frame，只有 Stage Gate 才揭封。

标签由产品裁决、语料事实和独立监管复核共同形成；每个争议项保留裁决理由，不允许由当前实现反向生成 gold。两组至少包含：

- 同一内容在两个不同问题中从 Supplementary 变为 Primary；
- 很新但无关的内容不得进入 Primary；
- 旧但必要的解释材料进入 Background；
- 高热度但弱相关内容不能跨层晋级；
- 一手来源与转载内容描述同一事件时正确去重并保留 provenance；
- “重要动态”和“安全机制变化”产生不同分层；
- 精确编号和标题导航保持确定性命中。

保护切片必须单独报告：精确导航、中文模糊表达、高热弱相关、旧闻冒充最新、实体别名和复合约束。评估器先用三份手写结果验证辨别力，必须满足 `正确结果 > 退化结果 > 错误结果`，再允许评价系统输出。

首轮评价分开报告，不再用一个 F1 代表整个系统：

- 候选召回：Recall@20；
- 语义排序：MRR、NDCG@5；
- 分层判断：Primary/Supplementary/Background 的混淆矩阵与关键错误清单；
- 用户结果：主答案相关率、背景冒充最新率、引用精确跳转率；
- 性能：P50/P95 延迟和每请求模型调用成本。

## 9. Stage Gate

只有同时满足以下条件，才允许替换正式链路：

1. 新链路在冻结小样上优于当前链路，而不是只展示自身绝对分数；
2. 很新但无关的内容进入 Primary 的数量不得增加；
3. 精确导航不得退化；
4. 至少覆盖中文模糊表达、实体别名和多约束问题；
5. 质量监管 Agent 已检查产品语义、完整用户流程、成本和可回滚性；
6. 不修改正式索引即可关闭新链路并恢复旧链路。

12–20 条开发样本只用于证明接口与方向，不得用于对外宣称整体质量提升。正式晋级结论必须来自冻结盲测集。

## 9.1 成本、停止与回滚合同

- 精确编号和精确标题导航：零模型调用；
- 确定性规则置信度足够时：零路由模型调用；只有歧义问题允许最多一次结构化路由调用；
- 初召回可扩大，但昂贵语义 rerank 的输入上限首版固定为 30 条；
- 证据不足时最多执行一次内部修正检索，不允许无限 Agent 循环；
- Graph 只进入关系、时间线和结构趋势路径；
- Web 只在用户明确要求、内部时效缺口或证据评级不足时启动；
- 新链路先以影子模式运行，由 `QUERY_EVIDENCE_ROUTING_V2` 功能开关控制，不写正式索引；
- 新链路异常、合同校验失败或超出整体请求硬超时时，自动回退旧链路并记录原因；
- 若盲测质量未优于基线、P95 延迟增幅超过 30%，或单请求付费模型调用数超过上述预算，停止晋级并回到合同或候选召回阶段；
- 回滚只需关闭功能开关，不删除数据、不重建索引。

## 9.2 旧语义迁移表

| 当前语义 | 处理方式 | 目标语义 |
|---|---|---|
| `intent="important_news"` | 转换 | Query Frame 中的 `evidence_need=news`、`importance_requested=true` 和时间约束，不再独占整个 intent |
| 固定 `_rank_important_news_candidates` 门和权重 | 影子期保留作基线，V2 不复用 | `assign_relevance_tier` 后按层调用 `rank_within_tier` |
| `news_tier=background` | 停止作为语料或 Prompt 的固定属性 | 当前请求中的 `relevance_tier=Background` |
| `records[]` | 兼容适配期只读聚合 | V2 明确的 Primary、Supplementary、Background、Unverified 列表 |
| 单数 `intent/task_mode` 覆盖 | 逐步替换 | 一个 `primary_task_family` 加零到多个 `supporting_task_families` |

旧链路只作为对照与回滚路径，不再成为新合同的定义来源。

## 10. 当前明确不做

- 不训练专用路由分类器；
- 不引入覆盖全项目的大型 RAG 框架；
- 不把所有问题都交给多步 Agent；
- 不用 Prompt 替代召回和证据分层；
- 不在没有对照小样的情况下重建全量索引。
