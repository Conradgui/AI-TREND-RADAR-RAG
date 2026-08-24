# Stage 9：任务 Prompt 与 Graph Evidence 接线

## 现状

- QueryPlan、EvidenceRetrievalGateway、task family、Prompt Registry 已存在并已接入聊天。
- 关系问题会声明 `graph_requirement=required`，但 Gateway 返回的仍主要是普通条目证据。
- Observation Graph 的聚合统计已激活，却没有稳定作为一条可引用 Evidence Record 进入普通 Agent 回答。
- 基础 Agent Prompt 仍鼓励自由组合旧工具，可能绕过任务契约和既有证据账本。

## 目标

1. Gateway 接受一个独立 Graph Evidence Provider。
2. timeline / relation_exploration 路由时，Provider 生成 Observation-first 图谱证据并加入 EvidenceBundle。
3. 图谱证据获得正常 evidence_id，可由答案使用 `[E#]` 引用。
4. Provider 失败时，required graph 请求返回明确 partial_error，不静默退化。
5. Prompt Registry 保持任务级稳定契约；基础 Agent Prompt 删除与它冲突的旧式自由编排指引。

## 不做

- 不新增第二套路由器。
- 不让 Prompt 自己决定图是否必需。
- 不把共同出现解释为因果。
- 不修改普通事实检索和联网搜索边界。

## Gate

- 单测证明关系问题含图谱 citation，普通问题不额外查询图。
- 图 Provider 故障时关系问题 fail closed。
- 真实 DeepSeek 关系问题显示 task family、图谱 evidence marker 和正确引用。
