# Stage 4 执行记录：统一时间语义

日期：2026-08-12

## 阶段目标

解决“日报收录日期被误当成原文发布日期”的结构性问题，使最近发布、旧文重现和跨日观测可以被分别表达和检索。

## 已实现契约

- `publication_date`：原始内容发布日期；未知时保持 `null`。
- `report_date`：条目进入哪一天日报。
- `observed_at`：该次日报观测发生的日期。
- `ingested_at`：向量或图记录真正写入本地存储的时间。
- `effective_date`：检索排序使用的兼容日期。
- `effective_date_basis`：明确记录使用发布日期，还是降级使用日报日期。

历史语料只从显式 `发布时间：YYYY-MM-DD` 字段恢复日期，不从标题或正文猜测。异常日期会进入诊断，不能静默成为“最近”。

来源日期角色也已分开：RSS/Feed 明确提供的发布日期进入 `publication_date`；sitemap `lastmod`、GitHub `pushedAt`、Hugging Face `lastModified`、Gitee `updatedAt` 统一进入 `source_updated_at`，不得冒充发布日期。历史 `legacy_evidence` 在 Agent 提示中显示为“历史记录日期（旧语料字段，未独立核验）”。

## 数据通路

同一时间契约已进入：

1. TypeScript 规范搜索文档；
2. Python 运行时语料和 Chroma 元数据；
3. lexical SQLite；
4. Neo4j Observation；
5. Hybrid/Graph 结果；
6. citation、Gateway 排序和 Agent 证据提示。

同一内容跨日报再次出现时，`content_id` 保持稳定，`occurrence_id` 和 `observed_at` 随日报变化，保留纵向趋势观测。

## 语料审计

- 当前规范文档：3663 条。
- 最新日报：2026-08-12。
- ATR 编号覆盖：100%。
- 影子索引输出：3663 条向量 + 3663 条 lexical 记录。
- 复用已有 embedding：3663 条；新增 embedding：0 条。
- 未映射活跃原子记录：0 条。

早期影子构建曾只有 3550 条，明确丢失 2026-08-11 至 2026-08-12 的 113 条内容，因此未激活。根因是同步日报写在可丢弃的容器层，重建镜像后规范语料回退，而持久索引仍保留新数据。

已修复 Docker 边界：新增 `corpus_data:/app/digests` 持久卷；先把容器内完整日报备份到临时目录，再重建应用容器并回填。Neo4j 和现有索引卷均未删除。

## 验证证据

- `pnpm exec vitest run`：250 个 TypeScript 测试通过（本阶段全量结果）。
- `pnpm exec vitest run src/__tests__/search-document.test.ts`：17/17 通过。
- `pnpm exec tsc --noEmit`：通过。
- `.venv/bin/python -m pytest ...`：37/37 通过。
- `.venv/bin/python -m unittest ...`：54/54 通过。
- Stage 4 Python 定向测试合计：91 个通过。
- 五类时间边界：结构化发布日期、旧文新收录、缺失发布日期、异常日期、同内容跨日观测均有测试。
- 服务健康：Neo4j 已连接、hybrid ready、活跃索引 3663 条。

## Stage Gate 与正式激活

独立质量监管第一次审查为 FAIL：发现 3477 条历史 evidence 被恢复为发布日期，其中至少 1944 条来自明确的更新时间来源。随后完成最小修正：

- `legacy_evidence` 不再生成 `publication_date`；
- GitHub/Hugging Face/Gitee 的历史日期只恢复为 `source_updated_at`；
- 历史记录统一使用 `report_date_fallback`，不参与“最近发布”推断；
- 影子和正式发布路径都执行 `audit_temporal_documents`，任何历史/更新时间升格都会在切换活跃指针前失败；
- lexical、vector 和 Graph 写入时统一注入真实 `ingested_at`。

最终影子门禁：3663 条，`legacy_promoted_to_publication=0`，`update_only_promoted_to_publication=0`，通过。

正式 generation：`gen-20260812T053410-cd457f28`。Graph 维护期间服务安全降级为 vector-only，完成后恢复 `hybrid / ready`。Neo4j 与 ChromaDB 均覆盖 66 个日期，双向缺失均为 0，一致性检查通过。

独立质量监管最终结论：**PASS，Stage 4 可以关闭**。
