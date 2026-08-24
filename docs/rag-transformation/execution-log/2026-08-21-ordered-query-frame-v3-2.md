# Ordered Query Frame v3.2 Prompt-only 校准执行记录

- 日期：2026-08-21
- 分支：`claude/rag-transformation-checkpoints`
- 证据等级：已解封校准，不是 Blind、泛化、生产或检索质量证据
- Docker：未启动；本阶段不依赖服务容器，也未创建或重建容器

## 1. 本阶段目标与边界

本阶段只验证 Query 理解 seam 中的五个决策边界：重要新闻与趋势簇、跨任务族复合交付、
C/E 比较边界、四种 C 输出形式、澄清与 delivery 正交。未修改 Schema、L2、RAG、
正式 Agent、Web UI 或索引。

## 2. TDD 与质量门禁

1. Prompt contract 测试先失败，证明旧 Prompt 缺少目标规则；
2. 最小修改 `rag/ordered_frame_client_v3.py`；
3. 修正通用校准器的两个测量错误：缺席 task family 不再被计为 0 分，clarification
   样本也从 L1 frame 评估 web permission；
4. 增加“完美预测必须使 Gate PASS”的离线测试；
5. 相关离线测试：`42/42` 通过；
6. 质量监管 Agent 三轮审阅后给出最终 `GO`，随后立即关闭。

## 3. 冻结资产

- Query：`ordered-query-frame-v3-2-visible-calibration-queries-2026-08-21.json`
- Gold：`ordered-query-frame-v3-2-visible-calibration-gold-2026-08-21.json`
- Freeze：`ordered-query-frame-v3-2-visible-calibration-freeze-2026-08-21.json`
- Predictions：`ordered-query-frame-v3-2-visible-calibration-predictions-2026-08-21.json`
- Score：`ordered-query-frame-v3-2-visible-calibration-score-2026-08-21.json`

运行前已验证 Query、Gold、Prompt、Provider Schema、Runner、Scorer、Route Schema、
runtime 哈希。真实运行严格为每题一次、零重试。

## 4. 真实 DeepSeek 结果

| 指标 | 结果 | v3.2 门槛 | 裁决 |
|---|---:|---:|---|
| 调用完成 | 7/7，0 error | 7/7 | PASS |
| ordered delivery exact | 6/7（85.7%） | >= 6/7 | PASS |
| primary route（resolved） | 5/5（100%） | 5/5 | PASS |
| web permission | 7/7（100%） | 7/7 | PASS |
| clarification precision / recall | 100% / 100% | 100% / 100% | PASS |
| 单次调用 | 7/7 | 7/7 | PASS |
| 平均 / 最大延迟 | 2.141s / 2.599s | <= 8s / <= 12s | PASS |

因此 **v3.2 的路由决策校准 Gate 通过**。它只证明这 7 条已解封样本上的目标边界得到修正，
不证明新样本泛化，也不允许直接接入正式 Agent。

## 5. 不应混入路由裁决的字段问题

通用 Score 文件同时报告 `protected_span_micro_f1 = 65.0%`、
`complete_projection_accuracy = 14.3%`。该数字混合了两类问题：

1. **评估器层级错配**：Gold 标注 L1 frame 字段，但 resolved 样本使用 L2 Route Contract
   的合并后 `protected_terms` 比较；联网权限和定位信息因此被误报为多余项。
2. **真实 L1 抽取误差**：003、008 截短限定词或实体；018 将三个并列要求合成一个 span。

按同层级 L1 frame 重算：precision 81.2%、recall 72.2%、F1 76.5%，exact 4/7。
该指标仍未达标，但它属于字段保真问题，不应推翻本阶段已经通过的路由决策 Gate。

## 6. 唯一明确的路由错误

`new-blind-008` 正确输出 B `trend_clusters`，但漏掉 supporting A
`item_navigation/descriptive`。这是复合交付召回不足，不应使用该已解封样本继续调 Prompt。

## 7. 下一 Stage Gate

下一阶段只做新的双重标注 Blind，用未参与 Prompt/Gold 调整的 Query 验证泛化，并在评分器中
严格分开：

- 路由决策指标；
- L1 字段保真指标；
- L2 Route Contract 投影指标。

Blind 通过前继续暂停 Query Rewrite、检索参数、GraphRAG、正式 Agent、UI 和 Docker 改造。
