# New Blind v3.1 隔离复核与合并裁决

- 日期：2026-08-16
- 范围：仅复核两个 Query shard、两个 Gold shard、ordered semantic frame schema 与两份计划；未读取 predictions/results/score、旧 Gold 或实现模型输出。
- 结论：合并为 20 题，保留 case 顺序 `new-blind-001` 至 `new-blind-020`。

## 已裁决事项

1. 同一 task family 的多个回答小节合并为一个 delivery，并选择能覆盖请求的更丰富 output form；因此 005 的新闻与主题聚类合并为 B `trend_clusters`。
2. 明确先汇总动态、再梳理动态如何改变路线，属于两个不同 family 的有序 B+C（006）；时间范围本身不新增 B。
3. 后置主张（013、019）、标题片段（003）和普通“对应记录”（008）均不是 unresolved；只有没有唯一可执行映射的指代（002、007、012、018）进入 clarification，并保留明确 delivery。
4. 仅空 context 不足以把有明确实体的 Query 判为 unresolved；含“这个/这项”且无唯一映射的 Query 才澄清。
5. 修正两处 schema 对齐：002 的 descriptive locator 改为 `item_disambiguation`；010 的两个时间截面变化改为 `cross_sectional_trend`，不是非法的 temporal `comparison`。

## 机械校验结果

- Query cases：20；Gold cases：20。
- ID：两文件均为 001–020，逐项一致，无重复。
- primary：A/B/C/D/E 各 4。
- clarification：4；其中保留 delivery 4。
- 复合 delivery：6（003、006、008、010、013、019）。
- web permission：`forbidden`、`on_demand`、`explicit` 三态均覆盖。
- Gold span：所有 protected/unresolved span 均为对应 Query literal；未改写 Query literal。
- 未决项：无。

## 封存前契约校正

- 机器校验发现 4 条澄清样本使用了简写枚举 `clarification`；已统一为冻结评估器规定的 `clarification_required`。
- 本次只修改 `expected_status` 枚举，不修改 Query、delivery、span、联网权限或标注理由。
