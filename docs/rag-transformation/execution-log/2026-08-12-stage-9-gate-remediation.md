# Stage 9 Gate 修复执行记录

日期：2026-08-12
状态：完成；Stage Gate 通过

## Slice A：确定性条目导航

失败测试证明：即使 Retrieval Gateway 已把 `ATR-20260805-99E550` 识别为精确条目，`build_chat_response()` 仍会进入 `direct_composer` 并调用模型。

最小修复：在 Gateway 返回 `item_navigation + ready + records` 后，直接通过现有 `EvidenceLedger` 和 `build_evidence_presentation()` 生成响应，不进入联网决策、工具规划或模型生成。

真实服务结果：

- task family：`item_navigation`
- execution path：`deterministic_navigation`
- model turns：0
- agent tool calls：0
- citation：`ATR-20260805-99E550`
- 站内地址：`#2026-08-05/ai-topic-radar/item/ATR-20260805-99E550`
- evidence integrity：valid，missing=[]

产品意义：用户查明确条目时得到导航答案，不再为确定性数据库结果支付 LLM 延迟与费用，也不会被模型改写成不确定叙述。

## Slice B：成对 GraphRAG 关系证据

失败测试证明：多实体关系只产生 `graph-reasoning/openai` 与 `graph-reasoning/apple` 两份单体聚合，无法回答“二者之间是什么关系”。

最小修复：基于 `Entity -> Observation -> Content/Category` 增加成对查询，分别返回：

- 同一 Observation 被两实体标记的直接共现数；
- 两实体观察指向同一稳定 Content 的数量；
- 两实体观察共享的 Category 及名称；
- 最多 8 条直接共现样例。

新 Evidence Record 为 `graph_relation`；关系任务存在该证据时，只要求最终答案必须使用成对证据，单实体时间线仍要求 `graph_reasoning`。证据摘要固定声明“共现或共享上下文不能单独证明因果”。

真实 DeepSeek 结果：

- task family：`relation_exploration`
- graph trace：2 entities / 1 pair relation / 109 observations
- OpenAI–Apple：0 条直接共现、0 个共享稳定内容、1 个共享分类
- 最终可见 citation：`graph-relation/openai/apple`（E5）
- required evidence：E5
- missing required evidence：[]
- evidence integrity：valid

模型据此把结论限定为“同一争议时段的并列曝光”，没有把共享分类夸大为持续互动或因果。

## 测试证据

- 新行为测试：3/3 先红后绿。
- Graph service + Retrieval Gateway + Chat service：48/48 通过。
- Graph planner + Prompt Registry + Server chat/stream + Evidence Ledger/Presentation：32/32 通过。
- 合计相关回归：80/80 通过。
- `git diff --check`：通过。

## 变更边界

- 未重建或删除 Neo4j、ChromaDB 数据卷。
- 未重建向量索引。
- 只滚动替换 app 容器以加载新 Python 代码。
- 未修改 Stage 10 已通过的时间/来源/分类筛选与精确跳转 UI。
- 未新增纯形式的 PromptEnvelope 抽象。

## 独立质量监管结论

结论：**APPROVE**。

- P0：0；P1：0。
- 独立复跑相关测试：85/85 通过。
- 确认正式 `/chat` 与 `/chat/stream` 均使用 Retrieval Gateway。
- 确认确定性导航保留 E1、ATR 编号和站内深链，且模型/工具调用均为 0。
- 确认关系证据来自共享 Observation、Content、Category，并通过 Prompt 与证据摘要双重限制避免把共现写成因果。

P2：可在后续评估阶段补充更多零共现、三实体组合和真实图数据回归样本，不阻塞本阶段。

## Gate 判定

Stage 9 Gate：**通过**。
