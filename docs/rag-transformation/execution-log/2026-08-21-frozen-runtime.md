# 2026-08-21 固定语料运行证据

## 变更

- 新增 `RAG_STARTUP_CORPUS_UPDATE_ENABLED`，默认 `false`。
- Docker Compose 与 `.env.example` 同步采用冻结默认值。
- Server 在 frozen 模式不创建启动同步任务，只加载活动索引。
- `/dashboard/status` 返回 `corpus_mode=frozen`，并覆盖历史遗留的 `syncing` 展示状态。
- Web UI 显示“固定语料（自动更新已暂停）”。

## 验证

- 定向测试：`8 passed`。
- Docker app 与 Neo4j 均从原有数据卷启动，没有删除或重建数据卷。
- 启动日志：`Startup corpus update is disabled; serving the frozen active index`。
- 运行状态：Neo4j connected、index ready、root HTTP 200。
- 活动索引：`gen-20260821T074117-404548ad`，`4133` chunks，最新日期 `2026-08-21`。

## 边界

此前一次同步已在冻结决策落地前完成，因此当前活动索引已经包含 2026-08-21；本次冻结不做
回滚，也没有继续导入新内容。从本记录开始，后续分数变化应归因于系统策略或代码，而不是
语料变化。
