# Docker 语料版本一致性修复

## 用户可见问题

侧边栏列出 `2026-08-22/ai-topic-radar`，点击后返回 HTTP 404。

## 已验证根因

- 新镜像中的 `manifest.json` 已包含 2026-08-22 至 2026-08-24。
- Docker 持久化卷 `corpus_data` 只同步到 2026-08-21。
- `corpus_data:/app/digests` 会遮蔽镜像内更新后的 `/app/digests`。
- 原启动脚本没有比较、补齐或验证两份语料。

因此浏览目录和实际日报来自不同代次，构成版本分裂。

## 修复合同

1. 镜像构建时保存一份不可变的 bundled corpus（随镜像发布的语料快照）。
2. 启动时比较 bundled corpus 与持久化 runtime corpus 的生成时间，选择更新的一份。
3. bundled corpus 更新时只补齐持久化卷，不删除用户后续同步得到的新文件。
4. runtime corpus 更新时保留并公开 runtime 版本，不被旧镜像回滚。
5. 启动前逐条验证公开清单中的日报文件；缺失时拒绝带病启动。

## 范围边界

- 不删除或重建 Docker volume。
- 不修改 Neo4j 数据。
- 不重新生成向量或图索引。
- 仅修复浏览语料和清单的一致性。

## 验收证据

- 自动化测试：`rag/tests/test_corpus_volume_bootstrap.py`
- 同步持久化测试：`SyncCorpusTests::test_sync_corpus_persists_runtime_manifest_when_configured`
- 全量回归：870 tests + 36 subtests passed。
- 运行时验收：`/health`、`/manifest.json`、`/digests/search-index.json` 均返回 HTTP 200。
- 回归目标：2026-08-21、2026-08-22、2026-08-24 日报均返回 HTTP 200。
- Web UI 验收：刷新原故障 URL 后出现 `AI 热点选题池 2026-08-22`，不再显示“加载失败：HTTP 404”。
