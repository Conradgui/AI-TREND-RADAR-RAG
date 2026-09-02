# 2026-09-01 G3 Runner、发布幂等性与单日期 canary 收口

## 阶段目标

补齐 G3 最后可执行的独立证据：验证 GitHub Runner 的托管语料链路、PR/Pages 发布链路、无变化时的幂等行为，以及现有 Docker 后端的单日期更新入口。保持已有容器和数据卷，不重建、不删除、不重复全量同步。

## 证据总览

| 子关口 | 实际结果 | 原始证据 |
|---|---|---|
| GitHub Runner dry-run | 通过；验证 hosted corpus、工作流合同和上游变更计划成功，未发布 PR | [run 33504345648](https://github.com/Conradgui/AI-TREND-RADAR-RAG/actions/runs/33504345648) |
| GitHub Runner 正式发布路径 | 通过；校验、提交、PR 合并和 Pages 部署均成功 | [run 33504962102](https://github.com/Conradgui/AI-TREND-RADAR-RAG/actions/runs/33504962102) |
| 首次正式运行的异常发现 | 已定位；PR #11 只有派生元数据变化，没有日报源文件变化 | [PR #11](https://github.com/Conradgui/AI-TREND-RADAR-RAG/pull/11) |
| 幂等性修复后的 CI | 通过；工作流契约和 P0 测试均通过 | [run 33505517378](https://github.com/Conradgui/AI-TREND-RADAR-RAG/actions/runs/33505517378) |
| 修复后的 hosted no-op | 通过；明确记录“仅派生元数据变化，不需要 PR”，PR/Pages 均跳过 | [run 33505647996](https://github.com/Conradgui/AI-TREND-RADAR-RAG/actions/runs/33505647996) |
| Docker 单日期复核 | 通过；无变化时不写入、不切换 generation，服务和双库仍健康 | 见下文实时接口结果 |

## 发现与修复

第一次正式 Runner 路径在 `8294ed1` 上成功完成了语料校验、派生文件构建、PR 合并和 Pages 部署，但 PR #11 的四个变更文件全部是派生制品：

```text
corpus-manifest.json
digests/search-index.json
feed.xml
manifest.json
```

没有新的日报源文件。这说明工作流虽然“能发布”，但在无源数据变化时会被时间戳等派生元数据误触发，形成无意义 PR。该问题不是通过重跑解决，而是补了一个共享守门脚本：

```text
scripts/has-corpus-source-changes.sh
```

脚本只允许包含真实语料源文件的暂存差异进入提交；若只有 `manifest.json`、`feed.xml`、`corpus-manifest.json` 或 `digests/search-index.json` 变化，则撤销暂存、标记 `changed=false`，不推送分支、不创建 PR、不部署 Pages。托管来源和自维护来源两条工作流都使用同一守门逻辑，并由工作流合同测试锁定。

修复提交为 `bc9cd2171762e55b292151e92029279122d93609`，已推送 `main`。修复后的正式 Runner 运行显示：

```text
Only derived corpus metadata changed; no PR required
Push dedicated corpus branch: skipped
Create and merge corpus pull request: skipped
Deploy published corpus to Pages: skipped
```

## Docker 单日期 canary

当前公开上游和本地最新日期均为 `2026-09-01`，不存在可以安全执行“新日期首写”的源数据增量。因此没有把无变化检查冒充首写测试，而是执行了真实容器的单日期幂等复核：

```text
POST http://127.0.0.1:8001/corpus/update
{"days": 1, "dry_run": true}
→ status=dry_run, changed_dates=[], ingested_dates=[], error=""

POST http://127.0.0.1:8001/corpus/update
{"days": 1, "dry_run": false}
→ status=unchanged, changed_dates=[], ingested_dates=[], error=""
```

复核前后保持：

```text
Neo4j: healthy / runtime ready
ChromaDB: 4734 chunks
active generation: gen-20260901T103944-88f80847
index_status: ready
```

这证明单日期无变化时不会重复 embedding、不会切换活动 generation，且服务不会因为一次检查而失去双库连接。真实写入路径和失败后保留旧 generation 的证据，已记录在 [G3 本地 Docker 自动更新验证](2026-09-01-g3-managed-local-auto-update.md)：该次实际更新处理了 `8` 个变化日期、`11` 个入库日期，并通过双库一致性检查。

## 本地回归

```text
bash -n scripts/has-corpus-source-changes.sh                         PASS
YAML parse for .github/workflows/*.yml                                PASS
pytest rag/tests/test_workflow_contracts.py                           16 passed
targeted corpus/update/consistency/reconnect suite                    21 passed
git diff --check                                                       PASS
```

GitHub Actions 对 `bc9cd21` 的 CI 也通过了 actionlint、lint、format、typecheck、前端测试和 RAG P0 focused suite。

## Gate 决定

| 子关口 | 决定 |
|---|---|
| Runner 校验、PR、Pages 发布链路 | **PASS** |
| 无变化发布幂等性 | **PASS** |
| Docker 单日期无变化复核 | **PASS** |
| 新日期首写 canary | **待未来来源数据增量**，不是当前代码失败 |

因此 G3 当前结论是：**条件通过，可继续后续收敛；严格意义上的“新日期首写”观察项尚未关闭，不将 G3 写成无条件完全通过。** 该观察项只需在上游第一次出现新日期时由既有定时工作流自然产生证据，不需要现在重跑或重建环境。

## 2026-09-02 新日期检查

为推进“新日期首写”观察项，重新读取公开上游的 `manifest.json`，不修改本地语料、不伪造日期，也不重复触发已验证的无变化同步：

```text
upstream latest date: 2026-09-01
upstream generated: 2026-09-01T07:05:59.918Z
upstream date count: 105
local latest date: 2026-09-01
```

结论：截至 2026-09-02，上游尚未产生 `2026-09-02` 或更晚的公开日报，因此没有可安全执行的“新日期首写”样本。该观察项继续保持 `PENDING_EXTERNAL_INCREMENT`，不是代码失败；下一次真实日期出现后，应由现有定时工作流完成一次首写，并补录源文件、ATR、generation、双库一致性和失败恢复证据。

## 未做与恢复边界

- 未重建或删除 Docker 容器、Neo4j、ChromaDB 数据卷。
- 未删除旧语料、活动 generation 或用户配置。
- 未新增来源、未进行付费 API 测试、未修改 G4 发布范围。
- 上游出现新日期后，保留源数据、manifest、ATR、generation、双库一致性和失败恢复证据；若失败，继续保持旧 generation，不自动切换到不完整索引。
