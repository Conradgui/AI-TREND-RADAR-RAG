# Ordered Query Frame v3.2 双标注 Blind 执行记录

- 日期：2026-08-21
- 实验：`ordered-query-frame-v3-2-new-blind-2026-08-21`
- 证据边界：只评估 Query Frame / Route Contract；不评估检索、GraphRAG、最终回答或发布质量
- Provider：DeepSeek `deepseek-v4-flash`
- 调用：20/20，单题一次、零重试、0 error

## 1. 标注与冻结

- 20 条公开 Query 只含 `case_id/query/conversation_context`；
- A–E 主任务各 4 条，8 条复合任务，4 条澄清；
- 联网 `explicit=4 / forbidden=4 / on_demand=12`；
- 两位独立标注者的 status、primary family、web permission 一致率均为 100%；
- 46 个 span / 关键字段粒度分歧由第三位裁决者逐项裁决；
- `expected_protected_terms` 原始一致率仅 55%，`expected_critical_terms` 完全一致率为 0%。

冻结分为公开 Prediction Freeze 与密封 Evaluation Freeze。首次 Stage Gate 因 Runner 读取 sealed
清单、跨轮 claim 未进入 Route Contract 而 BLOCK；TDD 修复后，46 个相关测试通过，第二次独立
Stage Gate 为 APPROVE。

## 2. 正式 Blind 结果

| 指标 | 结果 | Gate |
|---|---:|---:|
| delivery sequence exact | 85.0% | 85% |
| primary family overall | 95.0% | 85% |
| A / B / C / D / E | 100 / 100 / 75 / 100 / 100% | 每类 80% |
| output form | 89.3% | 85% |
| locator | 96.4% | 诊断指标 |
| web permission | 100% | 100% |
| protected span char F1 | 71.5% | 85% |
| delivery evidence char F1 | 96.1% | 85% |
| web evidence char F1 | 91.1% | 85% |
| critical term recall | 95.6% | 100% |
| unresolved precision / recall | 100 / 79.2% | 80 / 80% |
| clarification precision / recall | 100 / 75% | 80 / 80% |
| L3 legal / replay consistency | 100 / 100% | 100 / 100% |
| product complete | 20% | 80% |
| mean / max latency | 1.836 / 2.384 秒 | 8 / 12 秒 |

结论：Gate 未通过，不接正式 Agent，不修改本批 Gold，不重跑本批 Blind。

## 3. 错误归因

### 真实产品错误

- `v32-new-blind-012`：明确询问三方“是什么关系”，被误分为 E explanation；C relation 为 3/4，
  导致分路线 Gate 失败。
- `v32-new-blind-016`：无上下文的“这个说法”未触发澄清，导致 clarification recall 只有 75%。
- `v32-new-blind-009`：完整书名号标题被输出为 `title_fragment/item_disambiguation`，而非
  `full_title/exact_item`。
- `v32-new-blind-018`：条件影响分析被过度升级为 `deep_research`，而非 `explanation`。

### 合同与评估粒度问题

- protected span 的模型 precision 为 98.4%、recall 为 56.2%，说明模型倾向输出少而精的语义原子；
- 两位人工标注者在 protected span 上只有 55% 完全一致，关键字段分组为 0% 完全一致；
- 因此 raw protected char F1 适合作为诊断，不适合在标注粒度尚未稳定时单独代表产品保真；
- 产品真正需要 Gate 的是最终 Route Contract 是否保留日期、金额、ATR ID、来源、否定、权限和
  已解析上下文主张，而不是模型是否圈出与裁决者完全相同宽度的字符串。

## 4. 架构决策

v3.3 不继续单纯加长 Prompt，也不引入通用 Router 框架。采用职责分层：

1. LLM 负责有序 deliveries、主辅任务、relation / explanation 等语义边界；
2. 确定性投影负责可由 Query 直接证明的 ATR ID、完整标题、联网权限、时间/数字/否定约束和
   无上下文指代的失败关闭；
3. Gate 同时报告 raw Frame span 指标与最终 Route Contract 关键字段保真，后者作为产品 Gate；
4. 本批已解封，只可作为 v3.3 可见诊断/回归集，不得再次宣称 Blind。

## 5. v3.3 后续状态

- v3.3 计划经质量监管三轮收敛后 APPROVE；
- 确定性规则被限制为 ATR ID、完整书名号标题、明确联网/禁网和无上下文指代；
- relation 与 deep-research 只修改 Prompt，不新增关键词路由器；
- 第一批 TDD 离线回归 55/55 通过；
- v3.3 已新增独立合同级 scorer；旧 v3.2 scorer 未被修改或复用。

## 6. v3.3 可见校准结果

- 资产：6 条已解封的修复/控制样本，明确标记为 `visible-calibration`，不构成 Blind 或泛化证据；
- 评分：Gold 逐项指定 `path / literal / match`，只允许在目标 Route Contract 字段得分；
- 评分器辨别力：TDD 证明 `正确 > 局部退化 > 完全错误`，相同 literal 放入错误字段不得补分；
- 第一次独立 Stage Gate 因跨字段补分风险 BLOCK；修复并重建 Freeze 后，复审 APPROVE；
- 首次沙箱运行在第 1 条以 `APIConnectionError` 停止，0.349 秒、无 Provider 结果，作为基础设施
  无效运行保留，不计入模型质量；
- 外部网络恢复运行：6/6、0 error、Provider 侧单题一次、零重试；
- delivery、status/contract shape、web permission、合同 literal、L3 legal/replay、product complete
  均为 100%；
- 平均 / 最大延迟：1.972 / 2.836 秒；
- raw Frame protected exact-span 继续只作诊断，不参与产品 Gate。

结论：v3.3 可见回归 Gate 通过，证明四个已知缺陷在既有样本上已修复且两个控制样本未回归；
不能据此宣称新问题泛化通过。下一决策应是冻结合同设计后创建全新、未见的 Blind，而不是继续调旧样本。
