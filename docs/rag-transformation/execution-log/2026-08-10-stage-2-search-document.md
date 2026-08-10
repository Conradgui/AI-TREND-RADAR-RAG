# Stage 2：Search Document、条目搜索与稳定深链执行记录

日期：2026-08-10  
分支：`claude/rag-transformation-checkpoints`  
固定点：`d58e0785945d22dd2416bdbce57786594766a282`  
状态：Gate Review 通过，待 Claude 分支 checkpoint

## 1. 完成内容

- 建立 `sd-v1` Search Document：分离 `content_id` 与 `occurrence_id`，摘要等可变字段不参与身份。
- 从真实 `topic-pool.json.candidates` 生成 `digests/search-index.json`；周报/月报不进入条目索引。
- Web UI 从“匹配日期”改为“返回具体条目”，支持时间、来源和分类筛选。
- 搜索结果进入 `#date/report/item/<occurrence_id>` 独立详情；标题、摘要、推荐理由、分析角度、证据和外链均来自 Search Document，不二次生成。
- 只有 producer 提供有效 `report_target` 时才显示“在日报中定位”；consumer 不按标题、URL 或行号猜落点。
- 静态 HTTP 与 FastAPI 复用同一组 Playwright 用户路径。
- GitHub Pages 发布 allowlist 增加本地 vendored MiniSearch 7.2.0 与 MIT 许可证。

## 2. 全量索引证据

| 指标 | 结果 |
|---|---:|
| source candidates | 3,558 |
| Search Documents | 3,550 |
| 聚合的完全重复记录 | 8 |
| occurrence ID 唯一数 | 3,550 / 3,550 |
| `sum(duplicate_count)` | 3,558 |
| rollup documents | 0 |
| URL 安全诊断 | 0 |
| degraded identity | 0 |
| external URL 非空 | 3,550 / 3,550 |

公开语料合同已重建并通过精确校验：

```text
revision=1bbc3d98270bb5e4ffcbdde29debc049ced125575c5082e01208be9aeef1fcca
files=160
source_mode=hosted
```

## 3. 搜索引擎 bake-off

真实 3,550 条数据、74 个字符召回代理查询：

| 指标 | FlexSearch 0.8.212 | MiniSearch 7.2.0 |
|---|---:|---:|
| 构建中位数 | 389 ms | 1,506 ms |
| 查询中位数 / P95 | 0.11 / 0.70 ms | 0.59 / 3.79 ms |
| 序列化索引 | 26.79 MB | 5.23 MB |
| gzip 后索引 | 7.55 MB | 0.77 MB |

两者在精确标题、字面实体词、中文短词和测试 typo 上的 Hit@1/3、MRR 代理指标打平；MiniSearch 因单 JSON、字段 boost、分数可解释性和明显更小的传输体积胜出。生产策略为：精确检索优先，零结果时才对长度至少 5 的拉丁查询开放保守 fuzzy；`Open AI` 显式归一为 `OpenAI`。FlexSearch 已移除。

可复现证据：

- `docs/rag-transformation/evals/item-search-bakeoff-2026-08-10.cjs`
- `docs/rag-transformation/evals/item-search-bakeoff-2026-08-10.json`

SHA-256：脚本 `dc9ebe4706da356c6fbdd0d5edbe96a2f75086f3ad4e7d144a05270625542eab`；原始结果 `564e3ffbb06aa93ed2025be55364263f70d277d05439eb00eed3ee7fde7f6293`。

证据边界：这些 gold 来自标题精确匹配和字段字面包含，不是人工相关性标注；只能证明字符召回和工程性能，不能证明用户主观相关性。

## 4. 红绿循环与验证

1. Search Document 测试先因模块不存在变红；实现后覆盖真实 candidates、稳定身份、重排、重复聚合、URL 安全、rollup 排除和 report target。
2. 首轮 E2E 证明 `Open AI` 路径可用；新增普通多词标题 fixture 后变红，定位到 query plan 把多词错误压成单 token；拆分“紧凑品牌归一”与“保留分词检索”后转绿。
3. Playwright 首次退出残留 FastAPI 子进程；webServer 改用 `exec` 后服务可被测试框架完整回收。

最终结果：

```text
Vitest: 245 / 245 passed
RAG unittest: 242 / 242 passed
RAG pytest: 36 / 36 passed
Stage 2 focused TypeScript: 35 / 35 passed
Dashboard/release pytest: 30 / 30 passed
Playwright: 4 / 4 passed (static + FastAPI)
TypeScript typecheck: passed
corpus contract exact check: passed
```

## 5. 独立双轴初审与处置

| 轴线 | 初审发现 | 处置 | 当前结论 |
|---|---|---|---|
| Standards | Pages 构建脚本复制整个 `assets/`，发布边界过宽 | 改为只复制 MiniSearch 7.2.0 runtime 与许可证，并增加发布包断言 | 已修复 |
| Standards | 新公开接口缺少职责与失败语义说明 | 为 Search Document 与 manifest 生成接口补充 JSDoc | 已修复 |
| Standards | route parser 在模块与单文件 UI 中重复 | 暂不抽象：当前生产 UI 是无 bundler 的单文件静态边界；以同一套路由测试覆盖两端，列为后续可维护性债务 | 接受的 P2 残余 |
| Spec | 同一稳定身份的非完全相同候选可能被静默聚合，源记录覆盖率缺少闭合证明 | 构建期改为歧义即失败；累计并校验 `sum(duplicate_count) == source_candidate_count`；新增歧义和 malformed candidate 回归测试 | 已修复 |
| Spec | bake-off 只有口头结果，缺少可复现原始证据 | 落盘便携脚本、原始 JSON 与 SHA-256 | 已修复 |
| Spec | 空摘要被 UI 合成“上游未提供摘要” | 恢复原始数据语义：空值保持为空，不生成伪摘要 | 已修复 |

审查隔离说明：`article-extractor`、连接恢复与启动器相关改动来自 Stage 2 之前已经存在的工作树，不计入本 Stage 的规格实现，也不据此扩大本次 checkpoint 的声明范围。

复审结论：Standards **APPROVE**、Spec **APPROVE**；两条轴线剩余 P0=0、P1=0。监管 Agent 未修改文件。

## 6. 已知边界

- `report_target` 历史数据当前均为空；只有未来 producer 输出稳定 anchor 后，UI 才会显示日报定位。fixture 已验证该路径，不伪造历史映射。
- 当前 7.2 MB Search Document JSON 在用户开始搜索或打开 item deep link 时懒加载，不阻塞普通日报首屏；后续可根据真实网络指标决定是否拆分详情载荷。
- 当前 `entities`、`aliases` 为空，不把 Claude 与 Anthropic 擅自当同义词；实体 enrichment 和人工相关性集属于后续 Stage。
- `report-route.ts` 与无 bundler 的 `index.html` 之间仍有小段路由编解码重复；当前以跨静态/FastAPI 的同一 E2E 合同约束行为，待前端模块化 Stage 再统一实现，避免为了消除少量重复而提前引入构建链。
