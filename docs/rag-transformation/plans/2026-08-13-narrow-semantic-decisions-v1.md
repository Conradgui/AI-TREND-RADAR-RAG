# Narrow Semantic Decisions v1 影子合同计划

- 日期：2026-08-13
- 状态：已完成并冻结；最终 Stage Gate `APPROVE`
- 正式流量影响：无
- API 调用：禁止

## 背景

Route Contract v2 的 50 条封存盲测显示旧理解内核泛化失败；Rich SemanticParse 与 Lean Task Atom 两个模型 fallback 又分别因成本、结构可靠性和产品语义偏差未过 Gate。继续修改同一个 Prompt 会形成样本追逐，且不能关闭默认 E 的产品风险。

## 决策

L1 不再生成完整任务、路线或策略，只给出五个相互正交的语义判断：

1. `item_lookup`：用户是否要求定位一条具体记录；
2. `recent_update_set`：用户是否要求近期新闻/动态集合；
3. `cross_time_or_entity_structure`：用户是否要求演变、时间线、关系或结构；
4. `truth_assessable_claim`：用户是否要求核验可判真伪主张；
5. `explanation_or_comparison`：用户是否要求解释、比较、建议或深挖。

每个判断只能输出 `present / absent / uncertain` 和来自原 Query 的逐字证据片段。禁止输出 A–E、route、answer mode、policy、Prompt ID 或最终答案。合同不包含无裁决作用的置信度字段。

真实 Query 由调用方单独传入校验器，L1 不得回传或替换 Query。L1 另提供必须逐字保留的 `protected_spans`，以及单条定位精度 `none / partial / exact`。已解析上下文引用只能是公开上下文中真实存在的 bare ATR ID，并作为独立引用合同贯穿 L2 投影。

L2 确定性规则：

- 存在未解析指代，或关键判断为 `uncertain`：`clarification_required`；
- 没有任何 `present`：`clarification_required`，禁止默认 E；
- 多个独立交付目标按其首个证据片段在 Query 中的位置排序；第一个为主路线，其余为辅助路线；
- 当“解释/比较”证据包裹并重叠于更具体的 A/B/C/D 交付时，它只代表表达方式，不额外生成 E 路线；
- 同起点冲突且无法确定主次：`clarification_required`；
- L2 才将五个语义维度映射为 A–E 产品路线。

## 本阶段交付

- route-neutral JSON Schema；
- 12 条离线校准/退化样本；
- 语义校验与 L2 影子投影；
- TDD 证明：非法 span、越权 route 字段、空判断、冲突和未解析指代都不能静默进入 E。

## Gate

- 12/12 预期投影正确；
- 所有退化 mutation 被拒绝或进入 clarification；
- 不调用模型 API；
- 不修改正式 query understanding、检索、Prompt Registry、聊天或 Web UI。

## 最终结论

- 独立质量监管最终结论：`APPROVE`；
- 监管复现：`114 passed + 28 subtests`，`git diff --check` 通过；
- 冻结清单：`docs/rag-transformation/evals/narrow-semantic-decisions-v1-shadow-freeze-manifest-2026-08-13.json`；
- 下一阶段必须重新过 Gate，目标只能是验证 L0→L1 对未见 Query 的真实理解能力，不能把本阶段 12/12 当作泛化成绩。
