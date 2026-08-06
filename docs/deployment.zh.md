# 部署与数据迁移

本项目的推荐部署是 Docker Compose。它启动两个服务：浏览器访问的 `app` 和内部使用的 `neo4j`；默认只将 `app` 的 8001 端口映射到本机，Neo4j 不对宿主机公开。

## 正常启动与停止

首次使用请运行 `setup.command` / `setup.bat`。之后：

```bash
docker compose up -d
docker compose logs -f app
docker compose stop
```

`stop` 只停服务，保留数据库、向量索引和同步状态。每次 app 容器启动会：

1. 预热后的镜像先启动 Web 服务；
2. 从上游公开站点单向检查报告变化；
3. 在后台摄取新增或变更日期，首次运行优先处理最新日报；
4. 每成功处理一天就写入本地检查点；中断后只补未完成日期；
5. 同步失败时继续使用最后一次成功的本地索引。

`RAG_CORPUS_RECHECK_DAYS=30` 是近期修订重检窗口，不是“只保留 30 天语料”的限制。若本地长期未启动，更新程序会追平缺失日期。

### 首次索引期间可以做什么

页面和 System 面板会先可访问；System 中“语料同步：同步中”表示后台正在建立或补齐索引。此时可以浏览日报，Agent 只会基于已建立的证据回答。最新日报优先进入索引，历史语料随后补齐；不要把“同步中”误解成服务已经卡死。

## 旧版本迁移

旧版本可能只创建了一个固定名称的 Neo4j 容器。新版 Compose 不再使用 `container_name`，以避免克隆多个项目时发生名称冲突。

1. **不要先执行** `docker compose down -v`，否则会删除项目数据卷。
2. 在原项目目录运行 `docker volume ls`，记录原来的 Neo4j 卷名。
3. 先备份重要数据，再运行新版 `setup.command` / `setup.bat`。
4. 如需让新版复用旧数据卷，确认 Compose 项目名和卷名后再配置；不确定时优先让新版重建索引，旧容器和卷保持不动，验证无误后再手动清理。

这是一项刻意保守的策略：索引可以重建，错误删除旧研究数据则很难恢复。

## 重建索引的影响

重建会清空**本项目的本地** Neo4j 图谱、Chroma 向量库与同步状态，随后从本地/上游日报重新生成。它不会修改 AI-TREND-RADAR 上游的公开报告，也不会影响 Provider 账户。

适合重建的场景：索引一致性检查失败、向量模型/分块策略发生不兼容变更、需要彻底验证新摄取逻辑。代价是首次索引时间更长，期间 Agent 结果可能为空或不完整。

## Docker 排错入口

```bash
docker compose ps
docker compose config --quiet
docker compose logs --tail=200 app
docker compose logs --tail=200 neo4j
```

如果端口 8001 已被占用，可在 `.env` 添加 `RAG_PORT=8002` 后重新启动，再访问 `http://127.0.0.1:8002`。
