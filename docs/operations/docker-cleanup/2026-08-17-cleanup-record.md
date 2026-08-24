# Docker 旧版本清理记录（2026-08-17）

> 状态：进行中。本文先记录事实和保护边界；只有在 Docker Engine 恢复、容器身份核验完成后，才会填写并执行删除清单。

## 目标

- 只保留当前工作仓库实际使用的 Docker 服务版本。
- 清理旧容器、旧镜像和不再使用的构建缓存。
- 保留当前 Neo4j、RAG 数据和语料数据卷，避免清理造成知识库丢失。
- 为被清理对象保留可审计记录，说明删除原因和恢复方式。

## 清理前事实

| 项目 | 已确认结果 |
|---|---|
| 当前工作仓库 | `/Users/conrad/Documents/Graph RAG :claude/AI-TREND-RADAR-RAG` |
| Docker Desktop 数据目录实际占用 | 约 9.5 GB |
| `Docker.raw` 显示大小 | 228 GB（稀疏文件逻辑上限，不等于实际占用） |
| 主机磁盘状态 | 228 GiB 总量、约 12 GiB 可用、使用率约 94% |
| Docker Engine | 当前不可连接，无法读取容器、镜像和卷清单 |
| 当前 Compose 服务 | `app`（8001 端口）与 `neo4j` |
| 必须保护的数据卷 | `rag_data`、`corpus_data`、`neo4j_data`（最终名称以 Compose 标签核验为准） |

## 安全边界

本轮明确不执行以下操作：

- 不删除或重建 `Docker.raw`。
- 不执行 Docker Desktop Factory Reset / Clean data。
- 不执行带 `--volumes` 的全局 prune。
- 不依据日志中出现的容器 ID 直接删除；必须先核验 Compose 工作目录、项目标签、镜像、端口和挂载卷。
- 不删除当前仓库正在使用的命名卷。

## 身份判定规则

“当前版本”需要同时满足以下证据中的多数，而不是只看容器名称：

1. Compose 标签中的工作目录等于当前工作仓库绝对路径。
2. Compose service 为当前 `docker-compose.yml` 中的 `app` 或 `neo4j`。
3. 应用服务映射端口为 `8001`，并能通过健康检查。
4. 挂载卷与当前项目的数据卷一致。
5. 容器使用的镜像与当前 Compose 构建结果一致。

其余对象只有在确认不属于当前版本、且不承载唯一数据后，才会进入删除清单。

## 核验结果与保留对象

Docker Engine 已于 2026-08-17 恢复。以下对象通过 Compose 工作目录、项目标签、服务名称和挂载关系核验，必须保留：

| 类型 | 名称 / ID | 依据 |
|---|---|---|
| 应用容器 | `ai-trend-radar-rag-app-1` / `52724f14f8d5` | Compose 工作目录为当前仓库，service=`app`，挂载当前 `corpus_data` 与 `rag_data` |
| Neo4j 容器 | `ai-trend-radar-rag-neo4j-1` / `e10b7e29c658` | Compose 工作目录为当前仓库，service=`neo4j`，挂载当前 `neo4j_data` |
| 应用镜像 | `ai-trend-radar-rag-app:latest` / `e3693385eaba` | 当前应用容器使用 |
| Neo4j 镜像 | `neo4j:5` / `db03e618d0cd` | 当前 Neo4j 容器使用 |
| 数据卷 | `ai-trend-radar-rag_rag_data` | 当前 RAG / Chroma 数据，约 1.333 GB |
| 数据卷 | `ai-trend-radar-rag_neo4j_data` | 当前 Neo4j 数据，约 557.1 MB |
| 数据卷 | `ai-trend-radar-rag_corpus_data` | 当前语料，约 22.03 MB |
| 匿名卷 | `67320da5a193…` | 当前 Neo4j 容器仍挂载，必须保留 |
| 网络 | `ai-trend-radar-rag_default` | 当前项目网络 |

> 注：当前两项容器在 Docker Desktop 重启后显示为 `Exited (137)`，这代表被运行时强制终止，不代表应删除；清理后会用当前 Compose 配置重启。

## 精确删除清单

以下对象均不属于当前仓库运行栈，且其命名、Compose 工作目录或项目标签明确表明它们是临时验证或历史旧版本。删除容器和镜像可通过重新执行相应 Compose 构建恢复；删除的验证数据卷不保留唯一生产数据。

### 历史容器

| 容器 | ID | 原项目 | 删除理由 |
|---|---|---|---|
| `ai-trend-radar-rag-bootstrap-check-neo4j-1` | `0e3d6a3d7b48` | `/private/tmp/ai-trend-radar-rag-bootstrap-check...` | 干净克隆验证残留 |
| `ai-trend-radar-rag-release-check-neo4j-1` | `8d3ad53d02da` | `ai-trend-radar-rag-release-check` | 发布验证残留 |
| `ai-trend-radar-rag-claude` | `b8e1f640c940` | 历史手工容器 | 与当前 Compose 栈无标签关联，创建于 2026-06-26 |

### 验证用镜像

| 镜像 | ID | 删除理由 |
|---|---|---|
| `ai-trend-radar-rag-bootstrap-check-app:latest` | `06df6b616903` | 干净克隆验证构建 |
| `ai-trend-radar-rag-clean-clone-retry-app:latest` | `129c73869284` | 干净克隆重试构建 |
| `ai-trend-radar-rag-clean-clone-check-app:latest` | `d8ed2a75c7f7` | 干净克隆验证构建 |
| `ai-trend-radar-rag-release-check-app:latest` | `e9a498d225eb` | 发布验证构建 |

### 验证 / 历史数据卷

- `ai-trend-radar-rag-bootstrap-check_neo4j_data`
- `ai-trend-radar-rag-bootstrap-check_rag_data`
- `ai-trend-radar-rag-clean-clone-check_neo4j_data`
- `ai-trend-radar-rag-clean-clone-check_rag_data`
- `ai-trend-radar-rag-clean-clone-retry_neo4j_data`
- `ai-trend-radar-rag-clean-clone-retry_rag_data`
- `ai-trend-radar-rag-release-check_neo4j_data`
- `ai-trend-radar-rag-release-check_rag_data`
- `ai-trend-radar-rag-claude_neo4j_data`
- 与上述旧容器绑定的匿名卷：`68d98b19af1c…`、`2002fbb868cb…`、`fcf78cfe90a5…`
- 当前没有链接的匿名卷：`606e4c4b8a34…`、`860d931a9904…`、`b745dad9ea0f…`、`c7a7fcea71e7…`、`d4ef9e3dfd59…`、`f561c0e3c2c7…`

### 验证网络与构建残留

- `ai-trend-radar-rag-bootstrap-check_default`
- `ai-trend-radar-rag-release-check_default`
- 所有悬空镜像层（`<none>:<none>`）
- 不再被当前构建引用的 BuildKit 缓存（清理前约 1.911 GB）

## 可预期效果

清理将主要回收：多个历史 Neo4j 数据卷（约 2 GB 级）、约 1.9 GB 构建缓存、验证镜像独占层、容器可写层和悬空层。Docker 的虚拟磁盘文件可能不会立即缩小，但 Docker 引擎可用空间会立即释放，随后由 Docker Desktop 按需回收给宿主机。

## 计划执行顺序

1. 恢复 Docker Engine，不重建任何服务。
2. 获取容器、镜像、数据卷、网络和构建缓存的完整只读清单。
3. 通过 Compose 标签和挂载关系确认当前版本。
4. 将精确删除对象、占用空间、删除原因和恢复方式写入本文。
5. 先向用户展示删除清单，再执行精确清理。
6. 验证当前服务、Neo4j、ChromaDB、8001 页面与 Agent 链路。
7. 对比清理前后 Docker 占用和主机可用空间。

## 删除执行记录

### 已执行

- 已删除 3 个历史容器：bootstrap-check、release-check、`ai-trend-radar-rag-claude`。
- 已删除 18 个验证 / 历史 / 无链接匿名数据卷；当前项目的 `rag_data`、`neo4j_data`、`corpus_data` 与当前匿名卷均保留。
- 已删除 2 个验证网络。
- 已删除 4 个验证应用镜像。
- 已清理 611.6 MB 悬空镜像层。
- 已清理 1.911 GB BuildKit 构建缓存。

### 清理后验证

| 验证项 | 结果 |
|---|---|
| 当前容器数 | 2 个，均为 `ai-trend-radar-rag` 当前 Compose 栈 |
| 应用容器 | `healthy`，端口 `8001` 已发布 |
| Neo4j 容器 | `healthy` |
| `GET http://127.0.0.1:8001/health` | 成功：`status=ok`、`neo4j_connected=true`、`chromadb_chunks=3718` |
| Docker 清理后镜像占用 | 1.32 GB，0B 可回收 |
| Docker 清理后容器占用 | 548.4 MB，0B 可回收 |
| Docker 清理后本地卷占用 | 1.914 GB，均为当前栈所需数据 |
| Docker 清理后构建缓存 | 0B |
| 宿主机可用空间 | 约 18 GiB（清理前约 12 GiB） |

## 恢复说明

- 被删除的容器、镜像和构建缓存均可通过相应仓库重新执行 Compose 构建恢复。
- 被删除的验证数据卷属于临时验证环境，不是当前 RAG 索引或 Neo4j 数据。
- 当前数据卷完整保留；若以后需要停止服务，可执行 `docker compose stop`，不应使用带 `-v` 的命令，除非明确希望删除知识库。
