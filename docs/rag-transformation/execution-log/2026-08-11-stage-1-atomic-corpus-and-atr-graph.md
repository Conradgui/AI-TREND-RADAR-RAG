# Stage 1 执行记录：原子语料与 ATR Observation 图谱

日期：2026-08-11
状态：Stage Gate PASS

## 本阶段目标

把日报中的每条信息变成唯一、独立、可检索、可引用、可跳转的原子语料；Markdown 日报只保留浏览职责，不再重复进入向量库。ATR 编号同时作为 Web UI、关键词索引、向量索引和 GraphRAG Observation 的统一身份。

## 已完成事实

- 搜索投影升级为 `schema_version=2 / atr-v1`。
- Web UI 品牌名改为 **AI Trend Radar**，并只接受 ATR v2 搜索索引。
- ChromaDB 只保留原子日报条目，不再写入 Markdown 报告切块。
- 同步成功后，由本项目根据本地 `topic-pool.json` 重新生成 v2 搜索投影。
- Neo4j 新增唯一 `Observation {id: ATR-...}`，连接 Topic、DailyDigest、Source 和 Entity。
- `Document` 仅保留报告元数据，历史 `Document.content` 已清理。
- 自然语言中出现 ATR 编号时走精确条目路由，不要求用户只输入裸编号。
- 内部证据上下文保留 `local_url`，使精确条目回答可以返回本地跳转地址。
- 旧向量存在但零条可复用时，迁移会在补嵌入前停止，避免静默全量重算。

## 运行态证据

| 指标 | 结果 |
|---|---:|
| 规范化搜索文档 | 3609 |
| Neo4j Observation | 3609 |
| 缺失 / 多余 Observation | 0 / 0 |
| 完整连接 Topic 与 DailyDigest | 3609 |
| 覆盖日期 | 65 |
| 保存正文的 Document | 0 |
| ChromaDB 原子向量 | 3609 |
| 检索模式 | hybrid / ready |
| 最新语料 | 2026-08-11 |

## 测试证据

- 核心回归：62 passed。
- 精确 ATR、Web UI v2、迁移保护及展示契约聚焦回归：39 passed。
- ATR 搜索产物 TypeScript 契约：26/26 passed。
- 精确 ATR 真实 DeepSeek：4.11 秒，1 条引用，引用 ID 与目标完全一致。
- 热门趋势真实 DeepSeek：20.98 秒，4 条引用，日期覆盖 2026-08-08 至 2026-08-11，来源覆盖 Anthropic、OpenAI、Google DeepMind、Hacker News；测试关闭联网搜索。

## 测试中发现并修复的问题

首次自然语言查询 `请查找并说明条目 ATR-...` 时，关键词索引只识别“整段输入等于 ATR 编号”，导致误走语义检索并返回“条目不存在”。现改为从自然语言中提取独立 ATR 编号，并以失败测试固定该契约。

## 明确不在本阶段冒充完成的内容

Observation 已经成为图谱事实层，但 `timeline`、`relation_exploration`、`claim_verification` 尚未拥有各自的 Observation 图查询视图。它们是下一阶段工作，不影响本阶段已验收的精确导航与热门趋势路径。

## Stage Gate

质量监管 Agent 在三轮独立审查中先后拦截了 Web UI 旧索引契约、零复用迁移保护和过期 TypeScript 测试预期。全部修复并复测后，最终结论为 **PASS**，允许关闭本阶段。
