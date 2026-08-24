# GitHub Actions、唯一编号与 RAG 入库链路审计

> 日期：2026-08-24
> 审查角色：Terra（只读质量与方向审查）
> 复核结论：**公开制品链路 PASS；本地数据库更新为部署边界内的条件 PASS。** GitHub Action 负责规范化、ATR 编号与搜索制品；本地 Docker 在获取新语料后负责 Chroma/Neo4j 入库。

## 用户期望

每次 GitHub Actions 抓取后，应把日报中的每条信息规范化为独立记录，分配稳定的 `ATR-YYYYMMDD-XXXXXX` 编号，并让浏览搜索、Chroma 向量库和 Neo4j 图谱读取同一份规范化结果。周报和月报只供浏览，不参与主检索索引。

## 当前真实链路

```mermaid
flowchart LR
  UPSTREAM[上游 Pages] --> SYNC[rag.sync_corpus]
  SYNC --> RAW[日报 / 周报 / 月报 / topic-pool]
  RAW --> COMMIT[提交语料制品]
  COMMIT --> PAGES[部署 Pages]

  RAW --> NORMALIZE[规范化 + ATR 编号]
  NORMALIZE --> SEARCH[浏览搜索索引]
  SEARCH --> COMMIT
  COMMIT --> LOCAL[本地 Docker 同步]
  LOCAL --> VECTOR[Chroma generation]
  LOCAL --> GRAPH[Neo4j Observation / Content]
```

- 托管工作流下载语料后运行 `pnpm manifest`，统一生成 ATR 编号和 `digests/search-index.json`，随后重建 corpus contract，校验通过才允许提交。
- 自维护工作流运行 `pnpm digest`；该命令由采集、日报生成和 `pnpm manifest` 串联，因此使用同一编号与搜索制品合同。设置 `CORPUS_MODE=self_managed` 后每日运行，并通过专用分支与自动 PR 发布。
- 稳定 ATR 编号与歧义身份拒绝逻辑位于 `src/search-document.ts`；同日碰撞会失败，不会静默覆盖。
- 本地运行时具备 staging、generation 切换和图谱更新能力，但当前先发布向量 generation，之后才更新 Neo4j；图谱失败时只标记失败，不会回退已激活的向量 generation（`rag/server.py:376-429`）。
- 日报以原子条目进入向量库，Markdown 不再重复切块；这部分边界正确（`rag/ingest.py:383-404`）。周报/月报保持只供浏览。

## 已实现事实与证据边界

### 已实现

- 日报条目可生成稳定 ATR 编号。
- 同日精确重复可聚合，歧义身份可以 fail closed（拒绝静默合并）。
- 日报以独立条目向量化；Markdown、周报、月报不进入主向量索引。
- 本地运行时有向量 generation、最后可用版本和 Neo4j 单日事务相关实现及测试。

### 仍然存在的部署边界

- GitHub Action 不会跨互联网直接修改用户电脑里的 Chroma/Neo4j；本地服务同步新公开制品后才进行索引。这是安全边界，不是遗漏。
- 云端成功表示“语料与搜索制品可发布”，本地系统状态才表示“向量与图谱已激活”；两者必须分别观测。

## 最小修复顺序

1. **P0：补齐公开语料链路。** hosted sync 下载 `topic-pool.json` 后，必须运行统一规范化器，重建并校验 `search-index.json`，校验通过后才允许提交与部署。
2. **P0：明确自动化边界。** GitHub Actions 负责“公开语料与搜索制品”；本地 Docker 服务负责“Chroma/Neo4j 入库”。两者通过可验证的 corpus manifest/generation contract 连接，不能再把 Pages 成功等同于 RAG 成功。
3. **P0：原子激活。** Chroma staging、Neo4j 写入和一致性校验全部通过后，才切换 active generation；失败继续使用旧 generation。
4. **P1：统一规范化器。** TypeScript 与 Python 共用同一数据契约、编号规则和隔离报告；缺字段、身份冲突必须进入 quarantine（隔离清单），不能静默跳过。
5. **P1：补齐 CI。** 把 generation、corpus update、图事务、唯一编号和周/月报排除规则纳入 P0 检查；workflow 安装完整开发测试依赖，而不只安装 pytest。

## 自动更新恢复 Gate

只有以下证据全部通过，才恢复自动更新：

1. `dry-run` 规范化覆盖率与隔离报告通过；
2. 新日报每条记录具有唯一稳定 ATR 编号；
3. 浏览搜索索引覆盖所有合格日报条目；
4. shadow generation 中 Chroma/Neo4j 数量与身份一致；
5. 故障注入证明任何一步失败都不会切换 active generation；
6. 默认分支干净环境 CI 通过。

## 产品结论

现有链路已明确拆为“云端公开制品生产”和“本地数据库激活”两个阶段。后续新增语料只需接入统一来源注册表并产出同一 `topic-pool` 合同，不应再修改 ATR 编号、页面跳转或 RAG 主架构。
