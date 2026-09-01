# G0 运行就绪与可复现基线记录

> 日期：2026-08-26 · 阶段：G0 · 类型：只读探针与聚焦测试
> 计划：[G0–G4 实施计划](../plans/2026-08-26-g0-g4-implementation-and-stage-gates.md) · 控制面：[CURRENT_CONTROL.md](../CURRENT_CONTROL.md)

## 执行范围

本次只验证当前代码/容器/索引是否可观察、可连接、可测试；没有创建、删除或重建 Docker，没有写入数据库，没有解除语料冻结，没有调用付费 API。

## 结果

| 检查 | 结果 | 证据 |
|---|---|---|
| 当前分支 | `main` | `git branch --show-current` |
| 当前 HEAD | `22191bfaed62c4f51c36c8f0e0445394976a7e08` | `git rev-parse HEAD` |
| 工作树 | 有 81 项修改/未跟踪状态 | `git status --short \| wc -l`；不能视为干净发布源 |
| Docker app | running / healthy | `docker compose ps`、`docker inspect` |
| Docker Neo4j | running / healthy | `docker compose ps`、`docker inspect` |
| `/health` | HTTP 200 | 约 2.97s；`neo4j_connected=true`、graph readiness `ready` |
| `/dashboard/status` | HTTP 200 | 约 0.30s；活动 generation 可见 |
| 活动索引 | `gen-20260821T074117-404548ad` | `/health` |
| Chroma | 4133 chunks | `/health` |
| 当前语料 | `frozen`，最新 `2026-08-21` | `/dashboard/status` |
| 连接状态 | Neo4j ready；hybrid；DeepSeek configured | 两个端点返回值 |
| 聚焦 readiness 测试 | 18 passed | `.venv/bin/python -m pytest -q test_release_package test_health_readiness test_runtime_database_reconnect` |
| 合同与路由聚焦测试 | 25 passed，三组 exit code 均为 0 | corpus contract/index generation 10；consistency/entity registry 6；product routing 9 |
| 评估输入用途 | 已冻结 | [G0 evaluation manifest](../evals/g0-evaluation-freeze-manifest-2026-08-27.json) |

## 发现与判断

1. 本机 Docker 权限在升级读取后可用；此前 sandbox 中的 socket `permission denied` 是执行环境限制，不是容器故障。
2. 8001 当前可用，且实际图数据库探针通过；不能从此推出 Agent、自动同步或发布已通过。
3. 当前源代码工作树不干净，HEAD 不能独立复现运行结果；这是 G0 的发布阻塞项，但不是立即改代码的理由。
4. Chroma/Neo4j 当前处于 frozen/hybrid，满足“先调现有系统”的约束；本记录不改变正式数据。
5. 12 条旧 golden 只作可见校准；15 条已评分样本只作回归；20 条 query-only holdout 在独立标签封存前不能声称盲测成绩。

## G0 决定

**状态：通过，可进入 G1 的确定性实现；独立盲测标签仍是 G2 评分前置条件。**

已通过：现有 Docker、Neo4j、8001、活动索引和 18 条聚焦 readiness 测试可工作。

已知限制：工作树有大量未提交改动，HEAD 不能单独复现当前运行源；该问题继续阻塞 G4 发布，但不阻塞在冻结数据上完成 G1/G2。20 条 holdout 尚无独立封存标签，因此不得用于调参或发布质量声明。

## 下一步

进入 G1：先在现有实体模块中完成最小的“已知主体快速匹配 → 未知候选隔离 → 有证据才晋级 → 下次复用/可撤销”闭环；不重试 Docker，不重建索引。
