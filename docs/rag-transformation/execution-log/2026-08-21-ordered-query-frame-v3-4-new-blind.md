# Ordered Query Frame v3.4 全新盲测执行记录

## 1. 证据边界

本次实验只验证 `Query -> OrderedSemanticFrameV3 -> RouteContractV2`。它不验证检索召回、
GraphRAG、Prompt Registry、回答质量、Web UI、生产可用性或发布质量。

- 数据：15 条全新 Query-only 样本，A–E 主任务各 3 条；
- 标注：双人独立标注后裁决；
- 执行：DeepSeek `deepseek-v4-flash`，每题一次，零重试；
- 冻结：公开 Prediction Freeze 与 sealed Evaluation Freeze 均在调用前生成；
- 纪律：本批已解封为诊断资产，不得修改 Gold 后重跑，也不得用事后口径替换正式分数。

## 2. 标注与冻结

双标注一致率：

| 项目 | 一致率 |
|---|---:|
| status | 100% |
| deliveries | 93.3% |
| web permission | 100% |
| unresolved references | 100% |
| contract literals | 46.7% |
| primary family | 93.3% |

覆盖检查确认：A–E 各 3 条、复合任务 4 条、澄清 3 条、联网 explicit / forbidden /
on_demand 分别为 5 / 4 / 6 条，并覆盖四类 locator。

冻结运行参数：temperature=0、max_tokens=900、timeout=20s、thinking disabled、
max_retries=0。15 条全部完成，无 provider error；总 token 35,794，平均每题 2,386，
平均/最大延迟 1.549/2.154 秒。

## 3. 正式结果

| 指标 | 结果 |
|---|---:|
| Product complete | 8/15 |
| Ordered Frame delivery exact | 15/15 |
| Final delivery contract exact | 93.3% |
| Clarification delivery exact | 100% |
| Unresolved references exact | 86.7% |
| Web permission contract | 100% |
| Contract literals | 66.7% |
| L3 legal | 93.3% |
| L3 projection consistent | 100% |

正式 Gate 为 **FAILED**。但 8/15 不能解释成“路由只有 53%”：模型在 15/15 条上都选对了
Ordered Frame 的交付类型，主要失分发生在 Frame 到最终合同的字段投影与评估协议。

## 4. 失败归因

| Case | 归因 | 结论 |
|---|---|---|
| 002 | 评估过约束 | 来源已正确进入专用字段，Gold 又要求复制到 protected terms。 |
| 003 | 评估过约束 | 已正确要求澄清；仅 unresolved span 的边界没有逐字一致。 |
| 006 | 模型语义遗漏 | 无公开前件的“它”未被识别为 unresolved。 |
| 009 | 合同表示缺陷 + 评估过严 | 时间区间被拼接为字符串；引号包装被当作语义本体评分。 |
| 010 | 系统投影缺陷 | Query 中直接 claim 没进入 claims；中文“机构官方材料”未解析为来源。 |
| 013 | 模型语义遗漏 | “不要扩展成行业研究”这类改变输出范围的否定约束丢失。 |
| 014 | 混合 | 假设 claim 未投影是真缺陷；要求把“小团队的产品决策”拆成“小团队”是 span 过约束。 |

独立质量监管复核后同意以上归因，并裁决：当前不进入 Query Rewrite、Retrieval、
Prompt Registry 或正式 Agent。

## 5. 产品与架构判断

现有“有序任务框架 + 一个 Route Contract 贯穿下游”的主架构可以保留。问题集中在四个
公共 seam，而不是需要替换 Router 框架：

1. 裸指代 / 无前件引用的澄清护栏；
2. Query 直接陈述与假设 claim 的投影；
3. 通用“机构 + 官方来源”解析；
4. 会改变回答范围的否定约束保留。

另有两个合同治理问题必须在 v3.5 明确：

- `web_permission`、`source_constraint` 是各自的单一事实来源，不强制复制进
  `protected_terms`；
- 时间范围需要可消费的标准表示，同时保留用户原始表达，不能继续使用 `A | B` 拼接。

## 6. 下一步

只开展 v3.5 可见校准，不再运行 v3.4 Blind：

- 先写 4–6 条公开失败测试；
- 只修上述公共 seam 和评估协议，不加入实体关键词补丁；
- 先跑离线合同测试，必要时最多一次小型 DeepSeek 可见校准；
- 经独立质量监管确认后，才决定是否进入下游 Query Rewrite / Retrieval Gate。
