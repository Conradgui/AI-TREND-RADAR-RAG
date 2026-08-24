# Ordered Query Frame v3 架构替换计划

- 日期：2026-08-16
- 状态：三条真实回归 Canary PASS；待独立 Canary Gate
- 前任候选：dimensions-only L1 v2（STOP）
- 正式流量：禁止

## 为什么不再修 v2

v2 的五个独立维度回答“Query 里是否出现某类语义”，却没有稳定回答“用户明确要求系统交付哪些动作”。因此相对时间会误触发 B、关系词会误触发 C，多任务 supporting 也会失真。与此同时，Query Facts 被迫用正则判断标题完整度、联网语气和任意主题词，职责超出确定性解析能力。

这不是继续加关键词或 few-shot 能可靠解决的问题。v3 改变中间表示，不沿用五布尔维度。

## 核心产品原子：有序交付动作

模型不再输出五个真假开关，而输出用户明确要求完成的交付列表，顺序与 Query 一致：

```text
deliveries:
  - task_family
  - exact evidence spans
  - requested_output_form
  - locator_kind（只在 A 使用；其余为 none）

protected_spans
web_permission + evidence spans
unresolved_reference_spans
```

关键区别：

- “过去三个月”只是时间约束，不自动成为 trend delivery；
- “多跳关系问答”只是比较对象的场景，不自动成为 C；
- 只有用户明确要求“汇总动态”才产生 B，明确要求“梳理演变/关系”才产生 C；
- primary 是第一项交付，后续不同 task family 才是 supporting；
- delivery 是独立路由的产品任务，不是回答中的每个小节；同一 task family 的多个小节合并为一个 delivery，并选能覆盖其余小节的更丰富 output form（例如 `trend_clusters` 包含代表性重要新闻）；
- 普通礼貌词或“解释一下”的措辞包装不得成为独立 delivery。

`locator_kind` 只描述 Query 中可观察到的定位方式：`atr_id`、
`full_title`、`title_fragment`、`descriptive` 或 `none`。模型不直接判断
`exact/partial`；该结果由 L2 根据 locator kind 映射。

`requested_output_form` 位于每个 delivery 内部，不是脱离任务类型的顶层值。
L2 必须校验它是否属于该 task family 的合法输出形式，再映射到既有
`answer_mode`。这样不会再生成 `C + explanation` 或 `E + relation` 这类非法组合。

## 稳定接口链

```text
Query + Public Context
  -> Deterministic Query Facts
  -> OrderedSemanticFrameV3
  -> RouteContractV2
  -> QueryRewritePlan（本阶段不实现）
  -> RAG
  -> Prompt Package
```

本阶段只实现到 `RouteContractV2`。`standalone_query`、多检索 Query 和
改写保真校验属于独立 `QueryRewritePlan`，必须在 Frame 通过新的 blind 后再实现。
分类和改写不得共享一个输出合同，以便未来独立替换改写策略而不破坏路由接口。

## 职责边界

### 确定性预解析

- 从 Query 提取 ATR ID、书名号标题、引号主张和时间表达；
- 仅当公开 context 明确把左/右映射到 ATR ID 时生成 reference map；
- 不猜标题完整度、不猜普通概念代词、不猜联网语气。

### 单次语义 Query Frame

DeepSeek strict tool 在一次调用中只完成：

- 交付动作分类与顺序；
- 每项交付的输出形式和可观察 locator kind；
- 联网语义区分 forbidden / on_demand / explicit；
- Query-only protected spans；
- 对普通概念代词判断是否 unresolved。

不输出 standalone query、检索策略、Prompt ID、预算、回答内容或虚构 ATR。

### 确定性 L2

- 按 deliveries 顺序生成 primary / supporting；
- 合并重复 task family；
- A 必须拥有合法 supporting answer-builder contract，不再发生 `KeyError`；
- 从 primary + answer_mode 选择既有 route policy；
- 输出完整、可通过 Route Contract v2 Schema 的合同。

在调用真实模型前，先修复 Route Contract 对 supporting A 的表达：A 使用
`answer_builder_contract_id` 而不是 Prompt ID。测试不仅要求“不抛异常”，还必须
要求最终完整合同通过 Schema。

## 为什么暂不引入通用 Router 框架

当前失败点是本项目特有的 A–E 产品任务合同和权限/引用语义，不是缺少工作流编排器。LangChain/LlamaIndex 的 Router 可以执行分类结果，但不会替我们定义正确标签、主次交付和保真规则。此时增加框架只会增加依赖和调试面，不解决根因。v3 继续使用 JSON Schema + strict tool；等合同通过不可见 Gate 后，再评估是否需要框架承载运行时编排。

## 最小 TDD 与成本控制

### Slice 1：离线合同

先写失败测试，只覆盖六组最小对照；每组只改变一个语义变量，避免针对单句加规则：

1. supporting A：`E -> A` 与 `A -> E` 都能形成合法完整合同；
2. locator：`《完整标题》` 与“标题里包含 X 的那条”分别映射 full title / fragment；
3. B/C：相同实体和时间，只改变“有哪些动态 / 如何演变”；时间本身不新增 B；
4. Web：同一问题分别使用“不要联网 / 必要时可联网 / 请联网查”；
5. reference：`解释这个`、`这个说法：<后置主张>`、公开 context 明确绑定三组对照；
6. protected spans：只改变礼貌词和句式，内容约束集合保持稳定，不使用词语黑名单充当成功标准。

### Slice 2：三条真实 Canary

只调用三条已解封回归 Query（原 blind-014、008、010）：supporting A、限定式联网、后置主张。完整 Query Frame 3/3、均一次合法输出、平均 ≤8 秒、最大 ≤12 秒才继续。它们只证明旧缺陷已修，不作为泛化证据。

### Slice 3：已解封 15 条校准

最多运行一次，作为 v3 调试证据，不再称 blind；达到：

- 主路线 ≥85%；
- 每类 ≥80%；
- 联网权限 100%；
- protected micro-F1 ≥85%；
- clarification P/R ≥80%；
- ordered deliveries 与完整投影均 ≥85%；
- 无异常或默认路线。

任一失败即停止，不围绕单个实体加词表。

## 新 Blind 的测试质量门

v3 只有通过已解封校准才允许冻结。新 Blind 在预测前增加双重标签 Gate：

1. 出题 Agent 生成 query-only 与 Gold；
2. 第二个隔离标注 Agent 在不知道实现输出的情况下复核；
3. schema validator 必须拒绝非法状态、不可表达 supporting、context 文本冒充 Query protected span；
4. 分歧在封存前解决并记录，不由主线看到内容；
5. 预测封存后才解封评分。

旧 15 条永远不再作为 blind。

## Stage Gate 停止规则

- v3 不修改正式 chat、检索、Prompt Registry、Web UI；
- v3 不实现 QueryRewritePlan 或 standalone query；
- 不重跑 v2 原 Blind 并包装成新结果；
- Canary 前只做离线实现与测试；
- 每个 Gate 主线给出证据，独立监管检查代码架构与用户成功路径；
- 新 Blind 未通过前不得接正式流量。

## 独立监管 Revision 1

首次架构 Gate 结论为 `REVISE`：有序 delivery 命中了 v2 根因，但原计划仍将
语义理解、引用、保真、回答形式和 Query 改写塞入一次 strict 输出，接近 v1 的
职责过载。本次修订已删除 `standalone_query`、将 output form 下沉到 delivery、
改用可观察 locator kind、先修 supporting A 合同，并把六个单例改为六组最小对照。

## 二次架构 Gate

独立监管结论：`GO`。仅授权实现 `OrderedSemanticFrameV3 -> RouteContractV2`
的 Slice 1 离线合同；尚未授权真实模型 Canary。脚本化 Frame 只能证明 Schema、
装配和产品不变量，不能被描述为模型语义能力。

## Slice 1 实现 Gate

独立监管结论：`REVISE`，暂不授权模型 adapter。阻断项是：空/歧义任务无法
fail closed、supporting A 丢失 locator 与消歧语义、Schema 未表达交叉字段约束、
以及原后置主张 Canary 的单引号与绝对日期未被真实语法测试。修订必须仍留在
离线合同内，不借机增加 Query 改写或检索逻辑。
