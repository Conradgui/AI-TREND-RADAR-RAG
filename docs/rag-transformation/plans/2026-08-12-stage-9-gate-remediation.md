# Stage 9 Gate 修复计划：确定性导航与成对关系证据

日期：2026-08-12
状态：完成；Stage Gate 通过

## 为什么重新打开 Gate

独立质量审查确认了两个会影响用户结果的缺口：

1. 已经精确命中唯一条目的问题仍会进入 LLM，增加延迟、费用和改写风险。
2. “OpenAI 与 Apple 有什么关联”只返回两个实体各自的聚合摘要，没有给出两者共享观察、共享内容或共享分类的成对证据。

审查提出的“必须新增 PromptEnvelope 类”不纳入本轮。当前任务规则、证据约束和失败策略已经进入实际 Prompt；仅替换接口形状不会改善用户结果。

## 已确认的测试接缝

- `build_chat_response()`：用户输入精确编号或标题时，返回可导航条目且模型调用数为 0。
- `EvidenceRetrievalGateway.retrieve()`：关系问题返回显式的 `graph_relation` Evidence Record，而不是把两份单体摘要当作关系证据。

## 两个纵向切片

### Slice A：确定性条目导航

1. 先写失败测试：模型和 composer 均为不可调用对象。
2. 精确命中后直接生成带本地链接的回答、引用、证据映射和执行 trace。
3. 只运行 chat service 定向测试；通过后再进入 Slice B。

### Slice B：成对关系证据

1. 先写失败测试：OpenAI/Apple 必须产生一条成对关系证据。
2. 从 Observation-first 图谱读取直接共现、共享 Content 和共享 Category；不把共现表述为因果。
3. 关系任务只把 `graph_relation` 作为必需证据；单实体时间线继续要求 `graph_reasoning`。
4. 运行 graph service、gateway、chat service 定向测试。

## 非目标

- 不重写 Query Understanding。
- 不替换现有 Prompt Registry。
- 不全量重建向量索引。
- 不修改已通过真实页面验证的筛选与精确跳转 UI。

## Stage Gate

- 自动化：两个新行为测试先红后绿，相关回归通过。
- 真实服务：精确条目请求 `model_turns=0`；关系请求含 `graph-relation/...` 且证据完整性无缺失。
- 独立质量监管：核对产品路径、证据语义和计划边界后再关闭 Gate。

## 执行结果

- Slice A：完成。精确 ATR 编号在真实服务上返回 `deterministic_navigation`，`model_turns=0`、`agent_tool_calls=0`。
- Slice B：完成。真实 OpenAI–Apple 请求返回 `graph-relation/openai/apple`，关系证据为必需 E5，`missing=[]`。
- 定向新测试：3/3 先红后绿。
- 相关回归：80/80 通过；`git diff --check` 通过。
- 独立质量监管：APPROVE；P0=0，P1=0；独立复跑 85/85 通过。
