# 配置说明

复制 `.env.example` 为 `.env`，或优先运行首次配置向导。`.env` 是本机私密配置，已被 Git 忽略。

## 最小可用配置

一次只选择一个 LLM Provider，并填对应的 key：

```dotenv
LLM_PROVIDER=deepseek
DEEPSEEK_API_KEY=你的真实密钥
NEO4J_PASSWORD=由配置向导生成的本地密码
```

支持 `deepseek`、`anthropic`、`openai`。切换 Provider 后双击 `update.command` / `update.bat`（或执行 `docker compose up -d --build`）让应用重新读取环境变量。

## 自动语料更新（Docker 默认开启）

Docker 部署会在 app 服务启动后立即检查一次公开语料，随后按
`RAG_CORPUS_UPDATE_INTERVAL_SECONDS` 周期检查（默认 6 小时）。发现新增或变更日报后，
服务在同一个进程内复用现有的同步、原子 generation、向量/图谱一致性检查和回滚入口；
不会创建第二个常驻更新服务，也不会让聊天请求等待抓取完成。

```dotenv
RAG_STARTUP_CORPUS_UPDATE_ENABLED=true
RAG_CORPUS_UPDATE_INTERVAL_SECONDS=21600
RAG_UPSTREAM_CORPUS_URL=https://conradgui.github.io/AI-TREND-RADAR
```

更新失败时保留上一次可用的运行时，并在 System 面板和 Docker 日志中记录失败状态。
只有明确要做固定语料评估时才将 `RAG_STARTUP_CORPUS_UPDATE_ENABLED` 设为 `false`；
直接运行 Python 进行离线评估时，默认仍是关闭自动更新的。

## 联网搜索

联网搜索不是每次回答都搜索互联网。默认策略是：先检索本地 RAG；仅在问题明确需要最新事实、用户主动要求联网、或内部证据不足时，再补充外部来源。Agent 页面和 System 面板的开关联动，关闭即不会调用外部搜索 Provider。

至少配置一个 Provider 后才可启用：

```dotenv
BRAVE_SEARCH_API_KEY=
# 或 TAVILY_API_KEY= / EXA_API_KEY= / SERPAPI_API_KEY=
```

外部来源会在回答和引用中标记为“联网搜索”。深度抓取是联网搜索开启后的子选项：它会读取少量高价值链接的全文，成本与延迟更高，因此默认关闭。

## API 鉴权（高级）

本地单用户仪表盘默认不设置 `RAG_API_KEY`，因为浏览器不会保存密钥。若将 API 提供给其他客户端：

1. 设置高熵 `RAG_API_KEY`；
2. 为客户端加上 `X-API-Key`；
3. 使用反向代理、HTTPS、访问控制和速率限制；
4. 不要直接把 Docker 端口暴露到公网。

具体安全提醒请看根目录 [`SECURITY.md`](../SECURITY.md)。

## GitHub Actions 与新闻源配置

本地 `.env` 只控制本机 Docker 和 Agent，不会自动上传到 GitHub。GitHub Actions 的密钥必须在仓库 `Settings → Secrets and variables → Actions` 单独配置。

- 默认托管同步不需要任何 Secret；可用 Repository Variable `UPSTREAM_CORPUS_URL` 覆盖公开语料地址。
- 自维护模式按 Provider 配置 `DEEPSEEK_API_KEY`、`ANTHROPIC_API_KEY`、`OPENAI_API_KEY` 或 `OPENROUTER_API_KEY` 中的一项。
- `PRODUCTHUNT_TOKEN`、`GITEE_TOKEN`、`AI_RADAR_GITHUB_TOKEN` 都是可选来源增强项。Product Hunt 在 `auto` 模式缺 Token 时跳过；Gitee 可匿名运行，Token 用于提高稳定性。
- 每个现有新闻连接器都可在根目录 `config.yml → sources` 中设置为 `auto`、`enabled` 或 `disabled`；运行 `pnpm sources:check` 可在产生模型费用前检查配置。
- 要让自维护抓取每日自动运行，再添加 Repository Variables：`CORPUS_MODE=self_managed` 与 `SELF_MANAGED_LLM_PROVIDER=<provider>`。不设置时默认继续使用无新闻源 Secret 的托管同步。

完整操作步骤、权限边界和故障定位见[GitHub 自动化与语料模式](github-automation.zh.md)。
