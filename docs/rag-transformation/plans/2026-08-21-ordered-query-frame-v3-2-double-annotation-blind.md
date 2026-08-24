# Ordered Query Frame v3.2 双重标注 Blind 计划

- 日期：2026-08-21
- 主控：GPT-5.6 Sol / High
- 工具实现：GPT-5.6 Luna / Max（仅有界代码，不裁决产品语义）
- 目标：验证 v3.2 是否能泛化到未参与 Prompt 调整的新 Query
- 证据边界：只评估 Query Frame / Route Contract，不评估检索、GraphRAG 或最终回答质量

## 1. 为什么现在做 Blind

v3.2 已在 7 条解封校准样本上通过路由门槛，但这些样本参与过 Prompt 修正，不能证明泛化。
下一步必须使用全新 Query，并在 DeepSeek 运行前固定 Query、双份独立标注、最终 Gold、Prompt、
Schema、Runner 和 Scorer 的哈希。Blind 结果不允许反向修改本批 Gold。

## 2. 最小而充分的测试构成

- 公开 query-only 文件只包含 `case_id/query/conversation_context`，不得包含 family、web、
  clarification、compound 或 contrast 等答案标签；
- 20 条 Query，最终裁决 Gold 中 A–E 五个主任务族各 4 条；
- 至少 5 组最小对照，重点覆盖 B/C、D/E、A/E、timeline/longitudinal、resolved/clarification；
- 至少 6 条复合交付，验证顺序与 supporting delivery；
- 至少 4 条 clarification，并有对应的 resolved 负例；
- `explicit` 与 `forbidden` 联网权限各至少 4 条，其余为 `on_demand`；
- 覆盖 ATR ID、完整标题、标题片段、日期范围、金额/数字、指定来源、否定限定词与跨轮指代；
- 不复用开发集、v3.1 Blind、v3.2 校准集中的实体—措辞组合。

20 条足以让每个主任务族进入现有 `>=3` 的分路线 Gate，同时避免在合同仍可能失败时花费 50 条
调用。若通过，再扩大样本；若失败，本批立即解封为诊断资产，不重复刷分。

## 3. 双重标注与裁决

1. Query 设计者只生成 query-only 文件，不读取现有实现预测。
2. Annotator A 与 Annotator B 独立读取 Query、Schema 和标注指南，不读取对方结果。
3. 两份标注必须分别保存，不得由后一个覆盖前一个。
4. 在任何 Provider 调用前，Adjudicator 读取 Query 与两份标注，只裁决分歧，生成最终 sealed Gold。
5. 记录原始一致率：status、ordered deliveries、web permission、protected spans、delivery/web
   evidence spans、critical terms 和 unresolved spans。
6. 如果 status / primary family / web permission 任一原始一致率低于 80%，先判定测试合同或 Query
   表述不稳定；不得用模型预测来决定 Gold。
7. 裁决完成后冻结所有哈希。冻结后不得修改 Query、Gold、Prompt、Schema、Runner 或 Scorer。

## 4. 执行顺序与成本上限

1. 离线实现并测试 query-only 隔离、从裁决 Gold 推导覆盖、双标注比较、裁决完整性和 Freeze；
2. 质量监管 Stage Gate 检查样本覆盖、泄漏、循环论证和用户路径；
3. 只在 Gate 为 `APPROVE` 时运行 DeepSeek；
4. 每题一次、零重试，共最多 20 次调用；网络或 Provider 失败立即停止，不自动补跑；
5. 预测文件落盘后才允许评分进程读取 sealed Gold；
6. 评分后该批数据永久解封，不再作为 Blind 使用。

冻结资产分为两层：

- 公开 Prediction Freeze：Runner 唯一可读的执行清单，只含 Query 哈希、Prompt/Schema/Runner
  哈希、运行参数和预算；不得包含 Gold、标注、密封覆盖或 Scorer 信息；
- 密封 Evaluation Freeze：仅在预测完整落盘后由 Scorer 读取，绑定双标注、裁决 Gold、覆盖、
  Scorer 以及公开 Prediction Freeze 的哈希。

Runner 必须拒绝位于 `sealed/` 的 Freeze 路径。跨轮已解析的待核验主张必须显式进入 Route
Contract 的 `claims`，不能只把状态改为 `resolved` 后丢失主张内容。

## 5. Gate 指标

三层分开报告，不再把层级错配混成一个总分：

### 路由决策

- delivery sequence exact >= 85%；
- primary task family overall >= 85%，每个 A–E family >= 80%；
- output form >= 85%；
- web permission = 100%；
- clarification precision / recall >= 80% / 80%。

### L1 字段保真

- protected span char micro F1 >= 85%；
- delivery evidence 与 web evidence span char micro F1 >= 85%；
- unresolved span precision / recall >= 80% / 80%；
- 日期、金额、ATR ID、指定来源、否定限定词与禁止联网等 Gold 关键字段 recall = 100%。

### L2 / L3 投影

- Route Contract legal = 100%；
- saved envelope 与冻结代码 replay consistency = 100%；
- product complete >= 80%；
- single attempt = 100%；平均延迟 <= 8 秒，最大 <= 12 秒。

## 6. Stage Gate 与停止条件

质量监管必须同时检查代码合同和产品行为：五类用户问题是否覆盖、复合问题是否保留全部明确交付、
澄清是否会阻断用户本来明确的动作、联网权限是否符合用户表达，以及引用/跳转所需定位信息是否保真。

以下任一发生即停止，不继续修本批样本：哈希漂移、标注顺序污染、两位标注者非独立、Gold 非法、
Runner 读取 sealed 目录、Provider/网络错误、任何题多于一次调用、预测不完整或默认路由兜底。

## 7. 本阶段不做

- 不修改 v3.2 Prompt、Schema 或 Route Contract；
- 不接 Query Rewrite、检索、Prompt Registry、正式 Agent、UI 或 Docker；
- 不重建索引，不调整 Top-K / reranker；
- 不因单条失败增加关键词规则；
- 不把本次通过宣称为完整 RAG 或产品发布质量。
