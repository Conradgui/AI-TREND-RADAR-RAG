# 摘要采集链路实施与验收记录

日期：2026-08-07

## 本轮目标

在不增加前端折叠/占位复杂度的前提下，修复 OpenAI 空摘要、官网正文冒充摘要，以及启动同步把已修复摘要重新覆盖为空的问题。

## 实施内容

1. 引入 `@extractus/feed-extractor` 与 `@extractus/article-extractor`：分别处理官方 Feed 和普通文章页；未引入 Crawlee、Firecrawl 或浏览器集群。
2. `WebPageItem` 拆分 `summary` 与 `content`：前者只承载来源提供的简短描述，后者承载供分析/RAG 使用的较长正文。
3. OpenAI 使用官方 RSS description；Feed 与 Sitemap 按 canonical URL 合并。Anthropic、DeepMind 使用文章提取器获取 description 与正文。
4. 日报映射从 `item.content` 改为 `item.summary`；前端保持原始 Markdown 表格展示，不新增摘要折叠逻辑。
5. 空摘要进入数据质量告警，不允许根据标题编造摘要。
6. 增量状态兼容旧 URL 键：同时识别有/无尾斜杠，并在后续写入时迁移到规范键，避免数百条历史 URL 被误判为新增。
7. 同步增加单向质量保护：上游摘要为空时，保留同 URL 已存在的非空本地摘要；标题等其他字段仍以上游为准。
8. 对 `2026-08-05` 的三条 OpenAI 记录定点回填官方摘要；没有重算历史分数、排序或其余字段。

## 测试驱动证据

- OpenAI Feed 用例首次运行时因尚无 Feed 支持而失败，实施后通过。
- 摘要/正文分离用例首次证明日报仍读取长正文，单点修正后通过。
- 旧 URL 无尾斜杠回归测试首次捕获重复抓取，兼容修复后通过。
- “空上游覆盖非空本地摘要”测试首次失败，增加同步防回退后通过。

最终自动验证：

- TypeScript：14 个测试文件，228 个测试通过。
- Python RAG：331 个测试通过。
- TypeScript 类型检查通过。
- ESLint 通过。
- `git diff --check` 通过。

## 真实来源验证

对 OpenAI 官方 Feed 与 Sitemap 做真实网络冒烟测试：发现 1160 个 URL，首轮按上限处理 25 条；以下三条均匹配到非空官方摘要：

- `Apple is getting this wrong`
- `Introducing the OpenAI Economic Research Exchange`
- `New ways to learn and teach with ChatGPT Work and Codex`

这同时证明 Economic Research Exchange 的官方发布时间是 2026-06-08，而历史日报行仍记录为 2026-08-04。为保持历史决策证据可追溯，本轮只补摘要，没有静默改写历史日期和分数。

## 代码审阅结果

Standards 审阅发现 1 个 P1：URL 规范化会使旧状态失效；已补回归测试并修复。

Spec 审阅发现同一 P1，以及三条已知 OpenAI 记录测试覆盖不足；已扩展 fixture，三条均有明确断言。

修复后未发现新的阻断项。

## 运行环境验收

- Docker 应用容器使用新镜像重建；Neo4j/Chroma 数据卷未删除。
- `/health`：`status=ok`、Neo4j 已连接、ChromaDB 6285 chunks、61/61 日期一致。
- 浏览器访问 `http://127.0.0.1:8001/#2026-08-05/ai-topic-radar`：三条官方摘要均真实可见；非静态模式；未显示连接失败。
- 启动同步后，容器内三条摘要仍存在，证明上游空值不再倒灌覆盖本地有效摘要。

## 边界与后续

- 本轮没有批量重写其他历史日期；历史 OpenAI 空摘要的全量回填应作为独立迁移任务，先定义证据与重算边界。
- 当前同步仍在后台执行“先本地索引、再检查上游”的启动流程；服务在同步期间保持可用。
- 本轮没有实现 GUI 数据源配置或自维护模式切换；它们属于已单独规划的下一阶段。
