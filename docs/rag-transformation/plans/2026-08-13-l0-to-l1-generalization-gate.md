# L0→L1 真实理解与泛化 Gate

- 日期：2026-08-13
- 状态：可见 Gate 未通过；当前候选 REJECT，禁止冻结和盲测
- 正式流量影响：禁止
- 外部调用：仅在三条可见 canary 通过后，才允许扩展到十二条可见校准；未见盲测另设一次性 Gate

## 要解决的问题

已经冻结的 Narrow Semantic Decisions v1 只证明“给定正确 L1 后，L2 能生成正确合同或明确澄清”。它没有证明真实用户 Query 可以稳定地产生正确 L1。旧关键词抽取器在封存盲测中大量默认到 E；旧模型合同又同时承担抽取和路线裁决，导致结构、成本与产品语义都不可靠。

## 公共 seam

```text
真实 Query + 可选公开会话上下文
  → NarrowDecisionExtractor.extract(...)
  → Narrow Semantic Decisions v1
  → Route Contract v2 / clarification_required
```

调用方只需理解一个接口：输入真实 Query 和公开上下文，得到完整合同或明确澄清。模型供应商、Prompt、重试与 JSON 修复属于模块实现，不泄露到下游。

## 候选实现

1. 模型只判断五个 route-neutral 语义维度，不得输出 A–E、路线、策略、答案模式或最终答案。
2. 每个 `present / uncertain` 判断必须附真实 Query 中逐字连续的证据片段。
3. 调用方传入的 Query 是唯一真源；L1 不得自报或替换 Query。
4. Schema 校验、字面证据、上下文 ATR 引用与 L2 路由由确定性代码裁决。
5. 第一次输出不合法时，最多做一次带具体校验错误的纠错重试；仍失败则 fail-closed。
6. 本阶段不接正式聊天、检索、Prompt Registry 或 Web UI。

## TDD 与成本阶梯

1. 用 fake external adapter 写公共 seam 红灯测试：合法输出、一次纠错、双次失败关闭。
2. 完成最小生产 adapter 与编排模块，让测试转绿。
3. 真实 DeepSeek 三条可见 canary：A+E、B+D、未解析指代。
4. 三条全部 Schema/语义/投影正确且平均延迟不超过 8 秒，才运行十二条可见校准。
5. 十二条通过后冻结实现、Prompt、Schema、测试与依赖哈希。
6. 冻结后由隔离 Agent 创建新的 query-only 与 sealed Gold；主流程预测落盘后才可评分。

## Gate

### 可见 canary Gate

- 3/3 Schema 与字面证据合法；
- 3/3 完整投影正确；
- 平均延迟 ≤ 8 秒，单条最大 ≤ 12 秒；
- 单条最多两次 API 调用；
- 不出现默认 E。

### 未见泛化 Gate

- 主路线总体准确率 ≥ 85%，每类 ≥ 80%；
- 最小对照 100%；
- 显式联网/禁止联网 100%；
- protected span micro F1 ≥ 85%；
- 歧义 precision、recall 均 ≥ 80%；
- 完整投影精确匹配 ≥ 70%。

## 非目标

- 不以可见 12/12 宣称泛化成功；
- 不调检索 Top K、排序、Prompt Package 或回答渲染；
- 不把失败样本追加进关键词白名单；
- 不在本阶段接入生产。

## 2026-08-15 Gate 结果

- 三条可见 canary：路线投影 3/3，平均 2.228 秒；复核发现标题保真外壳问题后补强完整合同评分。
- 十二条首次可见校准：9/12，平均 3.095 秒；失败集中在主次裁决、上下文复合指代和 protected terms。
- 三项通用确定性修复后，十二条可见复测：11/12，平均 2.116 秒。
- 唯一失败 `NSD-007` 定点复测仍为 0/1：连续三次无法生成合法 L1。

结论：当前候选不得冻结、不得创建未见盲测、不得接正式流量。根因不是继续增加 Prompt 例子即可解决，而是 strict tool 仍让模型同时承担五维判断、保真词、locator 和引用解析，违背本计划“模型只判断五维”的职责边界。
