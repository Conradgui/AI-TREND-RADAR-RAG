# RAG 策略 Changelog

本文件只记录策略、领域合同和架构决策变化，不代替代码提交记录或执行日志。

## [strategy/1.1-agentic-rag-boundary] - 2026-08-28

### Changed

- 将 Agentic RAG 明确为按任务升级的受控路径，而不是所有 Query 的默认循环。
- 确定性 Workflow 继续承担导航、单次检索和固定趋势候选；复杂分解、动态选源、证据缺口才进入短计划与最多一次纠偏。
- 分离当前请求状态、可核验长期关系反馈和语料知识；禁止保存隐藏思维链或把模型猜测直接晋级为事实。
- 增加 Agent 进入正确率、工具选择、有效步骤、停止正确率、预算与恢复质量的分层评估。

### Evidence Boundary

- 当前已有确定性路由、工具 trace、预算和证据合同；完整持久化 Agent 工作流仍为 `Not Claimed`。
- 外部 Agent/RAG 面试资料用于补齐问题框架，官方 Microsoft/LangGraph 文档用于边界核对；最终状态只以项目代码、测试和运行证据为准。

## [query-understanding/narrow-semantic-decisions-v1-shadow] - 2026-08-13

### Added

- 建立五个 route-neutral 窄语义判断：单条定位、近期动态集合、跨时间/实体结构、可核验主张、解释/比较。
- 每个判断只携带 `present/absent/uncertain` 与 Query 逐字证据；L2 仍是唯一 A–E 裁决者。
- 增加 fail-closed：未解析引用、不确定判断、无明确交付与无法区分主次的冲突一律进入 clarification，禁止默认 E。

### Simplified

- L1 不得自报 Query；真实 Query 由调用方传给校验器。
- 删除不参与裁决的 confidence 字段。
- 解释/比较仅包裹更具体交付时作为表达方式，不额外制造 E 路线。
- 已解析引用必须是公开上下文中存在的 bare ATR ID，并贯穿 L2 投影。

### Evidence Boundary

- 12 条是可见校准与退化样本，不构成泛化成绩。
- 离线及相关回归 84 项通过；仍未调用 API，未接入正式检索、Prompt Registry、聊天或 Web UI。

### Shadow End-to-End Projection

- 已贯通 L0 Query → L1 fixture → L2 → 完整 Route Contract v2 / clarification。
- 权限、ATR 引用、supporting contracts 和 fail-closed clarification 已有故障注入回归。
- 相关回归 `97 passed + 28 subtests`；L0→L1 泛化能力仍未验证。

### Projection Hardening

- 增加 L1 `protected_spans` 与 `item_locator_precision`，关闭标题/主题保真和模糊导航误判。
- 四种禁网表达在权限、Intent Signals 与 Protected Terms 三处保持一致。
- 补强后相关回归 `104 passed + 28 subtests`；正式链仍零接入。

## [query-understanding/fast-path-plus-lean-fallback-canary] - 2026-08-13

### Validated

- Deterministic Fast Path 离线 Gate 通过：6 条明确请求合同全对，3 条复合请求均正确要求 fallback，9000 次调用平均约 0.0103ms。
- 快速路径不依赖实体白名单，继续作为候选主路径保留。

### Invalidated

- Rich `SemanticParseV1` 因结构可靠性与延迟未过 Gate，已停止。
- Lean Task Atom 首轮三条 Canary 的 0/3 被更正为 `INFRA-INVALID`：使用了只保证合法 JSON 的 `json_object`，且未关闭 DeepSeek V4 默认思考模式，不能当作 Lean 架构或模型语义能力证据。

### Gate

- 在质量监管批准前，不允许继续调用或扩大样本。
- 若批准，只能对固定三条执行一次 `/beta` strict function calling + non-thinking 替代 Canary；失败即停止模型 fallback，仍不得接入生产。

### Strict Canary Result

- 替代 Canary 已按批准边界完成并失败：Schema + semantic 1/3、完整投影 0/3；平均延迟 2.478 秒、最大 2.659 秒。
- 性能改善成立，但 strict tool arguments 仍可能非法 JSON，且开放式 action 与引用身份仍不可靠。
- Lean Task Atom 开放式 fallback 停止；下一候选是 Deterministic Fast Path + 窄语义判断 + L2 唯一裁决 + clarification fail-closed。

## [route-contract/2.0-shadow-freeze] - 2026-08-13

### Added

- 增加上下文引用合同：公开会话上下文中的 ATR 条目可以解析“它/这条新闻”，无上下文时必须显式报告歧义。
- 增加可执行 supporting contracts，使 A 路由的解释、比较等辅助任务拥有独立 rewrite/retrieval/prompt/output/budget 合同。
- 增加严格独立片段保真评分、通用 query-only 预测生成器、确定性 sealed Gold 评分器和人工标注指南。

### Gate

- 独立质量监管最终 `APPROVE`：允许冻结影子资产并创建全新封存盲测。
- 仍禁止接入正式聊天、检索、Prompt Registry、DeepSeek 或 Web UI。
- 开发集及已解封挑战集只作为校准证据，不再用于声称泛化质量。

## [route-contract/2.0-shadow-understander] - 2026-08-13

### Changed

- 将影子理解器拆成确定性的 `QuerySignals` 抽取与 `RouteDecision` 裁决两个内部 seam，公开 Route Contract 接口保持不变。
- 明确 `protected_terms` 只保留会改变对象、范围或主张的字面片段；普通任务词由 Intent Signals、route、answer mode 和权限字段表达，禁止整句 Query 冒充保护词。
- A 路由改为“导航动作 + 可定位对象”判据，避免“找到最近动态/找到证据”被误判成单条导航。
- B/C 与 D/E 改为按用户成功标准裁决：短期重要新闻集合属于 B，跨时间/关系结构属于 C；可判真伪主张属于 D，价值判断与解释比较属于 E。

### Evidence Boundary

- 已解封挑战集仅用于修复后的校准诊断，不再称为盲测；新的真实泛化质量仍需独立未见样本验证。
- 本阶段仍为影子链路，尚未接入正式聊天、检索、Prompt Registry 或 Web UI。

## [route-contract/2.0-shadow-assets] - 2026-08-13

### Added

- 冻结 Route Contract v2 JSON Schema 和用于人工标注的 Expected Projection Schema。
- 建立 A–E 各 5 条、共 25 条的 route-balanced 开发小样。
- 增加应用级跨字段校验：主路线不得重复为辅助路线；保真词不得从原始 Query 消失。
- 增加退化合同测试：A 携带 Prompt、B 使用 C answer mode、policy ID 错配、主辅路线重复和原问题保真丢失必须失败。

### Evidence Boundary

- 当前资产可以评价路线、answer mode、合同 ID、联网权限和保真词；尚不能评价实体、主题、时间与来源约束的抽取质量。
- 独立质量监管 Stage Gate 结论为 `APPROVE`，仅允许进入不接正式检索链的影子理解器实现。

## [strategy/1.0] - 2026-08-13

### Added

- 建立五类任务路线：Item Navigation、Trend Discovery、Temporal Relation Exploration、Claim Verification、Evidence Research。
- 建立“输入保真 → 意图信号 → 单次路由 → Query Rewrite → Agentic GraphRAG → 相关性分层 → 层内排序 → Prompt Package → Answer Envelope → Renderer”的总—分—总体系。
- 新增八份模块策略和可点击 Mermaid 导航。
- 明确 Query Rewrite 与 Prompt Registry 必须消费同一个 Route Contract。
- 明确 JSON 是机器合同，Markdown/UI 是确定性用户呈现。
- 明确 ATR ID、Evidence ID、本地 deep link 和外部 URL 的贯穿关系。
- 将 Top K 拆为 channel、graph、fusion、rerank、context 和 display 六类阶段预算。

### Changed

- 将原有单值 intent 方向升级为可共存 Intent Signals + 一个主任务/多个辅助任务。
- 将 Timeline 与 Relation Exploration 收敛为同一 C 路由入口，但保留独立 answer mode 与输出结构。
- 全局“重要新闻”正式改为请求时相关性层级和层内动态重要性判断。
- 澄清 A 路由旁路生成模型，由服务端确定性生成 NavigationAnswer。
- A 使用 `answer_builder_contract_id` 而非 Prompt 合同；导航命中须先准入 Evidence Ledger。
- 澄清 Evidence Candidate 只有通过分层和准入后才成为 Ledger 中可引用的 Evidence Record。
- 澄清 Graph 结构、Web 候选与文本 RRF 的汇合边界；上游值仅作为 Dynamic Importance 的弱输入。

### Confirmed Product Boundary

- B/C 趋势边界已确认：B 回答“最近发生了什么、什么值得关注”；C 回答“如何演变、彼此关系和跨时间/跨实体结构”。“最近有什么趋势”默认进入 B。

### Not Implemented

- 尚未实现 Route Contract v2、Query Variant Set、EvidenceBundleV2、Answer Schema 或 Renderer。
- 尚未修改正式 QueryPlan、检索链、Prompt Registry、DeepSeek 调用和 Web UI。
- Canary Top K 仅为调研后的启动范围，尚未通过项目小样校准。
