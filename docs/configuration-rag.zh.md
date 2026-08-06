# 配置说明

复制 `.env.example` 为 `.env`，或优先运行首次配置向导。`.env` 是本机私密配置，已被 Git 忽略。

## 最小可用配置

一次只选择一个 LLM Provider，并填对应的 key：

```dotenv
LLM_PROVIDER=deepseek
DEEPSEEK_API_KEY=你的真实密钥
NEO4J_PASSWORD=由配置向导生成的本地密码
```

支持 `deepseek`、`anthropic`、`openai`。切换 Provider 后执行 `docker compose up -d --build` 让应用重新读取环境变量。

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
