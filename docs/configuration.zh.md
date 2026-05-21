# 配置帮助文档

本文是查表式配置手册。新手完整路径见 [新手启用指南](getting-started.zh.md)。

不要把真实 token 写进 README、提交记录、聊天内容或 `.env.example`。本地用环境变量，线上用 GitHub Actions Secrets。

官方参考：

- DeepSeek API 文档：https://api-docs.deepseek.com/zh-cn/
- GitHub Actions Secrets：https://docs.github.com/en/actions/how-tos/write-workflows/choose-what-workflows-do/use-secrets
- GitHub Personal Access Token：https://docs.github.com/authentication/keeping-your-account-and-data-secure/creating-a-personal-access-token
- GitHub Pages Quickstart：https://docs.github.com/en/pages/quickstart
- Product Hunt API：https://www.producthunt.com/v2/docs
- Telegram Bot：https://core.telegram.org/bots/features
- Telegram sendMessage：https://core.telegram.org/bots/api#sendmessage
- 飞书自定义机器人：https://open.feishu.cn/document/client-docs/bot-v3/add-custom-bot

## Pages URL

当前仓库名是 `AI-TREND-RADAR`，GitHub Pages 推荐 URL 是：

```text
https://conradgui.github.io/AI-TREND-RADAR
```

通知和 RSS 的链接应保持同一个路径。不要混用小写 `ai-topic-radar`，否则 Pages 链接可能因为路径大小写不一致而打不开。

## DeepSeek

本地临时配置：

```bash
export LLM_PROVIDER=deepseek
printf "DeepSeek API key: "
read -r -s DEEPSEEK_API_KEY
printf "\n"
export DEEPSEEK_API_KEY
```

如果账号使用特定模型 ID：

```bash
export DEEPSEEK_MODEL=your_deepseek_model_id
```

运行：

```bash
pnpm digest
```

macOS 剪贴板方式：

```bash
export LLM_PROVIDER=deepseek
export DEEPSEEK_API_KEY="$(pbpaste)"
pnpm digest
```

GitHub Actions Secret 名称：

```text
DEEPSEEK_API_KEY
```

## GitHub Token

Actions 中 `${{ secrets.GITHUB_TOKEN }}` 会自动提供，一般不需要手动创建。

本地运行时，如果遇到 GitHub API 403，可以配置个人 token 提高限流：

```bash
printf "GitHub token: "
read -r -s GITHUB_TOKEN
printf "\n"
export GITHUB_TOKEN
```

如果需要让脚本创建 digest issue：

```bash
export DIGEST_REPO=Conradgui/AI-TREND-RADAR
```

## Product Hunt

Product Hunt 用于补充 AI 产品发布信号。未配置时会跳过，不阻断主报告。

```bash
printf "Product Hunt token: "
read -r -s PRODUCTHUNT_TOKEN
printf "\n"
export PRODUCTHUNT_TOKEN
```

GitHub Actions Secret 名称：

```text
PRODUCTHUNT_TOKEN
```

## Telegram

需要两个值：

- `TELEGRAM_BOT_TOKEN`：从 BotFather 创建 bot 后获得。
- `TELEGRAM_CHAT_ID`：目标用户、群组或频道 ID。

本地测试：

```bash
printf "Telegram bot token: "
read -r -s TELEGRAM_BOT_TOKEN
printf "\n"
export TELEGRAM_BOT_TOKEN

printf "Telegram chat id: "
read -r TELEGRAM_CHAT_ID
export TELEGRAM_CHAT_ID

export PAGES_URL=https://conradgui.github.io/AI-TREND-RADAR
pnpm notify
```

GitHub Actions Secrets：

```text
TELEGRAM_BOT_TOKEN
TELEGRAM_CHAT_ID
```

未配置时，`pnpm notify` 会跳过，不会让 workflow 失败。

## 飞书

飞书使用自定义机器人 webhook。多个 webhook 用英文逗号分隔。

本地测试：

```bash
printf "Feishu webhook url: "
read -r -s FEISHU_WEBHOOK_URLS
printf "\n"
export FEISHU_WEBHOOK_URLS

export PAGES_URL=https://conradgui.github.io/AI-TREND-RADAR
pnpm notify:feishu
```

GitHub Actions Secret：

```text
FEISHU_WEBHOOK_URLS
```

未配置时，`pnpm notify:feishu` 会跳过，不会让 workflow 失败。

## GitHub Actions Secrets

进入：

```text
Settings -> Secrets and variables -> Actions -> New repository secret
```

建议配置：

| Secret | 是否必需 | 用途 |
| --- | --- | --- |
| `DEEPSEEK_API_KEY` | 必需 | 生成日报摘要和 highlights |
| `PRODUCTHUNT_TOKEN` | 可选 | 启用 Product Hunt 数据源 |
| `TELEGRAM_BOT_TOKEN` | 建议 | Telegram 通知 |
| `TELEGRAM_CHAT_ID` | 建议 | Telegram 通知目标 |
| `FEISHU_WEBHOOK_URLS` | 建议 | 飞书通知 |
| `ANTHROPIC_API_KEY` | 可选 | 备用 LLM provider |
| `ANTHROPIC_BASE_URL` | 可选 | 备用 provider base URL |

GitHub CLI 写入 Secret 示例：

```bash
printf "DeepSeek API key: "
read -r -s DEEPSEEK_API_KEY
printf "\n"
printf "%s" "$DEEPSEEK_API_KEY" | gh secret set DEEPSEEK_API_KEY
unset DEEPSEEK_API_KEY
```

Telegram：

```bash
printf "Telegram bot token: "
read -r -s TELEGRAM_BOT_TOKEN
printf "\n"
printf "%s" "$TELEGRAM_BOT_TOKEN" | gh secret set TELEGRAM_BOT_TOKEN
unset TELEGRAM_BOT_TOKEN

printf "Telegram chat id: "
read -r TELEGRAM_CHAT_ID
printf "%s" "$TELEGRAM_CHAT_ID" | gh secret set TELEGRAM_CHAT_ID
unset TELEGRAM_CHAT_ID
```

飞书：

```bash
printf "Feishu webhook url: "
read -r -s FEISHU_WEBHOOK_URLS
printf "\n"
printf "%s" "$FEISHU_WEBHOOK_URLS" | gh secret set FEISHU_WEBHOOK_URLS
unset FEISHU_WEBHOOK_URLS
```

## GitHub Pages

进入：

```text
Settings -> Pages
```

推荐配置：

```text
Source: Deploy from a branch
Branch: main
Folder: / (root)
```

部署后访问：

```text
https://conradgui.github.io/AI-TREND-RADAR
```

每日主报告：

```text
https://conradgui.github.io/AI-TREND-RADAR/digests/YYYY-MM-DD/ai-topic-radar.html
```

RSS：

```text
https://conradgui.github.io/AI-TREND-RADAR/feed.xml
```

## 输出开关

默认只生成中文主报告：

```bash
pnpm digest
```

生成源级中文报告：

```bash
SAVE_SOURCE_REPORTS=1 pnpm digest
```

生成中英文源级报告：

```bash
REPORT_LANGS=zh,en SAVE_SOURCE_REPORTS=1 pnpm digest
```

## 安全检查

提交前建议检查：

```bash
git status --short
git diff -- . ':!digests/**'
```

不要提交：

- `.env`
- 真实 API key
- Telegram bot token
- 飞书 webhook
- 私有社群内容
- 公司内部资料
- 未公开报告
