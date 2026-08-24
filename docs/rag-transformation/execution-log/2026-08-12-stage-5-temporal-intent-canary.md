# Stage 5 执行记录：时间意图 Canary

日期：2026-08-12

## 已完成

- QueryPlan 新增 `temporal_intent`：`publication / source_update / report / effective`。
- metadata filter 分别选择 `publication_date / source_updated_at / report_date / effective_date`。
- lexical recent 按实际过滤的时间角色排序，不再一律按 effective date。
- 24 个查询理解与过滤测试通过；10 个 lexical 测试通过。

## 正式索引无 LLM Canary

| 问题 | 路由字段 | 结果 |
|---|---|---|
| 最近发布了哪些模型？ | publication_date | 0 条；安全空结果，当前历史库无可证明发布日期 |
| 最近更新了哪些项目？ | source_updated_at | 20 条；全部有更新时间证据 |
| 最近收录了哪些内容？ | report_date | 20 条；全部有日报收录日期 |
| 最近有什么热门趋势？ | effective_date | 20 条；保持当前趋势视图 |

“最近发布”空结果是当前语料证据缺口，不以 report date 冒充 publication date。未来新抓取的 RSS/Feed 结构化发布日期会自然进入该视图。

## Stage Gate

独立监管第一次给出 CONDITIONAL：发现“新发布 / 近期收录 / 本周日报”部分同义表达可能没有时间窗口，并要求三条互斥文档证明日期角色不串线。

修正后：

- 补齐“新发布、近期、最新、收录、本周日报”等时间窗口表达；
- 三条互斥文档分别只命中 publication/source_update/report 视图；
- 相关测试 37/37 通过。

独立监管最终结论：**PASS，Stage 5 可以关闭**。下一唯一优先项是补充结构化 `publication_date` 覆盖。
