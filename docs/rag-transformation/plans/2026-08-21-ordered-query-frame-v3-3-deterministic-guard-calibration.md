# Ordered Query Frame v3.3 确定性护栏校准计划

## 1. 目标

在不更换整体架构、不接检索和正式 Agent 的前提下，修复 v3.2 Blind 暴露的四个窄问题，并把
“模型语义判断”与“可从 Query 直接证明的字段保真”分开。

## 2. 最小改动

1. ATR ID：只使用现有严格正则，确定性校正 item navigation 为 `atr_id/exact_item`；
2. 完整标题：只以 Query 中完整的 `《...》` 为证据，确定性校正为 `full_title/exact_item`；
3. 明确联网/禁网：只识别直接请求和直接否定，投影为 permission enum；模糊表达仍由模型判断；
4. 无上下文指代：`这个说法/该说法/上述说法` 没有同句后置主张或公开上下文时，强制失败关闭；
5. relation 边界：只修改 Prompt，明确“实体之间是什么关系、区分合作与共现”属于 C relation；
   不添加 relation 关键词路由器；
6. deep research 边界：只有明确要求深度/全面研究时才用 `deep_research`，普通“分析影响”保持
   `explanation`；
7. 关键字段 Gate：保留 raw Frame span 指标作为诊断；产品 Gate 从最终 `envelope.contract` 读取
   locator/output、permission、status、temporal constraint、claims、resolved references 与
   protected terms。数字、否定和来源本阶段不新增规则，只在合同已有逐字 literal 时计入保真。

禁止把金额、否定、来源、relation 或实体名称扩展成开放式关键词规则。确定性层优先级为：明确
禁网 > 明确联网 > on-demand；ATR ID > 完整书名号标题 > 模型 locator；缺少上下文的指代始终
失败关闭。

## 3. TDD 与小样顺序

1. 四个失败案例各写一个公共 seam 回归测试；
2. 每次只实现一条最小护栏或 Prompt 边界；
3. 离线回归通过后，质量监管 Agent 检查是否把语义判断过度规则化；
4. 只对已解封的 6 条诊断样本做一次可见 DeepSeek 校准，最多 6 次、零重试；
5. 达标后才设计下一批全新 Blind；当前 20 条不得重用为 Blind。

## 4. 可见校准 Gate

固定样本：

- 修复命中：009（完整标题）、012（relation）、016（无上下文澄清）、018（普通分析）；
- 控制样本：015（有上下文的 resolved claim，防止过度澄清）、011（跨时间点 C + 禁止联网，
  防止 relation/permission 回归）。

运行前生成独立 query/gold/Freeze 并固定哈希；文件和报告必须包含 `visible-calibration`，不得使用
`blind`、`generalization` 或类似表述。

合同级评分逐字段执行，不允许跨字段补分：

- `expected_status` 与 `envelope.status` 精确比较；澄清样本还必须满足 `contract == null`；
- resolved 样本必须有合法 contract；主 family 与 `contract.primary_task_family`、主 output 与
  `contract.answer_mode` 精确比较；辅 delivery 必须按顺序在 `supporting_contracts` 中逐项比较，
  其中辅助导航的 output/locator 分别读取 `requested_output_form/locator_kind`；009 的导航字段因此
  检查 supporting item-navigation contract，而不是主 C contract；
- 当前顶层 contract 不暴露主 item-navigation 的 `locator_kind`，而本轮六条没有主导航样本，故不
  把该字段伪装为可评分项；它必须在后续新 Blind 前通过合同设计单独解决；
- enum、status、family、output、locator、permission、temporal constraint 均精确匹配；
- claims、resolved references、protected literals 只在各自合同字段内计算 recall，出现在其他字段
  不得补分；
- 每条样本的所有必需字段全部通过才是 `product_complete`，本轮要求 6/6，不使用 pooled recall
  掩盖单条失败。

- 012 relation、016 clarification、009 full-title locator、018 explanation 全部正确；
- 6 条 ordered delivery exact = 100%，web permission = 100%；
- 最终 Route Contract 合同级关键字段 recall = 100%；
- raw Frame protected span F1 只报告，不进入 `product_complete` 或最终 Gate；
- contract-level `product_complete` = 6/6；
- L3 legal / replay = 100%；
- 单题一次、零重试；平均 <= 8 秒、最大 <= 12 秒。

## 5. 暂停项

不接 Query Rewrite、检索、GraphRAG、Prompt Registry、正式 Agent、UI、Docker 或索引；不为具体
实体增加关键词，不因可见校准通过宣称泛化。

## 6. 执行状态（2026-08-21）

- 离线合同/冻结/辨别力及相关回归：38/38 通过；
- 质量监管初审：BLOCK（发现同一 literal 可跨字段补分）；
- 改为逐项 `path / literal / match` 合同评分并重建 Freeze 后复审：APPROVE；
- 沙箱网络无效运行：第 1 条连接失败后按规约停止，不计模型结果；
- 外部网络恢复运行：6/6、0 error、每题一次、零重试；
- 合同级 `product_complete=6/6`，全部 Gate 通过；平均 1.972 秒，最大 2.836 秒；
- 本计划目标已完成。下一阶段只允许设计全新 Blind，不得继续优化或重跑这 6 条可见样本。
