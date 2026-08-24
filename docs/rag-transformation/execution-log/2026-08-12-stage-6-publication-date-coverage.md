# Stage 6 执行记录：结构化发布日期覆盖小样

日期：2026-08-12

## 根因证据

- 容器中 2026-08-10 至 2026-08-12 共 165 条候选；`publishedAt=0`、`sourceUpdatedAt=0`。
- 当前源码抓取适配器已经输出这两个结构字段；托管上游 Pages 仍提供旧格式语料。
- 旧生成器将发布时刻、仓库更新时间与 sitemap 时间统一写成“发布时间”，造成语义混合。

## 最小实现

- 新增 `legacy_adapter_contract` 发布日期来源标记。
- 首轮曾包含中文资讯；独立监管发现其适配器在缺日期时会用抓取时间兜底，阻断正式激活。
- 修正后仅恢复可以证明的发布事件来源：Hacker News、Product Hunt、ArXiv。
- GitHub、Hugging Face、Gitee 继续只恢复为 `source_updated_at`。
- OpenAI、Anthropic、Google DeepMind 等旧官网 sitemap 日期保持未知。
- 原始日报 JSON 不改；迁移仅发生在规范语料投影。

## 2026-08-12 影子投影

| 指标 | 结果 |
|---|---:|
| 原子条目 | 54 |
| 可证明发布日期 | 19 |
| 可证明来源更新时间 | 27 |
| 保持未知 | 8 |
| 更新型来源误提升为发布日期 | 0 |
| 官网 sitemap 误提升为发布日期 | 0 |

8 条未知中，OpenAI、Google DeepMind 各 1 条因旧 sitemap 时间语义不可信而留空；
全部中文资讯旧日期因适配器存在抓取时间兜底而不恢复，其中 5 条还是
`+058568-10`、`Mon, 10 Au` 等损坏值。

正式激活门同时拒绝：来源越权、非法日期、无来源的发布日期，以及
`publication_date_source/effective_date_basis/effective_date` 自相矛盾。

## 回归结果

- TypeScript 时间/规范语料/抓取相关测试：56/56 通过。
- Python ingestion、查询理解、时间路由、lexical、citation：67/67 通过。
- 本机 `pnpm typecheck` 因未安装 `node_modules` 无法启动 `tsc`；留待 Docker 构建统一验证。

## Stage Gate

第一次独立监管结论为 **BLOCK**，有限修正已完成。机器可读影子结果保存于：
`docs/rag-transformation/evals/stage-6-temporal-shadow-2026-08-12.json`。
等待复审后才决定是否重建正式投影与索引。

最终有限修正后，独立监管结论为 **APPROVE**。

## 正式激活

- 影子 generation：3663/3663 条，embedding 100% 复用，ATR 身份覆盖 1.0；
- 时间审计：6 类污染计数全部为 0，`passed=true`；
- 正式 generation：`gen-20260812T062943-febd908f`；
- Neo4j / ChromaDB：66 / 66 个日期，一致性通过。

## 正式索引互斥 Canary

| 查询 | 路由字段 | 结果 | 目标字段缺失 |
|---|---|---:|---:|
| 最近发布了哪些内容？ | `publication_date` | 20 | 0 |
| 最近更新了哪些项目？ | `source_updated_at` | 20 | 0 |
| 最近收录了哪些内容？ | `report_date` | 20 | 0 |

Stage 6 关闭。旧语料在可证明范围内恢复了发布日期/更新时间；不可信或损坏日期保持未知。
