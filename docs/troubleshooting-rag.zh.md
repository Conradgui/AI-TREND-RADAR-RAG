# 故障排除

## 双击脚本后提示 Docker Desktop 未运行

启动 Docker Desktop，等待状态显示正在运行，再双击 `setup.command` / `start.command` 或 Windows 对应 `.bat` 文件。

## 页面无法打开或显示连接被拒绝

运行：

```bash
docker compose ps
docker compose logs --tail=200 app
```

若 8001 被其他服务占用，在 `.env` 添加 `RAG_PORT=8002`，执行 `docker compose up -d`，再访问新端口。

## 页面可打开，但 Agent 不可用

先在 System 面板确认 Provider 是否已配置。若没有，检查 `.env` 中选择的 `LLM_PROVIDER` 是否与非空 key 对应；改完运行 `docker compose up -d --build`。不要把 key 发到 Issue、截图或聊天记录里。

## Agent 回答很慢或超时

首次请求需要加载模型连接、检索本地索引，通常会比后续请求慢。先尝试更明确的问题；需要联网时，关闭深度抓取或等待外部 Provider 恢复。查看 `docker compose logs -f app` 可以区分 Provider、检索还是网络错误。

如果 System 面板显示“语料同步：同步中”，后台还在建立历史索引。最新日报会优先可用，但不要把尚未进入索引的旧报告当作“系统没有数据”。可继续浏览日报，或稍后再问覆盖更长时间范围的问题。

## 搜索不到 `Open AI`

报告侧栏搜索会忽略大小写、空格和常见分隔符，`Open AI` 与 `OpenAI` 应命中同类结果。若仍无结果，先清空搜索框确认报告目录已载入，再检查浏览器控制台与 `manifest.json` 是否有加载错误。

## 索引或数据库不一致

访问 `/health/consistency`，或查看 System 面板的状态。先保留现有卷和日志；只有确认需要时才按[部署文档](deployment.zh.md#重建索引的影响)重建本地索引。

## 找不到答案

本地 RAG 只知道已同步的上游报告。询问最新外部事实时，可在 Agent 开启联网搜索；外部内容会单独标记，不能代替内部日报的历史证据。
