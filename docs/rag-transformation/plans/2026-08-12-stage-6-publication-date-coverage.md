# Stage 6 计划：结构化发布日期覆盖小样

日期：2026-08-12

## 问题结论

最新三天的 `topic-pool.json` 共 165 条候选，但 `publishedAt` 与
`sourceUpdatedAt` 覆盖均为 0。源码中的新适配器已经能输出这两个字段，
因此当前缺口来自托管上游仍发布旧格式，而不是检索器丢字段。

旧格式只保留 `evidence[]` 中的“发布时间”。该字段由旧生成器把不同时间
语义混写而成，不能无条件升级为发布日期。

## 最小迁移合同

仅对可以从旧适配器代码证明其时间语义的来源做恢复：

| 来源角色 | 旧字段真实含义 | 新字段 |
|---|---|---|
| 发布事件型：Hacker News、Product Hunt、ArXiv | 原始发布时刻 | `publication_date` |
| 更新状态型：GitHub、Hugging Face、Gitee | 仓库/模型最近更新时刻 | `source_updated_at` |
| 旧官网 sitemap：OpenAI、Anthropic、DeepMind 等 | 可能只是 sitemap 更新时间 | 保持未知 |

结构化 `publishedAt/sourceUpdatedAt` 始终优先；异常日期拒绝；不从摘要正文猜日期。
恢复出的发布日期标记为 `legacy_adapter_contract`，不能伪装成新上游直接声明。

## 小样与 TDD

1. 为三类互斥来源先写失败测试。
2. 在 TypeScript 静态产物与 Python 运行时投影中实现同一合同。
3. 只投影 2026-08-12，不写正式索引，检查覆盖与角色串线。
4. 小样通过后才重建正式搜索投影与索引。

## Stage Gate

- 8 月 12 日收紧后实测：19 条 publication、27 条 source update、8 条未知；
- 中文资讯旧适配器可能以抓取时间兜底，因此即使格式合法也不恢复；
- 其中 5 条资讯来源日期还是 `+058568-10`、`Mon, 10 Au` 等损坏值；
- 更新型来源不得出现 `publication_date`；
- 旧官网 sitemap 日期不得被提升；
- 恢复来源必须可审计为 `legacy_adapter_contract`；
- 相关 TypeScript/Python 测试全部通过；
- 独立质量监管同时检查代码合同与“最近发布”用户语义。

## 回滚边界

本阶段不改原始 `topic-pool.json`，只改变规范语料投影。若 Gate 失败，撤回投影
规则即可；原始日报、唯一编号、Web UI 和既有索引均不受影响。
