# Dimensions-only L1 v2 最小替换计划

- 日期：2026-08-15
- 状态：STOP；不得继续调参或接入
- 正式流量影响：禁止
- 目标：替换失败的 v1 模型输出合同，不在其上继续叠补丁

## 失败复盘

v1 名义上让模型判断五个窄语义维度，实际上 strict tool 还要求模型输出：

- protected spans；
- item locator precision；
- unresolved references；
- resolved ATR references。

`NSD-007` 同时包含左右 ATR 条目和句内主张代词“它”，模型连续三轮无法生成合法 L1。后处理可以修正已成功解析的 JSON，却无法拯救模型在复杂 Schema 下持续产出的非法结果。

## 替换接口

模型唯一输出：

```text
dimensions:
  item_lookup: state + literal evidence spans
  recent_update_set: state + literal evidence spans
  cross_time_or_entity_structure: state + literal evidence spans
  truth_assessable_claim: state + literal evidence spans
  explanation_or_comparison: state + literal evidence spans
```

模型不得输出 route、protected spans、locator、reference、permission、policy 或答案。

确定性 Query Facts 模块独立产生：

- ATR ID、完整/部分标题和 locator precision；
- 时间、金额、比例、数量、来源和联网权限；
- 左右位置引用、公开上下文 ATR 和句内先行词；
- 可搜索的 protected terms。

随后由一个 assembler 合并成现有 Narrow Semantic Decisions v1，再交给冻结的 L2 投影。调用方公共 seam 不变。

## 最小 TDD

1. Schema 明确禁止 protected/locator/reference/route 字段进入模型输出。
2. `NSD-007` 的模型 fixture 只包含五维；确定性层独立还原左右 ATR，忽略句内主张代词。
3. `NSD-009` 的无先行词“这个”仍 unresolved 并 fail-closed。
4. B+D / D+B、C+纯措辞 E、A+独立解释 E 的主次不回退。
5. 仅运行 3 条可见 canary；通过后才运行 12 条一次。

## Gate 与停止规则

- 三条 canary：完整合同 3/3，平均 ≤8 秒、最大 ≤12 秒；
- 十二条可见校准：完整合同 12/12；
- 任一失败即停止，不新增示例、实体词表或第三次可见调参；
- 通过后冻结哈希，再由隔离 Agent 创建全新未见盲测；
- 未见 Gate 仍沿用总体 ≥85%、每类 ≥80%、关键权限 100%、歧义 P/R ≥80%。

## 不做

- 不修改检索、重排、Prompt Package、聊天或 Web UI；
- 不读取旧 sealed Gold 调整 v2；
- 不删除 v1 失败资产；
- 不将组合可见成绩描述为泛化能力。

## 2026-08-15 执行快照

- 模型 Schema 只允许 `schema_version + dimensions`；
- 确定性 `Query Facts` 独立处理 ATR、标题、时间、权限和公开上下文引用；
- assembler 合并后复用既有 Narrow Decisions v1 与冻结 L2；
- 离线可见合同装配一致性 12/12，聚焦回归 79/79；
- 真实 Canary 使用 NSD-003 / NSD-007 / NSD-009，完整合同 3/3；
- 平均 1.744 秒、最大 2.263 秒；三条均一次输出合法 tool call；
- 结果文件：`../evals/dimensions-only-l1-v2-three-case-canary-results-2026-08-15.json`。

第一次独立 Stage Gate 最终返回 `REVISE`：允许一次性 12 条真实可见校准，但指出离线 fixture 不证明模型能力，并识别两处 fail-open 风险。

一次性 12 条真实校准结果：完整合同 12/12，平均 1.396 秒，最大 1.730 秒，全部一次输出合法 tool call；结果文件为 `../evals/dimensions-only-l1-v2-visible-calibration-results-2026-08-15.json`。该结果仍是可见诊断，不是泛化证据。

随后以失败测试修复监管指出的两处风险：

- 删除“前文任意 Latin token 即视为代词先行词”的捷径；
- 删除“按 context 中 ATR 出现顺序猜左右”的 fallback，必须存在明确左右标签。

修正后聚焦回归 81/81。没有重跑或覆盖上述真实校准结果。

第二次独立 Stage Gate 返回 `GO`：允许冻结当前候选并由隔离 Agent 创建不可见盲测；仍禁止接入正式流量。冻结清单见 `../evals/dimensions-only-l1-v2-freeze-manifest-2026-08-15.json`，同时固定 Prompt、Schema、Query Facts、assembler、L2 与评估器哈希。

## 首轮 Blind 结果异常

预测封存后原评分输出 0/15，但解封发现 Gold 含非法 `ambiguous` 状态，评分门槛也与既有 annotation guide 不一致。原始分数保留但 Blind Gate 判定无效；详见 `../evidence/2026-08-15-dimensions-only-l1-v2-blind-audit.md`。v2 仍禁止生产接入，本批 Query 永久转为解封后的校准资产。

人工裁决后的回顾性分数仍全面低于 Gate，且存在 supporting A 硬异常，因此独立监管裁决 `STOP`。v2 文件保留为失败证据，不在同一数据集上继续修改和重跑。
