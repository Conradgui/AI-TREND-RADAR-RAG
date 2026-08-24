# Ordered Query Frame v3.2 Prompt-only 校准计划

- 日期：2026-08-16
- 变更范围：只改语义 Prompt 与校准 Gold 合同
- 不变：JSON Schema、L2 投影、Route Contract、RAG、正式 Agent、Web UI
- 证据等级：已解封校准，不是 Blind

## 四个决策边界

1. **重要新闻 vs 趋势簇**
   - 用户只要求“动态、新闻、更新、热点”时选择 `important_news`；
   - 只有明确要求“按主题聚类、分组、趋势簇、归纳模式”时选择 `trend_clusters`；
   - 不得因为 trend_clusters 更丰富就自动升级。
2. **复合交付保留**
   - 不同 task family 的明确动作必须按原顺序全部保留；
   - 一个回答可能顺便包含记录或证据，不等于可以删除用户明确要求的 A/E/D delivery。
3. **C 与 E 的比较边界**
   - 同一实体跨时间截面、版本或阶段的变化属于 C；
   - 不同产品、实体或方案的属性差异属于 E comparison；
   - timeline 要求离散事件/里程碑顺序；无离散节点的多年演变使用 longitudinal trend。
4. **澄清与 delivery 正交**
   - unresolved reference 决定 Envelope 是否澄清，不决定用户有没有明确动作；
   - 动作明确但对象未解析时，保留 delivery + unresolved span；只有动作本身也无法判断时
     才允许空 deliveries。

## 字段标注合同

- protected：实体、ID、标题/完整主张、时间范围、数字、指定来源、影响内容含义的限定词；
- delivery evidence：动作与输出形式的原文依据；
- web evidence：联网权限的原文依据；
- unresolved：当前 Query 无唯一先行词的指代；
- 同一原文不因“重要”而重复塞进多个字段。确定性 L2 可在最终 Route Contract 中合并
  必须保真的权限与内容信息，但 L1 评分按字段职责分别判断。

## 7 条小样

从已解封新 Blind 中固定 003、005、006、008、010、012、018：

- 003：A + B important news；
- 005：B trend clusters 正对照；
- 006：B important news + C longitudinal；
- 008：B trend clusters + supporting A；
- 010：C cross-sectional + supporting A；
- 012：C longitudinal + unresolved clarification；
- 018：E explanation + unresolved clarification。

不重新发明实体词表，不根据单个标题写规则。先离线测试 Prompt/Schema 兼容，再冻结一次
真实调用；失败即停止。
