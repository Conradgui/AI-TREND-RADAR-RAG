# 2026-09-01 G3 本地 Docker 自动更新验证

## 目标

把已确认的“GitHub Actions 发布公开语料、本地 Docker 自动完成同步与 RAG 更新”落成一个单进程闭环，且不要求用户每次手动点击、重建容器或删除数据卷。

## 本次实现

- Compose 默认启用 `RAG_STARTUP_CORPUS_UPDATE_ENABLED=true`。
- Docker app 启动后立即检查一次，之后按 `RAG_CORPUS_UPDATE_INTERVAL_SECONDS`（默认 21600 秒/6 小时）轮询。
- 启动检查和手动 `/corpus/update` 共用 `_run_corpus_update_once`、更新锁与 `_rebuild_runtime_index`，不创建第二个常驻更新进程。
- 上游地址统一由 `RAG_UPSTREAM_CORPUS_URL` 配置，默认使用公开 AI Trend Radar Pages。
- 图数据库不可用时不发布新的 vector-only generation；图更新或一致性校验失败时恢复旧 generation 和运行时，保留 staging 目录供诊断。
- macOS/Linux、Windows 配置向导和 `.env.example` 使用同一套默认自动更新参数。

## 小范围验证

| 检查 | 结果 |
|---|---:|
| 自动更新配置、调度和 Compose 契约 | 通过：31 项自动更新/配置/发布回归；工作流契约 15 项；同步单元测试 18 项 |
| 项目既有 P0 总检查 | Python P0 308 项通过；发布/工作流 pytest 51 项通过；前端 270 项、ESLint、Prettier、TypeScript 另行通过 |
| Python 编译与 `git diff --check` | 通过 |
| Compose 配置解析 | 通过 |
| 现有 app/Neo4j 容器复用 | 通过；仅重建 app 镜像，未删除或重建数据卷 |
| Neo4j 主动 readiness | 通过 |
| 真实启动自动同步 | 通过 |
| 真实双库一致性 | 通过 |

## 真实 Docker 证据

- 复用的 Neo4j 容器保持健康运行；app 容器仅因加载本轮代码重建并健康启动。
- `/health`：`configured=true`、`neo4j_connected=true`、`retriever_mode=hybrid`、`index_status=ready`。
- `/dashboard/status`：`corpus_mode=managed`、`corpus_auto_update_enabled=true`、`corpus_update_interval_seconds=21600`、上游为默认公开 Pages。
- 首次补齐长期未同步的公开语料后：`upstream_latest_date=2026-09-01`、`local_latest_date=2026-09-01`、`changed_date_count=8`、`ingested_date_count=11`、`error` 为空。
- Docker 日志记录：`Post-ingestion consistency check passed for 8 dates`，随后 `Managed corpus update finished: status=updated changed=8 ingested=11`。
- 活动 generation：`gen-20260901T103944-88f80847`；ChromaDB：`4734` 条；任务结束后 app CPU 回落到低位，Neo4j 保持约 0.8 GiB 运行内存量级。

## 边界与未决项

本记录只证明本地 Docker 自动更新实现和一次真实同步通过，不等于 G3 整体 Gate 已通过。clean clone 与发布合同已在 [main 分批发布记录](2026-09-01-main-release-and-clean-clone.md) 中补充通过。仍待：

1. 在 GitHub Runner 上执行一次受控 workflow dry-run/PR 路径并保存证据；
2. 用一个新日期完成一次单日期 canary，确认发布、索引和回滚行为。

之前的 P0 失败来自当前工作树中已存在的 `digests/search-index.json` 与 `corpus-manifest.json` 生成摘要漂移；在 rebase 到远端最新 main 后，完整 P0 已通过。原本的本地生成文件仍以 `stash@{0}` 保留，未覆盖、删除或推送。

在上述 Runner 与单日期证据完成前，不扩大来源、不执行大规模付费测试、不删除 Neo4j/RAG 数据卷，也不宣称项目已通过 G3。

## 下一步

继续使用现有容器和数据，不再重复首次全量补齐；优先完成一次真实 Runner 与单日期 canary。后续无变化轮询只执行来源检查，不会重复 embedding 已存在的条目。
