# Ordered Query Frame v3.1 新 Blind 错误归因

- 日期：2026-08-16
- 冻结结果：FAIL（不得覆盖或改写为 PASS）
- 正式流量：禁止
- 预测：20/20、零异常、每题一次

## 冻结指标

| 层 | 指标 | 结果 | 判断 |
|---|---|---:|---|
| L1 | primary task family | 90.0% | 骨架基本成立 |
| L1 | ordered deliveries exact | 65.0% | 不达标 |
| L1 | output form | 73.1% | 不达标 |
| L1 | locator | 92.3% | 可保留 |
| L1 | web permission | 100.0% | 通过 |
| L1 | protected char micro-F1 | 83.2% | 略低于门槛，但存在 Gold 合同冲突 |
| L1/L2 | unresolved P/R | 100% / 100% | 通过 |
| L2 | clarification P/R | 100% / 100% | 通过 |
| L3 | legal / replay consistency | 100% / 100% | 通过 |
| L4 | product complete | 50.0% | 不达标 |

## 三类问题必须分开

### A. 真实模型语义错误

1. **重要新闻被过度升级为趋势簇**：003、006、007 将 `important_news` 预测为
   `trend_clusters`。根因是 Prompt 写了“更丰富形式可以包含较简单形式”，但没有同时
   规定只有用户明确要求按主题聚类时才选择 `trend_clusters`。
2. **复合交付漏项**：008 保留 B，却漏掉用户明确要求的 supporting A。
3. **跨时间比较误分为普通比较**：010 将同一实体两个时间截面的变化分到 E，而不是
   C `cross_sectional_trend`。
4. **时间输出形式边界不稳**：012 把无离散节点的“多年演变”选成 timeline，而不是
   longitudinal trend。
5. **澄清时丢失明确交付**：018 正确识别 unresolved reference，却输出空 deliveries；
   产品合同要求保留明确 E delivery，再由 L2 进入 clarification。

### B. Gold 与 Prompt 的标注合同冲突

Prompt 将三类信息分开：

- `deliveries/evidence_spans`：用户要系统做什么；
- `web_permission/web_evidence_spans`：是否联网及其原文依据；
- `protected_spans`：实体、ID、标题/主张、时间、数字、指定来源等内容锚点。

但冻结 Gold 又把“完整标题、对应条目、请联网、必要时可联网、研究报告”等输出指令
或联网指令重复放入 `expected_protected_terms`。这与 Prompt 的“排除通用任务词”以及
独立 `web_evidence_spans` 冲突，系统性压低 protected recall 和 L4 product complete。

冻结分数仍然有效地说明“候选没有通过这份冻结合同”，但不能把全部差距解释成模型
理解错误。后续 Gold 必须先按字段职责重新双标，禁止看预测后只挑有利标签。

### C. 评估 Harness 缺陷

1. 首次正式运行完成 Provider 循环后，Runner 才读取不存在的 `dataset_id`，导致预测
   未落盘；失败证据已单独保存，不能计入模型分数。
2. v2 Runner 在调用前兼容并校验 `dataset_id / shard_id`，20/20 成功落盘。
3. 首次离线评分仍只读取 `dataset_id`；评分修正案仅统一数据集身份解析，不修改预测、
   Gold、公式或阈值，随后产出当前冻结 FAIL。

## 架构判断

当前证据不支持全盘替换 Query Frame 架构：primary、web、clarification 和 L3 已稳定。
问题集中在 L1 的细粒度输出合同与标注职责。下一步应做 Prompt-only 小样，而不是引入
新的 Router 框架、调整检索 Top K 或修改正式 Agent。

## 下一步成功标准

用 7 条已解封失败/对照样本做 v3.2 校准 canary：

- ordered delivery exact >= 6/7；
- primary route = 7/7；
- web permission = 7/7；
- clarification P/R = 100% / 100%；
- protected Gold 只评内容锚点，不重复评 delivery/web 字段；
- 每题一次、零重试、平均 <= 8 秒、最大 <= 12 秒。

任一关键门失败即停止，不生成新 Blind，不接生产。
