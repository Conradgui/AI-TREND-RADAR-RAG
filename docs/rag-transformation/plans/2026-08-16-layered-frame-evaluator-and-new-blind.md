# Ordered Frame v3.1 分层评估器与新 Blind 计划

- 日期：2026-08-16
- 状态：设计待独立 Stage Gate
- Live 调用：停止
- 正式流量：禁止

## 1. 要解决的测量问题

旧评分器把三个不同问题压成一个分数：

1. 模型是否正确理解用户明确要求的任务（Frame）；
2. 未解析指代是否应触发 clarification（Envelope 状态）；
3. L2 是否把合法 Frame 无损编译成可执行 Route Contract。

当 Envelope 进入 clarification 时，`contract=None`。旧评分器因此把 Frame 中正确的
primary route 和 web permission 一并判错；这不等价于模型没识别任务。protected
spans 又用字符串集合完全相等，合理边界差异会被整项判错。

新评估器必须分层，不能修改或覆盖已保存的 v3.1 Gate FAIL。

## 2. 冻结后的四层指标

### L1：Ordered Semantic Frame

只读模型 Frame，不读最终 contract：

- `delivery_sequence_exact`：task family、output form、locator 及顺序全部一致；
- `primary_task_family_accuracy`：读取 Frame 第一项，而不是 contract；
- `output_form_accuracy`：逐 delivery 比较；
- `web_permission_accuracy`：直接比较 Frame；
- `unresolved_span_micro_P/R/F1`：比较 Query 中被标为 unresolved 的字符区间；
- `protected_span_char_micro_P/R/F1`：比较 Query 字符区间并忽略空白与标点，不要求
  span 字符串切分边界完全一致。

span 评分过程固定为：将每个 literal span 映射回 Query 的全部字符位置，取区间并集，
移除 Unicode 空白与标点后计算 micro P/R/F1。不存在于 Query 的 span 直接判非法，
不得用模糊语义匹配或 LLM Judge 放宽。

当同一 literal 在 Query 中重复出现时，固定标记它的**全部非重叠出现位置**；Gold 与
prediction 使用同一规则，不由评分器猜测“模型指的是哪一次”。这会牺牲单次提及的
细粒度区分，但规则确定、可复现且可审计；未来若产品确需区分，再升级合同为显式
`start/end` offsets，不能在本轮临时推断。

span 空集合规则固定为：

- 单题 Gold 与 prediction 都为空：P=R=F1=1；
- prediction 为空、Gold 非空：P=0、R=0、F1=0；
- Gold 为空、prediction 非空：P=0、R=1、F1=0；
- 聚合 micro 使用全数据字符位置 TP/FP/FN；若全数据 Gold 与 prediction 都为空，
  micro P/R/F1 均为 1。

`output_form_accuracy` 不做语义或最佳匹配：按 delivery 索引比较，分母为每题
`max(len(expected), len(predicted))`；缺失、额外或错序位置全部计错。locator 使用同一
位置规则单独报告。`delivery_sequence_exact` 仍要求整条序列完全一致。

### L2：Clarification / Envelope

- `clarification_precision/recall`：只比较 Envelope 状态；
- resolved 必须有 contract；clarification 必须 `contract=null` 且 reasons 非空；
- Gold clarification 仍保留明确 deliveries，不能以空 Frame 冒充谨慎。

### L3：确定性投影

这是自一致性指标，不依赖 Gold 偏好：

- resolved contract 的 primary 必须等于 Frame 第一 delivery；
- supporting 必须等于后续 distinct task families，顺序一致；
- answer mode 必须与 primary output/locator 一致；
- web permission 必须与 Frame 一致；
- contract 必须同时通过 JSON Schema 与产品语义校验；
- clarification 不得生成 contract。

评估器必须从保存的 Frame、原 Query 和公开 context **重新调用冻结的确定性 L2**，
再把重放得到的完整 envelope 与保存 envelope 做规范 JSON 全等比较；不能只抽查字段。
这样才能检测运行时投影与当前 L2 实现漂移。若 L2 文件哈希与预测冻结清单不一致，
直接拒绝评分，不用“当前代码重放旧预测”。

### L4：产品级完成

每题只有同时满足以下条件才算完成：

- delivery sequence、web permission、Envelope 状态均正确；
- protected 与 unresolved 的该题字符区间 F1 均不低于 0.80；
- L3 投影合法且自一致。

聚合指标仍单独展示，不能用一个综合分掩盖某层失败。

## 3. Gate 门槛

```text
delivery sequence exact >= 85%
primary task family >= 85%
each family primary >= 80%（每类至少 3 题才启用硬门）
output form >= 85%
web permission = 100%
protected char micro-F1 >= 85%
unresolved char micro precision/recall >= 80%
clarification precision/recall >= 80%
L3 legal + projection consistency = 100%
product complete >= 80%
single attempt = 100%
mean latency <= 8s, max <= 12s
```

当某 task family 少于 3 题时只报告，不作为硬 Gate；避免 1/2 条样本让整类指标在
0、50、100 之间跳变。

## 4. 新 Blind 的双重标注流程

1. 出题 Agent 只读产品合同，不读实现输出或旧预测，生成 20 条新 Query 与第一版 Gold；
2. 隔离复核 Agent 只读 Query、公开 context、评分合同和第一版 Gold，不读实现输出；
3. 两者分歧必须在封存前裁决并记录 rationale，尤其是：
   - 同 task family 多回答小节的合并；
   - “跨事件趋势”是否属于一个 B delivery 或 B+C 两个独立任务；
   - 后置主张、标题片段与普通“对应记录”不是 unresolved；
   - context 是否提供足够、唯一、可执行的指代映射；
4. 主线只获得 Query 文件与冻结哈希；Gold 单独封存；
5. 先用脚本化 perfect/degraded/wrong 三组预测验证 evaluator 辨别力；
6. evaluator Gate 通过后，模型每题只调用一次；预测封存后才解封 Gold。

20 题配额：A/B/C/D/E **分别作为 primary** 各 4 题；至少 4 条 clarification，其中一半保留明确 deliveries；
web forbidden/on_demand/explicit 均需覆盖；复合任务至少 5 条。

## 5. TDD 顺序与停止条件

先构造三类基线，并在 wrong 下拆成四个单层退化 fixture：

- perfect：所有层均正确，必须 PASS；
- degraded：span 边界略宽但语义位置正确，只降低 span precision，不应整题归零；
- wrong-L1：Frame 路线、output、web 或 unresolved 错误，必须 FAIL；
- wrong-L2：clarification 状态错误，必须 FAIL；
- wrong-L3：保存 envelope 与冻结 L2 重放不一致，必须 FAIL；
- wrong-L4：单层指标看似部分合格但产品完成率不足，必须 FAIL。

只有满足 `perfect > degraded > wrong` 且 wrong 无法通过硬 Gate，才允许生成新 Blind。
如果双标 Gold 存在未解决分歧、评分器读取模型输出参与定标、或任何 frozen hash 漂移，
立即停止，不调用模型。
