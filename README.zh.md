# AI Topic Radar

AI Topic Radar 是一个面向 AI 内容运营和产品调研的热点选题监控工具。它从 GitHub、Hacker News、Product Hunt、arXiv、Hugging Face、OpenAI / Anthropic 官网和技术社区等公开信息源抓取每日信号，输出一份中文“值得写、值得测、值得深挖”的 AI 选题池。

本项目基于 [`duanyytop/agents-radar`](https://github.com/duanyytop/agents-radar) 改造，保留 TypeScript 抓取管线、GitHub Actions 自动运行、RSS、通知和 Web UI 能力；本仓库重点新增中文内容选题评分、五类分类、动作建议、单文件 HTML 报告和结构化 JSON 选题池。

## 你会得到什么

默认运行后生成：

- `digests/YYYY-MM-DD/ai-topic-radar.html`：主报告，可双击打开，也可通过 GitHub Pages 分享。
- `digests/YYYY-MM-DD/ai-topic-radar.md`：同内容 Markdown，便于复制、归档和二次编辑。
- `digests/YYYY-MM-DD/topic-pool.json`：结构化选题池，保留分类、评分、动作、理由和证据。
- `manifest.json`：历史看板索引。
- `feed.xml`：RSS 订阅源。

默认只输出中文主报告。英文报告和源级报告仍保留，但需要显式开启。

## 快速开始

```bash
pnpm install --frozen-lockfile

export LLM_PROVIDER=deepseek
printf "DeepSeek API key: "
read -r -s DEEPSEEK_API_KEY
printf "\n"
export DEEPSEEK_API_KEY

pnpm digest
```

完成后打开：

```text
digests/YYYY-MM-DD/ai-topic-radar.html
```

如果要查看历史看板：

```bash
pnpm serve
```

然后访问：

```text
http://localhost:8080
```

## 数据源

默认链路会尝试抓取以下公开来源：

| 来源 | 用途 | 配置 |
| --- | --- | --- |
| GitHub Trending / Search | 开源项目、工具、模型和 repo 热度 | 推荐配置 `GITHUB_TOKEN` 提高限流 |
| Hacker News | 海外技术社区讨论 | 无需 token |
| Product Hunt | 新 AI 产品发布 | 需要 `PRODUCTHUNT_TOKEN` |
| arXiv | AI 论文和研究趋势 | 无需 token |
| Hugging Face | 热门模型 | 无需 token |
| OpenAI / Anthropic 官网 | 大厂官方发布 | 无需 token |
| Dev.to / Lobsters | 技术社区内容 | 无需 token |

某个来源失败不会中断整份日报，报告会在“数据源状态与修复提示”里记录原因。

## 选题评分

每个条目按 0-100 分评分：

| 维度 | 权重 | 含义 |
| --- | ---: | --- |
| 商业影响 | 40 | 是否影响产品、用户、企业、定价、落地或竞争格局 |
| 热度 | 30 | stars、votes、comments、likes、downloads 等来源热度 |
| 新鲜度 | 20 | 是否足够适合作为今日选题 |
| 可写性 | 10 | 是否有公开材料、明确标签和内容切入角度 |

动作阈值：

| 分数 | 动作 |
| ---: | --- |
| 80+ | 深挖 |
| 65-79 | 入池 |
| 50-64 | 观察 |
| < 50 | 归档 |

五类内容分类：

- 政策监管、社会影响与 AI 安全
- 模型与技术突破
- AI 产品与用户入口
- 企业落地与行业应用
- 标杆企业动向、商业格局与投融资

## 输出模式

默认模式：

```bash
pnpm digest
```

只生成中文主报告、Markdown、JSON、manifest 和 RSS。

恢复源级中文报告：

```bash
SAVE_SOURCE_REPORTS=1 pnpm digest
```

同时生成中文和英文报告：

```bash
REPORT_LANGS=zh,en SAVE_SOURCE_REPORTS=1 pnpm digest
```

底层生成入口仍可单独运行：

```bash
pnpm start
pnpm manifest
```

## 分发能力

AI Topic Radar 默认保留完整分发链路：

- GitHub Actions：每日定时运行，也支持手动触发。
- GitHub Pages / Web UI：`index.html` 读取 `manifest.json`，用于浏览历史报告。
- 单文件 HTML：每日主报告可直接打开和分享。
- RSS：`feed.xml` 默认优先收录主报告。
- Telegram：`pnpm notify` 发送主报告、Web UI 和 RSS 链接。
- 飞书：`pnpm notify:feishu` 发送主报告、Web UI 和 RSS 链接。

通知发送需要配置对应 token；未配置时脚本会跳过，不会让日报失败。

## GitHub Actions

Daily workflow 默认使用：

```yaml
LLM_PROVIDER: deepseek
REPORT_LANGS: zh
SAVE_SOURCE_REPORTS: "0"
```

需要在 GitHub 仓库里配置：

- `DEEPSEEK_API_KEY`：必填，用于 LLM 摘要和 highlights。
- `PRODUCTHUNT_TOKEN`：可选，启用 Product Hunt。
- `TELEGRAM_BOT_TOKEN`、`TELEGRAM_CHAT_ID`：可选但建议配置，用于 Telegram 通知。
- `FEISHU_WEBHOOK_URLS`：可选但建议配置，用于飞书通知。

完整步骤见 [配置帮助文档](docs/configuration.zh.md)。

## 常用命令

```bash
pnpm digest          # 生成主报告 + manifest + RSS
pnpm start           # 只生成日报文件
pnpm manifest        # 更新 manifest.json 和 feed.xml
pnpm serve           # 本地查看历史 Web UI
pnpm notify          # 发送 Telegram 通知
pnpm notify:feishu   # 发送飞书通知
pnpm test            # 单元测试
pnpm typecheck       # TypeScript 检查
pnpm lint            # ESLint
```

## FAQ

### 为什么默认不再生成很多 `.md` 文件？

默认读者只需要一份结构清晰的主报告。源级报告仍可用 `SAVE_SOURCE_REPORTS=1` 开启，用于排查和追溯。

### 为什么浏览器访问 `localhost` 会拒绝连接？

`index.html` 历史看板需要本地静态服务。先运行 `pnpm serve`，再打开 `http://localhost:8080`。单日主报告 `ai-topic-radar.html` 不需要服务，可直接双击打开。

### Product Hunt 被跳过怎么办？

配置 `PRODUCTHUNT_TOKEN` 后重新运行。未配置时不会阻断主报告。

### GitHub API 403 是什么？

未配置 `GITHUB_TOKEN` 时会使用匿名 GitHub API，限流较低。配置 token 后可显著减少 403。

### 可以把 token 放进 `.env` 吗？

可以本地使用，但不要提交。更推荐用终端 `read -r -s` 输入，或在 GitHub Actions 中使用 Secrets。

## 作品集边界

本仓库只使用公开信息源和可复现代码，不包含公司内部资料、私有社群内容、API key 或未公开报告。它用于展示一个可公开复现的 AI 热点监控、选题评分、日报生成和自动分发工作流。
