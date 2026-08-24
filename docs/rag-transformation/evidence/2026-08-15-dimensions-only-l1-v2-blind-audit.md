# Dimensions-only L1 v2 首轮盲测审计

- 日期：2026-08-15
- 状态：原始 Blind Gate 无效；人工裁决完成；v2 STOP
- 禁止：修改冻结候选后重跑同一批 Query

## 原始事实

- 15 条预测在读取 Gold 前已封存；
- 冻结哈希校验通过；
- 原始评分器输出完整合同 0/15；
- 解封后发现 Gold 含公共 envelope 不支持的 `expected_status=ambiguous`；
- 原评分器也错误使用了“完整合同 ≥85%”，而既有标注指南要求主路线 ≥85%、完整投影 ≥70%、保真词 micro-F1 ≥85%。

因此 0/15 必须保留为原始运行记录，但不能作为有效 Blind Gate 结论。修订后的评分器会在读取预测后、计算分数前拒绝非法 Gold，目前对原 Gold 明确报错：`invalid expected_status: ambiguous`。

## 初步责任拆分

### 明显标签/合同错误

- `blind-001`：Query 内 ATR 被错误标为来自 `conversation_context` 的 resolved reference；
- `blind-002`：使用不存在的 `ambiguous` envelope 状态，且把 context 文本当作 Query protected terms；
- `blind-003`：普通解释 + 定位被标为 temporal route，Query ATR 同样被伪标为 context reference；
- `blind-013`：明确传播关系与先后顺序却标为 evidence research 主路线；
- `blind-015`：公开上下文没有 ATR 左右映射，Query 还明确要求无法确定时先询问，却标为 resolved。

### 明显候选缺陷

- 标题片段置于引号内时被当作完整精确标题；
- A 作为 supporting route 时 `_supporting_contract` 不能构造，出现 `KeyError`；
- 相对时间窗容易被模型误判为独立 trend delivery，产生 B/C 或 D/B 假 supporting；
- `必要时可以联网`、`不需要联网` 等限定式权限被简单 substring 规则误判；
- “这个说法：后置主张”没有被识别为句内后指，错误要求澄清；
- protected terms 抽取出现前导“把/的”、疑问词和漏掉来源范围等问题；
- answer mode 过度依赖固定字面词，例如只有精确出现“热门趋势”才生成 `trend_clusters`。

### 需要产品口径裁决

- “跨事件趋势”应是 B 主 + C supporting，还是只视为 B 的内部检索方式；
- “补充其中最重要的一条新闻”在 trend discovery 中是否构成独立 supporting task；
- 已在上下文中解析为普通概念、但没有 ATR ID 的代词，应该允许语义引用还是必须要求澄清；
- 纯 item navigation 的默认联网权限是 `forbidden` 还是 `on_demand`。

## 正确后续

1. 保留原始 Query、Gold、Predictions、Score，不覆盖；
2. 独立监管逐条裁决标签有效性；
3. 生成 `adjudicated` Gold 和评分，只能称为解封后回顾性分数；
4. 将本批 15 条永久降级为校准/回归集；
5. 根据真实缺陷设计 v3，不在冻结 v2 上补丁后重跑同一 Blind；
6. v3 冻结后必须使用另一批全新不可见 Query 才能形成新的 Blind Gate。

## 独立监管结论

监管逐条审计后裁决：3 条原 Gold 基本有效、3 条 mixed、9 条无效；同时确认候选仍有 supporting A `KeyError`、部分标题误判、B/C/D 假 supporting、权限误判、误澄清和保真词系统性噪声。结论为 `STOP` 当前冻结候选。

## 解封后回顾性分数

使用独立监管口径生成新的 adjudicated Gold，仅对原 predictions 重新计分，没有调用模型或重跑 Query。该分数只能用来定位 v3，不是 Blind Gate：

| 指标 | 结果 | Gate |
|---|---:|---:|
| 主路线准确率 | 64.3% | ≥85% |
| A / B / C / D / E | 100% / 100% / 50% / 50% / 33.3% | 每类 ≥80% |
| 联网权限准确率 | 35.7% | 100% |
| 保真词 micro-F1 | 34.5% | ≥85% |
| 澄清 precision / recall | 20% / 100% | 均 ≥80% |
| 完整合同准确率 | 6.7% | ≥70% |

结果文件：`../evals/sealed/dimensions-only-l1-v2-adjudicated-score-2026-08-15.json`。

架构判断：五个独立布尔维度会把时间、关系等“语义出现”误当独立用户交付；确定性 Query Facts 又被迫用正则猜权限、标题完整度和任意主题保真词。v3 必须把“有序交付动作”作为核心原子，并让语义权限/保真信息回到受约束的 Query Frame，而不是继续扩充词表。
