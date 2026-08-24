# 单日真实语料事件化影子实验

## 决策问题

在不修改正式索引的前提下，验证六个最小事件字段是否能改善“某公司最近有哪些重要动态”的主榜准入，尤其减少“只提到品牌的第三方工具、教程和普通配置”污染。

## 本阶段不验证什么

- 不验证自动事件抽取器的准确率。
- 不重建 ChromaDB 或 Neo4j。
- 不用这 20 条样本报告全系统 Recall、F1 或生产可用性。

先将“事件契约是否有用”和“事件契约如何自动生成”解耦。人工冻结字段作为 Oracle；如果 Oracle 都不能改善结果，就停止事件化改造。

## 测试边界

公开接口：`EvidenceRetrievalGateway.retrieve(ResearchRequest)`。

输入是用户问题；可观察输出是 `records`、`background_records` 和 `excluded_candidate_ids`。测试不直接调用私有排序函数。

## 最小事件契约

- `content_kind`
- `event_type`
- `subject_entity_ids`
- `mentioned_entity_ids`
- `publication_date`
- `temporal_confidence`

## 执行顺序

1. 从 2026-08-05 冻结 20 条真实记录和独立人工标签。
2. 写公开接口失败测试，证明旧的 `entity_ids` 无法区分事件主体与普通提及。
3. 仅让 Gateway 优先消费六字段契约，同时保留旧索引兼容路径。
4. 对同一批样本运行 V0 旧实体、V1 主体角色、V2 完整事件字段三种视图。
5. 监管 Agent 审查标签独立性、数据泄漏与产品流程。

## Stage Gate

- V1 必须比 V0 减少“仅提及实体”进入候选集的数量；V2 必须进一步排除教程、兼容性、项目列表和普通价格细节。
- 重要官方事件不能因过滤而丢失。
- 结果必须保留稳定 ATR 编号和可跳转引用。
- 现有回归测试全部通过。
- 若提升不明显，停止，不开发自动抽取器。

本日不产生“历史背景”结论，因为源发布日期覆盖不足。背景层另用 3–5 条历史伴随样本验证。`importance_label` 与 `event_group_id` 只属于评估标签，暂不进入生产契约。
