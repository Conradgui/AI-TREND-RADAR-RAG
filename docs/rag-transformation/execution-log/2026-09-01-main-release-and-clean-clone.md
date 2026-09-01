# 2026-09-01 main 分批发布与 clean clone 验证

## 目标

把现有项目变更安全推送到 GitHub `main`，避免单个宽范围提交阻塞审查；随后在全新临时目录验证用户拉取后的基础交付物和语料合同。

## 发布结果

- 已创建本地备份引用 `split-backup-6481d87`，原始宽提交未丢失。
- 已将项目拆为 13 个职责清晰的提交并逐批推送到 `main`，最终提交为 `ff14872`；其中最后一个提交只回写发布验证记录。
- 提交职责依次覆盖：Agentic RAG 运行时、Docker/启动器、Web UI、架构规范、阶段证据、各实验轮次评估快照。
- 未提交或推送本地旧生成索引 `digests/search-index.json`；该文件保留在 `stash@{0}`。
- 未删除或重建 Neo4j/RAG 数据卷。

## Clean clone 结果

使用 HTTPS 在隔离临时目录执行浅克隆：

```text
/tmp/ai-trend-radar-clean.Yn6t06
HEAD = 1d3bda9d6addba89348fae940e64ee19c635a4a1
随后追加文档提交 `ff1487273431d107de450cd21815e1ef07d2dd53`，未改变运行代码。
```

验证结果：

| 检查 | 结果 |
|---|---:|
| clean clone 的分支与最终 main SHA | 通过 |
| `python -m rag.corpus_contract --check-existing` | 通过，204 个公开语料文件，revision `6800369a…` |
| `NEO4J_PASSWORD=clean_clone_check docker compose config --quiet` | 通过 |
| README、Compose、start、doctor 文件存在且非空 | 通过 |

## 完整质量检查

- `pnpm rag:check:p0`：Python P0 308 项通过，发布/工作流 pytest 51 项通过。
- 前端 Vitest 270 项通过；ESLint、Prettier、TypeScript 均通过。
- GitHub REST Actions 查询因匿名 API rate limit 被拒；本机 `gh` token 失效，因此没有把 Runner 状态冒充为已通过。

## 决定

本次 main 发布与 clean clone 通过；G3 仍保留“真实 Runner + 单日期 canary”两个独立证据条件。后续不重建 Docker、不重复全量同步，只补这两个证据。
