# 配置帮助文档

本文只写配置方法，不写任何真实 token。所有 key 都应该通过本地环境变量或 GitHub Actions Secrets 提供。

官方参考：

- DeepSeek API 文档：https://api-docs.deepseek.com/zh-cn/
- GitHub Actions Secrets：https://docs.github.com/en/actions/how-tos/write-workflows/choose-what-workflows-do/use-secrets
- GitHub Personal Access Token：https://docs.github.com/authentication/keeping-your-account-and-data-secure/creating-a-personal-access-token
- GitHub Pages Quickstart：https://docs.github.com/en/pages/quickstart
- Product Hunt API：https://www.producthunt.com/v2/docs
- Telegram Bot：https://core.telegram.org/bots/features
- Telegram sendMessage：https://core.telegram.org/bots/api#sendmessage
- 飞书自定义机器人：https://open.feishu.cn/document/client-docs/bot-v3/add-custom-bot

## 1. 本地配置 DeepSeek

当前终端临时配置，关闭终端后失效：

```bash
export LLM_PROVIDER=deepseek
printf "DeepSeek API key: "
read -r -s DEEPSEEK_API_KEY
printf "\n"
export DEEPSEEK_API_KEY
```

如果你的账号使用特定模型 ID：

```bash
export DEEPSEEK_MODEL=your_deepseek_model_id
```

运行：

```bash
pnpm digest
```

macOS 也可以先复制 key，再执行：

```bash
export LLM_PROVIDER=deepseek
export DEEPSEEK_API_KEY="$(pbpaste)"
pnpm digest
```

## 2. 本地配置 GitHub Token

GitHub token 用于提高 API 限流额度，并支持创建 issue。只做本地日报时也推荐配置。

```bash
printf "GitHub token: "
read -r -s GITHUB_TOKEN
printf "\n"
export GITHUB_TOKEN
```

如果需要让脚本创建 digest issue：

```bash
export DIGEST_REPO=owner/repo
```

## 3. 本地配置 Product Hunt

Product Hunt 用于补充 AI 产品发布信号。未配置时会跳过，不阻断主报告。

```bash
printf "Product Hunt token: "
read -r -s PRODUCTHUNT_TOKEN
printf "\n"
export PRODUCTHUNT_TOKEN
```

## 4. 本地配置 Telegram 通知

需要两个值：

- `TELEGRAM_BOT_TOKEN`：从 BotFather 创建 bot 后获得。
- `TELEGRAM_CHAT_ID`：目标用户、群组或频道 ID。

```bash
printf "Telegram bot token: "
read -r -s TELEGRAM_BOT_TOKEN
printf "\n"
export TELEGRAM_BOT_TOKEN

printf "Telegram chat id: "
read -r TELEGRAM_CHAT_ID
export TELEGRAM_CHAT_ID

export PAGES_URL=https://your-user.github.io/ai-topic-radar
pnpm notify
```

如果没有配置 token，`pnpm notify` 会跳过，不会报错中断。

## 5. 本地配置飞书通知

飞书使用自定义机器人 webhook。多个 webhook 用英文逗号分隔。

```bash
printf "Feishu webhook url: "
read -r -s FEISHU_WEBHOOK_URLS
printf "\n"
export FEISHU_WEBHOOK_URLS

export PAGES_URL=https://your-user.github.io/ai-topic-radar
pnpm notify:feishu
```

如果没有配置 webhook，`pnpm notify:feishu` 会跳过，不会报错中断。

## 6. 配置 GitHub Actions Secrets

在 GitHub 仓库页面进入：

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

如果已安装 GitHub CLI，也可以用命令写入 secret。命令会从标准输入读取，不会把 token 放进 shell 历史：

```bash
printf "DeepSeek API key: "
read -r -s DEEPSEEK_API_KEY
printf "\n"
printf "%s" "$DEEPSEEK_API_KEY" | gh secret set DEEPSEEK_API_KEY
unset DEEPSEEK_API_KEY
```

Telegram 示例：

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

飞书示例：

```bash
printf "Feishu webhook url: "
read -r -s FEISHU_WEBHOOK_URLS
printf "\n"
printf "%s" "$FEISHU_WEBHOOK_URLS" | gh secret set FEISHU_WEBHOOK_URLS
unset FEISHU_WEBHOOK_URLS
```

## 7. 配置 GitHub Pages

推荐配置：

```text
Settings -> Pages -> Build and deployment -> Source: Deploy from a branch
Branch: main
Folder: / (root)
```

部署后，访问：

```text
https://your-user.github.io/ai-topic-radar
```

每日主报告地址形如：

```text
https://your-user.github.io/ai-topic-radar/digests/YYYY-MM-DD/ai-topic-radar.html
```

RSS 地址：

```text
https://your-user.github.io/ai-topic-radar/feed.xml
```

## 8. 输出开关

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

## 9. 安全检查

提交前建议检查：

```bash
git status --short
git diff -- . ':!digests/**'
```

不要提交：

- `.env`
- 真实 API key
- 私有社群内容
- 公司内部资料
- 未公开报告
