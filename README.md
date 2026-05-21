# AI Topic Radar

面向 AI 内容运营和产品调研的热点选题监控工具。它会每天抓取公开 AI 信号，生成一份中文“值得写、值得测、值得深挖”的选题池，并通过 HTML、Web UI、RSS、Telegram、飞书和 GitHub Actions 分发。

本项目基于 [`duanyytop/agents-radar`](https://github.com/duanyytop/agents-radar) 改造。

## 5 分钟理解

### 它解决什么问题？

每天 AI 信息源很多：新模型、新产品、开源项目、论文、Hacker News 讨论、大厂官网发布、社区文章。AI Topic Radar 把这些公开信号聚合成一个可操作的内容选题池，帮助你判断：

- 今天哪些 AI 话题值得优先深挖？
- 哪些产品或开源项目值得进入选题池？
- 哪些信号还不够成熟，只需要观察？
- 哪些数据源失败了，应该怎么修？

### 最终会产出什么？

默认运行后会生成：

| 文件 | 用途 |
| --- | --- |
| `digests/YYYY-MM-DD/ai-topic-radar.html` | 主报告，可双击打开，也适合通过 GitHub Pages 分享 |
| `digests/YYYY-MM-DD/ai-topic-radar.md` | Markdown 版本，便于复制到文档、社群或编辑器 |
| `digests/YYYY-MM-DD/topic-pool.json` | 结构化选题池，保留分数、分类、动作、理由和证据 |
| `manifest.json` | 历史 Web UI 索引 |
| `feed.xml` | RSS 订阅源 |

默认只生成中文主报告。英文报告和源级报告仍然支持，但需要显式开启。

### 适合谁？

- AI 内容运营：每天做热点日报、社群内容、选题池。
- AI 产品研究：跟踪新产品、新模型和竞品动态。
- 技术/开源观察者：追踪 GitHub、Hacker News、arXiv、Hugging Face 信号。
- 作品集展示：展示一个公开、可复现、无公司内部资料的 AI 调研工作流。

## 最快跑通

你只需要 Node 22、pnpm 和一个 DeepSeek API key。

```bash
pnpm install --frozen-lockfile

export LLM_PROVIDER=deepseek
printf "DeepSeek API key: "
read -r -s DEEPSEEK_API_KEY
printf "\n"
export DEEPSEEK_API_KEY

pnpm digest
```

成功后打开：

```text
digests/YYYY-MM-DD/ai-topic-radar.html
```

如果想看历史看板：

```bash
pnpm serve
```

然后访问：

```text
http://localhost:8080
```

更完整的新手步骤见 [新手启用指南](docs/getting-started.zh.md)。

## 功能模块总览

| 模块 | 当前能力 | 默认是否启用 |
| --- | --- | --- |
| 数据采集 | GitHub Trending / Search、HN、Product Hunt、arXiv、Hugging Face、OpenAI / Anthropic 官网、Dev.to、Lobsters | 是，Product Hunt 需 token |
| LLM 摘要 | 支持 DeepSeek、Anthropic、OpenAI-compatible、OpenRouter、GitHub Copilot provider | 是，默认建议 DeepSeek |
| 选题评分 | 商业影响 40、热度 30、新鲜度 20、可写性 10 | 是 |
| 内容分类 | 政策监管、模型突破、AI 产品、行业落地、标杆企业与商业格局 | 是 |
| 主报告 | `ai-topic-radar.html`、`.md`、`topic-pool.json` | 是 |
| 源级报告 | `ai-web.md`、`ai-hn.md`、`ai-arxiv.md` 等 | 默认关闭，`SAVE_SOURCE_REPORTS=1` 开启 |
| 英文报告 | `*-en.md` | 默认关闭，`REPORT_LANGS=zh,en` 开启 |
| 历史 Web UI | `index.html` + `manifest.json` 浏览历史 Markdown | 是 |
| RSS | `feed.xml`，默认指向主报告 HTML | 是 |
| Telegram | 发送主报告、Web UI、RSS 链接和 highlights | 支持，需 token |
| 飞书 | 发送主报告、Web UI、RSS 链接和 highlights | 支持，需 webhook |
| GitHub Actions | 每日自动日报、周报、月报、CI | 是，需配置 Secrets |
| MCP server | `mcp/` 目录包含可部署的 MCP 服务代码 | 保留代码，不默认部署 |

## 数据源

默认链路会尝试抓取这些公开来源：

| 来源 | 内容 | 配置 |
| --- | --- | --- |
| GitHub Trending | 每日热门开源仓库 | 无需 token |
| GitHub Search | `llm`、`ai-agent`、`rag` 等关键词新 repo | 推荐 `GITHUB_TOKEN` 提高限流 |
| Hacker News | AI / LLM / Agent 相关社区讨论 | 无需 token |
| Product Hunt | AI 产品发布和投票讨论 | 需要 `PRODUCTHUNT_TOKEN` |
| arXiv | `cs.AI`、`cs.CL`、`cs.LG` 论文 | 无需 token |
| Hugging Face | 热门模型和下载/点赞信号 | 无需 token |
| OpenAI 官网 | 官方发布、产品更新、安全说明 | 无需 token |
| Anthropic 官网 | Claude、模型、安全和合作动态 | 无需 token |
| Dev.to | 技术社区文章 | 无需 token |
| Lobsters | 技术社区讨论 | 无需 token |

某个来源失败不会中断日报，主报告会在“数据源状态与修复提示”里说明原因。

## 选题评分

每条候选选题按 0-100 分评分：

| 维度 | 权重 | 含义 |
| --- | ---: | --- |
| 商业影响 | 40 | 是否影响产品、用户、企业、定价、落地或竞争格局 |
| 热度 | 30 | stars、votes、comments、likes、downloads 等来源热度 |
| 新鲜度 | 20 | 是否适合作为今日选题 |
| 可写性 | 10 | 是否有公开材料、明确标签和内容切入角度 |

动作阈值：

| 分数 | 动作 |
| ---: | --- |
| 80+ | 深挖 |
| 65-79 | 入池 |
| 50-64 | 观察 |
| < 50 | 归档 |

五类分类：

- 政策监管、社会影响与 AI 安全
- 模型与技术突破
- AI 产品与用户入口
- 企业落地与行业应用
- 标杆企业动向、商业格局与投融资

## 三种使用方式

### 方式一：本地使用

适合先跑通工具，生成一份本地 HTML 报告。

```bash
pnpm digest
```

打开：

```text
digests/YYYY-MM-DD/ai-topic-radar.html
```

### 方式二：GitHub Actions 自动日报

适合每天自动生成报告并提交回仓库。

1. 在 GitHub 仓库配置 `DEEPSEEK_API_KEY`。
2. 进入 `Actions -> Daily AI Topic Radar`。
3. 点击 `Run workflow`。
4. 成功后仓库会出现新的 `digests/YYYY-MM-DD/`、`manifest.json`、`feed.xml`。

### 方式三：GitHub Pages 公开分享

适合把 HTML 报告、历史 Web UI 和 RSS 公开给别人看。

1. 进入 `Settings -> Pages`。
2. Source 选择 `Deploy from a branch`。
3. Branch 选择 `main`，Folder 选择 `/ (root)`。
4. 访问：

```text
https://conradgui.github.io/AI-TREND-RADAR
```

主报告地址形如：

```text
https://conradgui.github.io/AI-TREND-RADAR/digests/YYYY-MM-DD/ai-topic-radar.html
```

## 自动化与通知

本仓库包含三条自动化 workflow：

| Workflow | 文件 | 默认时间 |
| --- | --- | --- |
| Daily AI Topic Radar | `.github/workflows/daily-digest.yml` | 每天 08:00 CST |
| Weekly AI Topic Radar | `.github/workflows/weekly-digest.yml` | 每周一 09:00 CST |
| Monthly AI Topic Radar | `.github/workflows/monthly-digest.yml` | 每月 1 日 10:00 CST |

Daily workflow 默认：

```yaml
LLM_PROVIDER: deepseek
REPORT_LANGS: zh
SAVE_SOURCE_REPORTS: "0"
```

通知能力：

- Telegram：`pnpm notify`，需要 `TELEGRAM_BOT_TOKEN` 和 `TELEGRAM_CHAT_ID`。
- 飞书：`pnpm notify:feishu`，需要 `FEISHU_WEBHOOK_URLS`。
- 邮箱早报：daily workflow 内置 SMTP 发送，需要 `SMTP_HOST`、`SMTP_USERNAME`、`SMTP_PASSWORD`、`EMAIL_TO`。
- 未配置 token 时会跳过，不会让日报失败。

配置细节见 [配置帮助文档](docs/configuration.zh.md)。

## 输出模式

默认模式：

```bash
pnpm digest
```

生成中文主报告、Markdown、JSON、manifest 和 RSS。

恢复源级中文报告：

```bash
SAVE_SOURCE_REPORTS=1 pnpm digest
```

同时生成中文和英文源级报告：

```bash
REPORT_LANGS=zh,en SAVE_SOURCE_REPORTS=1 pnpm digest
```

## 常用命令

| 命令 | 作用 |
| --- | --- |
| `pnpm digest` | 生成主报告 + manifest + RSS |
| `pnpm start` | 只生成日报文件 |
| `pnpm manifest` | 更新 `manifest.json` 和 `feed.xml` |
| `pnpm serve` | 本地查看历史 Web UI |
| `pnpm notify` | 发送 Telegram 通知 |
| `pnpm notify:feishu` | 发送飞书通知 |
| `pnpm weekly` | 生成周报 |
| `pnpm monthly` | 生成月报 |
| `pnpm test` | 单元测试 |
| `pnpm typecheck` | TypeScript 检查 |
| `pnpm lint` | ESLint |
| `pnpm format:check` | Prettier 检查 |

## 当前已验证模块

本地已验证：

- `pnpm typecheck`
- `pnpm test`：213 passed
- `pnpm lint`
- `pnpm format:check`
- `pnpm manifest`
- `pnpm notify`：无 Telegram token 时正常跳过
- `pnpm notify:feishu`：无飞书 webhook 时正常跳过

需要真实 token 或线上环境进一步验证：

- DeepSeek 真实摘要生成
- Product Hunt 数据源
- Telegram 实际发送
- 飞书实际发送
- GitHub Actions 线上定时运行
- GitHub Pages 首次部署

## FAQ

### 我只想最快看到一份报告，应该做什么？

配置 DeepSeek key 后运行 `pnpm digest`，打开 `digests/YYYY-MM-DD/ai-topic-radar.html`。

### 为什么浏览器访问 localhost 会失败？

历史 Web UI 需要先启动静态服务。运行 `pnpm serve` 后再打开 `http://localhost:8080`。单日 HTML 主报告不需要服务。

### GitHub API 403 是什么？

未配置 `GITHUB_TOKEN` 时会使用匿名 GitHub API，限流较低。本地可配置 `GITHUB_TOKEN`，Actions 中会自动提供 `${{ secrets.GITHUB_TOKEN }}`。

### Product Hunt 被跳过怎么办？

配置 `PRODUCTHUNT_TOKEN` 后重新运行。未配置时不会阻断主报告。

### 可以提交 `.env` 吗？

不可以。`.gitignore` 已忽略 `.env` 和 `.env.*`。请用环境变量或 GitHub Secrets。

## 作品集边界

本仓库只使用公开信息源和可复现代码，不包含公司内部资料、私有社群内容、API key 或未公开报告。它用于展示一个可公开复现的 AI 热点监控、选题评分、日报生成和自动分发工作流。
