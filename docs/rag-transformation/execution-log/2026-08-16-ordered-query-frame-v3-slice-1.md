# Ordered Query Frame v3 — Slice 1 执行记录

- 日期：2026-08-16
- 范围：仅离线 `OrderedSemanticFrameV3 -> RouteContractV2`
- 正式链路：未接入
- 真实 API：未调用

## 架构 Gate

首次独立监管结论为 `REVISE`：原计划仍把 standalone query 与语义 Frame 放在
一次 strict 输出中，可能重演 v1 的职责过载。删除改写职责、下沉 output form、
改用可观察 locator kind，并把单例改成最小对照后，二次监管给出 `GO`，只授权
离线 Slice 1。

## TDD 证据

红灯：使用项目 `.venv` 运行新测试，因
`rag.ordered_semantic_frame_v3` 尚不存在而在收集阶段失败。

绿灯：实现后，六组对照共 12 个测试全部通过：

```text
12 passed in 0.09s
```

相关路由、Schema、v1/v2 兼容回归：

```text
139 passed, 28 subtests passed in 0.47s
```

全量 `rag/tests`：

```text
703 passed, 28 subtests passed, 1 failed
```

唯一失败是既有发布打包测试。原因已一次诊断为当前工作树中的
`digests/search-index.json` 与 `corpus-manifest.json` checksum 不一致；它不经过
Query Frame 或 Route Contract，未在本 Slice 顺手修改，也没有反复重跑。

## 实现边界

- 新 Frame 只表达有序 deliveries、输出形式、可观察 locator、联网权限、保真词与未解析指代；
- 不生成 standalone query、检索策略、Prompt、预算或答案；
- supporting A 现在使用 answer-builder contract，完整 Route Contract 可通过 Schema；
- 新模块保持 shadow-only，没有修改正式 chat、检索、Prompt Registry 或 Web UI。

## 下一 Gate

独立监管需检查：实现是否符合计划、测试是否真的验证产品语义对照、是否有新的
确定性猜测或职责泄漏。只有监管再次 `GO` 才能设计真实 DeepSeek adapter 与三条
已解封回归 Canary。

## 实现 Gate 修订

首次实现 Gate 为 `REVISE`。修订后：

- 空 deliveries 进入 clarification，不强迫模型选路线；
- supporting A 保存 output form、locator、置信度和歧义；
- JSON Schema 约束 task family、output form 与 locator 的合法组合；
- 移除“出现官方二字就偏好官网”和“D 路由全部引号都算 claim”的确定性猜测；
- 支持原回归 Query 使用的中文单引号与绝对日期。

修订后的离线证据：

```text
16 passed in 0.10s
156 passed, 28 subtests passed in 0.74s
707 passed, 1 deselected, 28 subtests passed in 5.06s
```

被排除的 1 条仍是已定位的 corpus checksum 发布资产失败，未隐藏为通过。

第二次实现复核只发现 locator 与 output form 尚未强绑定。新增 primary A / supporting A
冲突红灯后，Schema 和 L2 统一执行：`atr_id/full_title -> exact_item`，
`title_fragment/descriptive -> item_disambiguation`。最终回归：

```text
88 passed, 28 subtests passed in 0.38s
709 passed, 1 deselected, 28 subtests passed in 5.06s
```

## 三条真实回归 Canary

adapter 严格限制为一次模型调用；三条是已解封回归样本，不是 blind。

首次受限网络运行在第一条以 `APIConnectionError` 停止。沙箱外重试揭示 DeepSeek
strict Schema 不接受内部 `if/then/allOf` 形态；保留失败报告后，以等价的扁平
`anyOf` 生成 Provider Schema，内部完整 Schema 与 Python 校验不变。第二个 Provider
兼容点是 `const/enum` 节点需要显式 `type`，补测试后解决。

模型第一次完整执行为 `2/3`：路线、主次、输出形式和联网权限均正确，第三条仅因
“禁止联网”没有同步进入最终 protected terms 失败。将模型已标出的
`web_evidence_spans` 确定性合并后，最终结果：

```text
3/3 complete projection
一次调用：3/3
平均延迟：1.913s
最大延迟：2.438s
总 tokens：5969
Gate：PASS
```

证据文件：

- `ordered-query-frame-v3-three-case-regression-canary-results-2026-08-16.json`：网络失败；
- `...-network-retry.json`、`...-provider-schema-retry.json`：Provider Schema 失败；
- `...-provider-schema-retry-2.json`：首次模型完整执行，2/3；
- `...-final.json`：修订后 3/3。

## 15 条已解封校准：按停止规则中止

调用前已冻结 Query/Gold、case 顺序、Prompt、Provider Schema、内部 Schema、
L2、运行器、评分器和运行时参数，并经独立监管两轮修订后得到 `GO`。正式运行
严格保持每题一次、零重试。

结果只执行 2/15：

- `blind-001` 成功，2.204 秒，2020 tokens；
- `blind-002` 在单次 Frame 校验中失败，模型把 conversation context 中的
  “左边列表中昨天新增的那条”放进只能来自当前 Query 的 `protected_spans`；
- 运行器按停止规则没有调用剩余 13 条；该结果不评分、不称 PASS；
- 当时运行器虽已停止，但 CLI 仍返回 exit 0，随后已用测试修正为失败 exit 2。

证据：

- `ordered-query-frame-v3-visible-calibration-freeze-2026-08-16.json`
- `ordered-query-frame-v3-visible-calibration-predictions-2026-08-16.json`

## 上下文污染防护修订与一次 Canary

修订只允许确定性删除“不属于当前 Query 的可选 protected span”，并把删除项写入
`dropped_non_query_protected_spans`；delivery evidence、web evidence、unresolved
reference 和路线语义仍不得自动修正。相关离线测试通过。

独立监管只授权 1 次新的非 blind Canary，且禁止重试。调用耗时 1.817 秒，但 Gate
失败。Canary 当时把 clarification 的空 contract 直接交给 Route Schema，导致外显
错误被误报为 `schema_version` 缺失，并在异常处理中丢失了原始 Frame/Envelope。
因此该次结果只能证明观测脚本存在缺口，不能可靠判断模型究竟输出了空 delivery
还是错误 unresolved reference。脚本随后已用离线测试修正为保留 clarification
诊断；没有再次调用 API。

证据：

- `ordered-query-frame-v3-context-guard-canary-results-2026-08-16.json`

当前结论：v3 仍是 shadow-only，15 条校准未通过，也没有资格进入新 blind 或正式流量。

## v3.1 最后一次可见校准

独立监管裁决：sanitizer 是通用合同边界，因此可视为新的 v3.1 候选；允许对同一
已解封 15 条校准集再冻结、再执行一次，但无论结果如何都不得称为泛化证据。
调用前全量回归为：

```text
723 passed, 1 deselected, 28 subtests passed
```

v3.1 运行完成 15/15、零异常、每题一次、总 tokens 30563、平均 1.715 秒、最大
2.2 秒。冻结评分 Gate 未通过：

```text
ordered deliveries: 73.3%
primary route: 78.6%
web permission: 78.6%
protected micro-F1: 70.9%
clarification P/R: 25.0% / 100.0%
complete projection: 40.0%
Frame/Route legal: 100.0%
```

证据：

- `ordered-query-frame-v3-1-visible-calibration-freeze-2026-08-16.json`
- `ordered-query-frame-v3-1-visible-calibration-predictions-2026-08-16.json`
- `ordered-query-frame-v3-1-visible-calibration-score-2026-08-16.json`

原 Gate FAIL 永久保留。离线错误聚类发现分数混合了三种问题：模型真实语义错误、
Gold 任务边界争议、以及 scorer 把 clarification 的空 contract 当作 Frame 路线/联网
错误。protected exact-set 还把“AI 芯片”与“AI 芯片领域”等粒度差异整项判错。
独立监管因此裁决停止 live：不得按预测修改 Gold，不再调用当前可见集；先冻结
Frame 语义与 Envelope/L2 分层的新 evaluator，再创建全新双重标注 blind。

## 新 20 条 Blind、Harness 失败与分层结果

新题集完成双人标注与独立裁决：20 条，A/B/C/D/E 各 4 条，4 条 clarification，
6 条复合任务，web 三态齐全。封存前机器校验发现 4 个状态枚举使用简写
`clarification`，已在预测前机械统一为 `clarification_required`；Query 与其他 Gold
字段未改。

第一次正式运行的 Provider 循环完成后，Runner 在组装报告时因 Query 顶层只有
`shard_id`、代码只读取 `dataset_id` 而触发 `KeyError`，预测未落盘。该实验永久标记
无效，不计入模型质量。Runner 随后以 TDD 改为调用前解析并校验两种身份字段；新的 v2
实验 20/20、零错误、每题一次。

离线评分又发现同一字段兼容缺口；通过评分修正案统一身份解析，未修改预测、Gold、
公式或阈值。最终冻结 Gate FAIL：

```text
delivery sequence exact: 65.0%
primary task family: 90.0%
output form: 73.1%
locator: 92.3%
web permission: 100.0%
protected char micro-F1: 83.2%
unresolved P/R: 100% / 100%
clarification P/R: 100% / 100%
L3 legal / replay: 100% / 100%
product complete: 50.0%
mean / max latency: 1.595s / 2.004s
```

错误归因表明：真实模型错误集中在 output form、复合 delivery 和 C/E 边界；同时
protected Gold 把 delivery/web 指令重复当作内容锚点，与 Prompt 字段职责冲突。
冻结分数保持 FAIL；下一步只允许 v3.2 Prompt-only 的 7 条已解封校准小样。
