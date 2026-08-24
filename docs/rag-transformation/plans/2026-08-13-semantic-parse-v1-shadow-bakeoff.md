# SemanticParseV1 影子对照计划

- 日期：2026-08-13
- 触发原因：Route Contract v2 一次性盲测未过 Gate
- 状态：监管 `CONDITIONAL`；阻断项已纳入合同与 Gate，待复审
- 生产接入：禁止

## 目标

用一个小而有辨别力的 12 条切片回答：结构化语义解析是否能实质修复未知主体、自然语言导航、复合任务、指代与保真 span，而不是只在已见措辞上变好。

## 本阶段产物

1. `SemanticParseV1` Schema：subjects、claims、locators、constraints、references、task_atoms、literal_spans、confidence、ambiguities。
2. DeepSeek structured-output 影子适配器；输入只有 Query 与允许公开的上下文，输出只有 Schema 数据。
3. L0 确定性覆盖层：ATR、日期/金额/数量、联网允许/禁止；其结果优先且不可被模型反转。
4. 从已揭盲数据选择的 12 条诊断切片及旧/新对照报告。

`SemanticParseV1` 明确禁止输出 route、answer mode、policy ID 或 prompt ID；L2 是唯一合同裁决者。

## 明确不做

- 不改生产 `analyze_query`、chat、retrieval、Prompt Registry、Neo4j、向量库和 UI。
- 不让模型生成最终答案。
- 不继续扩 `_KNOWN_TERMS` 或为 50 条校准 Query 写专用规则。
- 不用同一批校准成绩声称泛化。
- 不允许解析失败时静默回落为 E；必须返回结构化失败或进入消歧。

## 小样 Gate

- Parse Schema、parse 语义不变量、Route Schema、联网权限：100%。
- 路线 ≥10/12；A ≥3/4。
- 关键权限/ATR/日期/金额零漏失。
- 保真 span precision ≥80%、recall ≥80%、F1 ≥80%。
- 歧义 precision ≥80%、recall ≥80%。
- 对应旧实现至少净提升 4 条，且不牺牲已正确的安全权限。

## 冻结运行配置

- Provider：DeepSeek；model 固定为 `DEEPSEEK_MODEL` 在运行时解析出的具体值并写入报告。
- temperature：0；JSON object；max tokens：2400；timeout：45 秒；retry：0。最初 1200 token 运行因 11 条残缺对象 + 1 条截断判为 `infra-invalid`，永久保留但不计质量。
- 扩容后先运行 3 条跨路线 canary；必须 3/3 parse Schema/semantic valid 才可运行 12 条，否则停止。
- System Prompt、Schema、12 条 query-only 切片和预期 Gold 在调用前记录 SHA-256。
- 报告必须记录单条和总体延迟、成功/超时/失败率、输入/输出 token 与可得的 API 成本估算。
- 12 条是从已解封数据得到的诊断校准切片，不称盲测；但必须在实现前锁定 query-only 与 Gold，避免边写边改题。

没过 Gate：停止模型方向，重新审视语义合同或标注口径；不扩到 50 条。

通过 Gate：扩到已揭盲 50 条校准集；达到正式 Gate 后才创建另一套全新 sealed blind。

## Canary 失败后的 Lean 转向 Gate

Rich SemanticParseV1 已因 2/3 可用、平均 13.501 秒而停止。下一步只允许：

### Fast Path 离线 Gate

- 应命中 6 条：A 自然完整标题、A 日期+来源+标题、A 标题片段消歧、A 左右上下文、B 禁网近期趋势、D 禁网证据核验。
- 必须拒绝并返回 fallback 的 3 条：B+关系复合、B+核验复合、D+上下文反证复合。
- 6 条命中路线/answer mode/权限/引用必须 100%；3 条负例 fallback 100%；整体平均延迟 <10ms。

### Lean Task Atom Canary

- 输出 Schema：`docs/rag-transformation/specs/lean-task-atom-v1.schema.json`。
- 输出只能含 route-neutral main/supporting Task Atom、references、confidence、ambiguities；不得出现五路标签、answer mode 或 policy。
- 固定 3 条复合 Query；3/3 Schema valid、3/3 Task Atom 语义正确、3/3 L2 Route Contract 投影正确。
- 平均延迟 ≤8 秒、最大延迟 ≤12 秒、平均 completion ≤600 token；记录总 token，成本无冻结价格时仍标未知。
- 任一项不满足即停止，不得通过修改 Gate 迁就结果。
