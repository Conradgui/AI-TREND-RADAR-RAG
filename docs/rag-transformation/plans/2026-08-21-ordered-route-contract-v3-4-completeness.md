# Ordered Route Contract v3.4 完整性交付切片

## 1. 为什么先补合同，而不是直接做新 Blind

v3.3 可见校准 6/6 只证明四个旧错误已修复。独立质量监管指出，最终 Route Contract 仍无法完整
表达用户交付：顶层主导航没有 locator，非导航辅助任务没有 output；时间和来源文字也可能只留在
`protected_terms`，下游无法稳定消费。此时直接做新 Blind 会测试一个不可观测接口。

## 2. 最小架构决策

新增统一的 `delivery_contracts` 序列，每项固定为：

```text
task_family / requested_output_form / locator_kind
```

- 它保存用户要求的有序交付，不保存执行策略；
- 现有 `supporting_contracts` 继续保存 rewrite/retrieval/prompt/budget 等执行策略；
- 主任务和辅助任务使用同一结构，不再分别追加字段；
- Ordered Frame 投影必须保证 `delivery_contracts` 与 Frame deliveries 完全一致；
- 旧的非 Ordered shadow 路径允许暂时输出空序列，避免在本切片重写历史规则路由。

时间与来源沿用现有 `temporal_constraint` / `source_constraint`：

- 明确相对窗口、年份/月/日表达进入 `temporal_constraint.value`；多个时间截面按原顺序保存；
- 明确“内部日报/内部语料/内部知识库”进入 `requested_sources`；“X 官方”设置
  `official_first=true` 并保留 X；
- 只投影 Query 中可直接观察的文字，不猜测来源，不新增实体词表。

## 3. TDD 公共 seam

1. 主 A 的 ATR ID / full title / fragment / descriptive locator 在 `delivery_contracts[0]` 可见；
2. 辅助 B/C/D/E 的 output 在对应 `delivery_contracts[i]` 可见；
3. delivery 序列与 Frame 顺序完全一致；
4. 两个绝对月份进入 temporal 专用字段，不只进入 protected terms；
5. 明确内部来源与官方优先进入 source 专用字段；
6. Route Contract Schema 与语义校验拒绝 delivery 序列漂移。

## 4. Stage Gate

- 先写失败测试，再做最小实现；
- 相关 Route Contract / Ordered Frame 回归全部通过；
- 独立质量监管确认没有把语义任务重新做成关键词 Router；
- 通过后才设计不少于 14 条的全新未见 Blind；
- 新 Blind 覆盖 A–E、4 类 locator、复合顺序、联网、澄清、时间和来源专用字段；
- 关键合同字段 100%，product complete 至少 13/14。

## 5. 明确暂停

Query Rewrite、检索/GraphRAG、Prompt Registry、正式 Agent、UI、索引和 Docker 继续暂停。

## 6. 正式 Blind 结果（2026-08-21）

- 15/15 完成，零错误、零重试；
- Ordered Frame delivery exact：15/15；
- Product complete：8/15，正式 Gate 未通过；
- 失败由真实合同缺陷、模型语义遗漏与 Gold/Scorer 过约束共同造成，不能把 8/15 解释为
  整体路由准确率；
- 本批已永久解封为诊断资产，不得修改 Gold 后重跑；
- 下一步转入 v3.5 可见小样修复，仍不进入下游模块。
