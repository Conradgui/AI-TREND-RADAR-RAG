# 官网内容提取开源方案调研

日期：2026-08-07

## 调研问题

AI Trend Radar 每天只需处理少量由官方 Feed 或 Sitemap 发现的新链接。目标是稳定取得标题、官方简介、发布日期与正文，同时兼容 GitHub Actions 中个别官网页面可能返回 403 的情况；不是建设通用互联网爬虫平台。

## 候选方案

| 方案 | 官方定位 | 优势 | 主要代价 | 对当前项目的判断 |
|---|---|---|---|---|
| [Mozilla Readability](https://github.com/mozilla/readability) | Firefox Reader View 使用的正文提取库 | 成熟、Apache-2.0；返回 title、excerpt、textContent、publishedTime | Node.js 需要额外 DOM 实现（如 jsdom）；不负责下载或绕过 WAF | 稳健备选，集成略重 |
| [Extractus article-extractor](https://github.com/extractus/article-extractor) | 从 URL/HTML 提取文章和 metadata | TypeScript 友好；直接返回 description、content、published；支持自定义 fetcher；MIT | 不能绕过源站 403；维护规模小于 Mozilla | 当前页面提取首选 |
| [Extractus feed-extractor](https://github.com/extractus/feed-extractor) | 统一解析 RSS、Atom、JSON Feed | 输出标准 title/link/description/published；TypeScript 友好；MIT | Feed 地址仍需发现或配置；不是正文抓取器 | 当前 Feed 解析首选候选 |
| [rss-parser](https://github.com/rbren/rss-parser) | Node/browser 轻量 RSS 解析 | 成熟、简单、TypeScript 支持 | 主要面向 RSS/XML；标准化能力比 feed-extractor 窄 | Feed 解析稳健备选 |
| [Crawlee](https://github.com/apify/crawlee) | Node.js 端到端抓取与浏览器自动化平台 | 队列、重试、代理、HTTP/浏览器双模式、Apache-2.0 | 依赖和运行成本明显增加，浏览器模式还需 Playwright | 现阶段过重 |
| [Firecrawl](https://github.com/firecrawl/firecrawl) | 托管/自托管 Web Data API | 动态网页、搜索、批量抓取、Markdown/结构化输出 | 托管需 API Key/费用；自托管增加服务；主仓库 AGPL-3.0 | 只适合作为未来可选困难页面适配器 |

## 一手资料要点

- Mozilla Readability 官方文档说明，它是 Firefox Reader View 使用的独立版本；Node.js 需要外部 DOM 库，`parse()` 可返回 `excerpt` 和 `textContent`，并明确提示不负责清理不可信 HTML。
- Extractus article-extractor 官方接口同时返回 `description` 与 `content`，还允许注入自定义 fetcher，适合把当前超时、请求头和测试假响应留在项目控制之下。
- Extractus feed-extractor 官方接口可统一解析 RSS、Atom、RDF 和 JSON Feed，并将条目标准化为 title、link、description、published。
- Crawlee 官方项目覆盖队列、自动扩缩、代理、会话、Cheerio/JSDOM 和真实浏览器；这些能力适合大规模或强动态抓取，但超过当前每日少量官网文章的需求。
- Firecrawl 官方说明其托管快速开始需要 API Key，自托管仓库采用 AGPL-3.0；它解决的是搜索、抓取、交互、整站 Crawl/Map 等更大范围问题。

## 关键判断

任何文章提取库都工作在“已经拿到 HTML”之后，不能把被 Cloudflare/WAF 拒绝的 403 页面变成可读页面。因此，OpenAI 官方 Feed 与文章提取器不是二选一：Feed 解决可达性并提供第一方 description，文章提取器解决普通可达页面的正文与 excerpt 质量。

普适做法也不是给 OpenAI、Anthropic、DeepMind 各写一套抓取代码，而是：

1. 来源配置只声明可用的标准入口（Feed URL、Sitemap URL、路径过滤）。
2. 统一 Feed 解析器读取第一方 description。
3. 统一文章提取器补足无 Feed 来源的 excerpt/content。
4. 按 canonical URL 合并，同一条记录分别保存 `summary` 与 `content`。
5. 只有标准入口确实失败时，才增加站点专属 Adapter。

## 推荐

当前 Stage 推荐采用 `@extractus/feed-extractor` + `@extractus/article-extractor`，理由是接口正好覆盖当前缺口、TypeScript 集成最小、许可证宽松，并允许复用当前 fetch 超时与测试方式。Mozilla Readability 保留为文章提取质量不达标时的稳健替代；Crawlee 和 Firecrawl 暂不进入默认依赖。

实施前仍需用 OpenAI、Anthropic、DeepMind 的固定 HTML/Feed fixtures 做离线对比测试；选型不能只看 README，必须以三类真实页面的摘要准确性和正文噪声率为准。
