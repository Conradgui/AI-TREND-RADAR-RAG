# AI Trend Radar 总—分—总端到端策略

## 1. 一句话定义

一份 Route Contract 贯穿输入改写、五路检索、证据分层、Prompt 封装、结构化生成和用户渲染；系统只分类一次，所有后续模块都消费同一决定。

## 2. 总—分—总

### 第一个“总”：统一理解

用户只提交原始 Query。系统先保真记录，再提取多个 Intent Signal，最终生成：

- 一个 `primary_task_family`；
- 零到多个 `supporting_task_families`；
- 实体、主题、时间、来源、证据需求与联网权限；
- 对应的 rewrite、retrieval、prompt、output 和 budget 合同 ID。

### “分”：五类纵向任务路线

| 路由 | 稳定名称 | 用户成功标准 | 典型回答模式 |
|---|---|---|---|
| A | `item_navigation` | 找到唯一条目并可精确跳转 | 条目卡片；通常不调用 LLM |
| B | `trend_discovery` | 回答“最近发生了什么、什么值得关注” | 动态榜 / 趋势簇 |
| C | `temporal_relation_exploration` | 回答“如何演变、彼此有什么关系、形成了什么结构” | timeline / relation / longitudinal / cross-sectional |
| D | `claim_verification` | 判断主张被支持、反驳或证据不足 | verdict + 判据—证据矩阵 |
| E | `evidence_research` | 解释、比较或深挖一个问题 | 结论—证据型研究回答 |

复合问题不新增第六类。例如“OpenAI 与 Anthropic 最近的关系变化是否说明竞争升级”可用 C 为主、D 为辅。

### 第二个“总”：统一回答

五路都产出同一外层 `AnswerEnvelope`，路由专属字段由 Schema 分支约束。A 由服务端确定性生成 `NavigationAnswer`，不默认经过 Agent；B–E 才经过 Prompt Package 和生成模型。应用层统一校验结构、Evidence ID、ATR ID 与业务不变量，再由 Answer Renderer 生成 Markdown 或 UI 卡片。

## 3. 端到端接口链

```text
understand(original_query, context) -> RouteContract
rewrite(RouteContract) -> QueryVariantSet
retrieve(RouteContract, QueryVariantSet) -> ChannelCandidateSets
rank_and_admit(RouteContract, ChannelCandidateSets) -> EvidenceBundleV2 + EvidenceLedger
A: admit_navigation_match(RouteContract, Match) -> EvidenceLedger
A: build_navigation_answer(RouteContract, EvidenceLedger, answer_builder_contract_id) -> AnswerEnvelope
B-E: compile(RouteContract, EvidenceBundleV2) -> PromptPackage
B-E: generate(PromptPackage) -> RawStructuredOutput
validate(RawStructuredOutput, EvidenceLedger) -> AnswerEnvelope
render(AnswerEnvelope, Surface) -> Markdown | UIModel
```

每个接口都是阶段门和测试 seam。内部技术可以替换，但调用方不需要知道底层使用规则、模型、RRF、cross-encoder 或 Cypher。

## 4. 贯穿全链的身份与链接

- ATR `daily_item_id`：永久公开身份；
- `content_id/event_group`：内部跨日关联身份；
- `[E1]`：仅本请求中的紧凑证据编号；
- `local_url`：精确到日报中的 ATR 条目；
- `external_url`：原始信息源页面。

召回结果首先只是 `Evidence Candidate`。只有经过身份去重、语义重排、相关性分层和证据准入的 Primary、Supplementary 与合格 Background 才成为 `Evidence Record`，进入 Ledger 并获得请求内 E 编号。Unverified 和 Excluded 只进入 trace/诊断，不能被 Claim 引用。后续 Agent 只能引用 Ledger 中的 Evidence ID；标题、日期和链接由服务端账本注入，不能信任模型自行生成。

## 5. 成本分层

- A 路由和高置信简单问题：零路由模型调用；
- A 路由使用版本化 `answer_builder_contract_id`，不携带 Prompt 合同；
- 复杂/歧义 Query：最多一次结构化路由调用；
- 子问题最多 3 个；
- 证据不足最多一次内部 corrective retrieval；
- Web 只在明确要求、时效缺口或证据不足时进入；
- Graph 只在证据形状需要关系、时间或全局结构时进入；
- Answer JSON 校验失败最多一次格式修复，不重新发明事实。

## 6. 迁移顺序

1. Route Contract 与 25 条 route-balanced 小样；
2. 输入侧影子 rewrite；
3. 多通道候选与语义重排；
4. 相关性分层和层内排序；
5. Prompt Package 与 Answer Schema；
6. Renderer 与 deep link；
7. 一次纠错和受控 Web；
8. 独立盲测通过后才切正式流量。

## 7. 共同停止条件

- 精确导航退化；
- 新但无关或高热弱相关进入 Primary 增加；
- Prompt 与 rewrite 使用不同 route 版本；
- Answer 引用了账本外 Evidence ID；
- P95 延迟增幅超过合同预算；
- 无法通过功能开关回滚；
- 只凭开发集对外宣称整体质量提升。

## 8. 来源与适配原则

本策略借鉴 Azure Agentic Retrieval 的查询规划和并行子查询、Hybrid + RRF + Semantic Ranker 的多阶段检索、Microsoft GraphRAG 的 Local/Global/DRIFT 边界，以及 JSON Schema 的机器合同；不直接引入一个覆盖全项目的新框架。详见[研究报告](../research/2026-08-13-end-to-end-query-routing-strategy-research.md)。
