# M5：证据分层、层内排序与 Top K 策略

## 不可改变的顺序

```text
Lexical / Vector 文本宽召回
→ ATR/content 去重
→ 同类文本列表 RRF 融合
→ 使用原 Query 做文本语义重排
并行：Graph 生成结构 + 支持 ATR；Web 通过准入后形成外部候选
→ 三类候选按“对当前问题承担什么证据角色”汇合
→ Primary / Supplementary / Background / Unverified / Excluded 分层
→ 同层按重要性、新鲜度、证据质量、上游价值排序
→ 多样性约束
→ 合格候选转为 Evidence Record / Ledger；其余进入 trace
→ EvidenceBundleV2
```

相关性决定层级；其他信号没有跨层晋级权。

## 层内因子

- Dynamic Importance：影响范围、深度、主体显著性、新颖度、讨论价值；
- Query-relative Freshness：用户时间预期、事件/发布时间和旧闻回流；
- Evidence Quality：一手性、正文完整、日期可信、独立佐证和直接支持度；
- Upstream Value：日报原有分数与录入时热度快照，只是 Dynamic Importance 的弱输入，不是第四个独立排序轴；
- Diversity：初排后的列表约束，限制同事件/来源/主题占位。

## 多阶段 K

| K | Canary 启动范围 | 作用 |
|---|---:|---|
| `channel_k` | lexical/vector 各 30–50 | 保住候选 Recall |
| `graph_k` | 10–30 条结构记录 | 控制图展开 |
| `fusion_k` | 50–100 个唯一身份 | 容纳多通道重叠 |
| `rerank_k` | 20–50 | 控制昂贵语义重排 |
| `context_k` | Primary 5–8、Supplementary 2–4、Background 0–3 | 控制 Agent 噪声与 token |
| `display_k` | 主结果 3–5 | 控制用户扫描负担 |

这些只是小样起点，不是最终参数。Azure Hybrid Search 将通道 K、融合结果和语义重排窗口分开，并说明语义 ranker 最多处理前 50 条，这支持“多阶段 K”而非一个全局值。[官方说明](https://learn.microsoft.com/en-us/azure/search/hybrid-search-how-to-query)

## 校准方法

先增加 `channel_k` 直到 Recall@candidate 收益趋平，再确定 `rerank_k`，最后用忠实度、延迟和上下文噪声选择 `context_k`。不能从“UI 展示 5 条”倒推初召回也只取 5 条。

## 评价

Recall@20/50、MRR、NDCG@5、层级混淆矩阵、高热弱相关进 Primary 比例、旧闻冒充最新率、来源/事件多样性、P95 与每请求成本。
