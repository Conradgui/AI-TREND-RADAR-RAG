# OpenAI 空摘要诊断记录

日期：2026-08-07

## 最小复现

读取 `digests/2026-08-05/ai-topic-radar.md` 的摘要列，Apple、Economic Research Exchange、ChatGPT Work/Codex 三条均为空，命令稳定返回失败。

## 根因

`src/web.ts` 中 OpenAI 的 `metadataOnly` 策略绕过文章页抓取，并为每个条目固定设置 `content: ""`；`src/topic-radar.ts` 随后将该值直接映射到 `summary`。这是确定性设计缺口，不是偶发网络错误、LLM 超时或前端渲染问题。

同一接口还存在相反方向的问题：Anthropic、Google DeepMind 的 `content` 是最多 1500 字的页面正文片段，同样被日报当成 `summary`。因此空摘要和超长摘要实际来自同一个字段建模错误：展示摘要与分析正文没有分离。

## 历史复核

- 初始提交 `4a263856` 已存在 OpenAI `metadataOnly` 和空 `content`；这不是近期摘要折叠改动造成的数据丢失。
- 提交 `7bcdd2b` 新增日报“摘要”列时，没有同步建立摘要非空约束，才让既有缺口成为用户可见的空白列。
- 当前历史日报按日期和 URL 去重后，OpenAI 46 条全部为空；Anthropic 96 条、Google DeepMind 58 条均非空。问题范围明确集中在 OpenAI 特例。

## 外部一手证据

OpenAI 官方 RSS 对三条记录均提供非空 description，说明无需依赖推测性摘要即可修复；官方文章页也能读取正文，但云端 Actions 的可达性仍不应被假定为稳定。

官方资料还显示 Economic Research Exchange 首次发布于 2026-06-08、于 2026-08-05 更新；当前 sitemap 元数据链路未表达发布与更新的区别。

## 预防措施

- 为每种数据源定义摘要来源优先级和质量状态。
- 报告生成前统计高优先级条目的空摘要率。
- 数据源适配器测试同时验证“发现 URL”和“获得可展示摘要”，避免只测数量。
