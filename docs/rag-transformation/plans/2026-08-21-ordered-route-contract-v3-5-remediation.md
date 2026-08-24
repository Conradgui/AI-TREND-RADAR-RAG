# Ordered Route Contract v3.5 最小修复计划

## 1. 目标

修复 v3.4 全新盲测暴露的合同 seam，避免把评估器的字符串偏好写进生产架构。v3.5 是
可见校准，不是新的泛化证明。

## 2. 范围

### 必修的产品缺陷

1. 无公开上下文时，裸指代（如“它”）必须触发澄清；来源短语不能被误当作指代前件。
2. 用户在 Query 中直接提出的事实陈述或假设必须进入 `claims`。
3. “X 官方 / X 官方材料 / X 官方发布”统一投影为 `requested_sources=[X]` 且
   `official_first=true`，不建立公司名称词表。
4. “不要扩展成…… / 不要讨论……”等会改变回答范围的否定约束必须保留。
5. 时间范围不再用 `A | B` 作为唯一表示；合同应同时支持原始短语与结构化边界。

### 评估协议修订

1. source / permission 只评分专用字段，不要求在 `protected_terms` 重复。
2. unresolved reference 评分“是否识别同一未解析对象”，不要求完全相同字符边界。
3. 引号只是表面格式；标题内容一致即可，不要求数组成员保留引号。
4. span 粒度按语义完整性评分，不强制把更完整短语拆成 Gold 的短片段。

这些规则仅用于 v3.5 新协议；不追溯修改或替代 v3.4 正式结果。

## 3. TDD 小样

先建立 6 条公开用例：

1. 裸指代、无公开前件 -> clarification；
2. 直接事实 claim -> `claims`；
3. 假设 claim -> `claims`；
4. 任意中文机构官方材料 -> source contract；
5. 内容改变型否定 -> 约束保真；
6. 绝对时间区间 -> surface + start/end 双表示。

Red 阶段必须证明现实现失败；Green 阶段只改公共 seam。禁止为案例中的实体增加关键词规则。

## 4. Stage Gate

离线通过标准：

- 6/6 新用例通过；
- v3.3/v3.4 相关合同回归全部通过；
- `correct > degraded > wrong` 的评分器辨别力仍成立；
- Schema 与 deterministic replay 通过；
- 独立质量监管确认没有跨字段重复、实体词表补丁或职责泄漏。

若需要真实模型，只允许一次 4–6 条可见校准、每题一次、零重试。可见校准只判断修复是否
有效，不宣称泛化，也不追加新 Blind。

## 5. 明确暂停

在 v3.5 Gate 通过前继续暂停 Query Rewrite、Retrieval/GraphRAG、Prompt Registry、正式
Agent、UI、索引与 Docker 改造。

## 6. 2026-08-21 执行结果

- 10/10 离线可见 TDD 小样通过；
- 相关回归、Schema 与评分器 Gate：`95 passed, 28 subtests passed`；
- 一次 6 题 DeepSeek 可见校准首轮 5/6；失败项已通过公共护栏修复，按协议不重跑；
- 没有实体词表补丁，没有修改冻结语料或索引；
- 独立监管复审：`APPROVE_WITH_ACTIONS`。允许进入固定语料、影子模式的检索调优；不得直接
  接正式 Agent。检索入口必须验证 Route Contract，并按 A–E 分层报告。
