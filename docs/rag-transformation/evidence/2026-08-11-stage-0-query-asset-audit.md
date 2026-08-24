# Stage 0A：现有 32 条评估问题资产审计

- 日期：2026-08-11
- 状态：AI 提案，等待人工确认
- 输入：`retrieval-quality-dataset-2026-08-10-silver-v2.json`
- 对照结果：`retrieval-quality-task-based-directional-2026-08-10.json`
- 审计行为：只读；未运行 LLM，未修改评估器或正式索引

## 1. 结论

现有 32 条问题不适合直接升级为正式评估集：

- 10 条当前可评分；
- 22 条只能诊断；
- 20 条是批量构造的负例；
- 12 条缺 claim 标签；
- 8 条缺 evidence sufficiency（证据是否足够）判定；
- 1 条关系探索缺任务契约；
- 1 条旧负例缺任务契约。

建议资产处置：

| 处置 | 数量 | 含义 |
|---|---:|---|
| `retain` | 3 | 问题和相关集基本可用，仍需人工确认 |
| `repair` | 9 | 有产品价值，补少量任务/标签后进入 12 条校准集 |
| `diagnostic` | 4 | 保留暴露未来能力缺口，不进入首轮总分 |
| `retire` | 16 | 重复、过度虚构或短期无法形成可解释评分，停止消耗标注成本 |

最重要的问题不是“负例不够多”，而是负例没有建立可检查的 `claim -> supporting/contradicting evidence -> expected verdict`。仅把 `relevant=[]` 当成负例，会错误地把“检索到用于反驳的证据”判成失败。

## 2. 逐条审计

### 2.1 原有 12 条主问题

| ID | 当前任务 | 处置 | 主要原因 | 修复方向 |
|---|---|---|---|---|
| RQ01 | trend_discovery | `repair` | 核心用户问题；15 个 relevant、cutoff=10，Recall 上限只有 0.667；相关集为 sampled 且未人工确认 | 固定趋势定义、分级相关性和来源多样性；主看 NDCG/coverage，不用 F1 单独决策 |
| RQ02 | evidence_research | `repair` | “最近有哪些重要动态”本质是公司趋势发现；当前 relevant 混入低相关外围文章 | 改为 trend_discovery；复核时间窗、官方/媒体证据等级 |
| RQ03 | evidence_research | `repair` | 与 RQ02 同类，任务路由不一致；当前 0 命中是有价值退化信号 | 改为 trend_discovery；复核 Anthropic/Claude 别名与相关集 |
| RQ04 | evidence_research | `repair` | 已把“最近”改成“当前语料”，但 relevant 是 sampled 项目列表，完整性不明 | 明确为 evidence_research；冻结候选池并补齐可接受项目集合 |
| RQ05 | trend_discovery | `repair` | 来源+主题路径重要，但 3 个 Product Hunt URL 是否覆盖窗口内全部 MCP 产品尚未复核 | 固定窗口和来源；核对候选全集与 URL canonicalization |
| RQ06 | evidence_research | `repair` | 与 RQ04 同类；“值得关注”隐含质量阈值尚未写入合同 | 固定候选池、开源定义与关注阈值 |
| RQ07 | item_navigation | `repair` | cutoff=1，却把官方条目和次级报道同时列为 relevant，导致正确 Top-1 的 Recall 只有 0.5 | 导航 gold 只保留唯一 canonical target；次级报道移出导航相关集 |
| RQ08 | item_navigation | `retain` | 唯一标题、唯一官方目标、cutoff=1，当前 1.0 命中 | 人工确认 canonical target 后保留 |
| RQ09 | item_navigation | `retain` | 唯一事件与官方目标明确；当前失败反映真实召回问题，不是标签结构问题 | 人工确认标题别名后保留 |
| RQ10 | relation_exploration | `diagnostic` | 关系/事件簇任务尚无输出和评分契约 | 等最小时间图谱与 relation contract 成立后再评分 |
| RQ11 | item_navigation | `retain` | 单一官方事件目标明确；当前失败有诊断价值 | 人工确认 canonical target 后保留 |
| RQ12 | claim_verification | `diagnostic` | 虚构实体可测拒答，但当前 evaluator 只会检查“是否返回结果”，不能判断证据是否足够 | 保留作 evidence sufficiency 未来测试，不进入首轮总分 |

### 2.2 20 条附加负例

| ID | 负例类型 | 处置 | 判断 |
|---|---|---|---|
| HN01 | entity_absent | `retire` | 与 RQ12 的虚构 GPT 控制高度重复 |
| HN02 | entity_absent | `retire` | “Claude 12 Atlantis/海底机器人”过度虚构，不能代表真实用户误解 |
| HN03 | entity_absent | `repair` | WeatherNext 与火星形成近邻误导，适合作为首轮证据不足测试 |
| HN04 | claim_refutation | `retire` | Apple/OpenAI 虚构产品与已有更贴近真实文档的 HN19 重复 |
| HN05 | entity_absent | `retire` | 虚构 Product Hunt 项目，和核心用户路径距离较远 |
| HN06 | entity_absent | `repair` | `telepathy-agent` 与现有 telepathy 近邻内容可能发生误召回，适合作为首轮证据不足测试 |
| HN07 | claim_refutation | `retire` | 虚构收购，当前无 claim contract，短期标注收益低 |
| HN08 | claim_refutation | `retire` | 量子纠缠属于明显荒诞断言，不能有效区分中等质量系统 |
| HN09 | entity_absent | `retire` | 与其他虚构模型负例重复 |
| HN10 | entity_absent | `retire` | 与其他虚构模型负例重复 |
| HN11 | claim_refutation | `retire` | 脑机接口插件过度虚构，现实代表性低 |
| HN12 | claim_refutation | `retire` | “芯片内置 RAG 数据库”过度虚构，现实代表性低 |
| HN13 | entity_absent | `retire` | 与其他虚构榜单/模型负例重复 |
| HN14 | claim_refutation | `retire` | 联合国协议断言距离当前核心产品路径较远 |
| HN15 | claim_refutation | `retire` | 绝对化断言可轻易拒绝，区分度低 |
| HN16 | claim_refutation | `diagnostic` | 基于真实 OERX 条目制造错误含义，是高价值困难反驳样本，但不属于“证据不足” | 留待 claim verification 阶段标注 `contradicted` |
| HN17 | claim_refutation | `retire` | 高风险武器断言并非首轮产品重点，且与 HN16/HN19 相比标注成本更高 |
| HN18 | claim_refutation | `retire` | 核电站部署属于过度极端场景，不能代表常见误解 |
| HN19 | claim_refutation | `diagnostic` | 基于真实标题制造错误结论，是高价值困难反驳样本，但不属于“证据不足” | 留待 claim verification 阶段标注 `contradicted` |
| HN20 | claim_refutation | `retire` | 与 HN03 同为 WeatherNext 错误场景，保留一个即可 |

## 3. 推荐的 12 条校准集来源

| 产品行为 | 候选 | 进入前必须修复 |
|---|---|---|
| 趋势发现 4 条 | RQ01、RQ02、RQ03、RQ05 | 任务归类、时间窗、分级相关性、来源多样性 |
| 精确导航 4 条 | RQ07、RQ08、RQ09、RQ11 | RQ07 移除次级目标；其余人工确认 canonical URL |
| 证据研究 2 条 | RQ04、RQ06 | 冻结候选池、明确“值得关注”的相关性规则 |
| 证据不足 2 条 | HN03、HN06 | 近邻证据、expected=`insufficient`、禁止把相似实体当成目标实体 |

这 12 条不是为了覆盖所有 RAG 能力，而是为了覆盖当前最重要的产品承诺并保护关键底线。

## 4. 本轮不应做的事情

1. 不把 32 条全部补成 gold；边际收益过低。
2. 不用一个宏平均 F1 混合趋势、导航、研究和拒答。
3. 不把关系探索的未实现合同记成 0 分。
4. 不把任何检索结果都视为负例失败；反驳本身也需要检索证据。
5. 不调用 LLM 自动生成更多负例，直到现有 12 条能证明评估器有辨别力。

## 5. 下一步（需确认后执行）

为上述 12 条建立独立 `gold-candidate-v1`，逐条补齐任务合同和证据标签，但仍标记为 `human_review_pending`。先用三个手工构造结果集验证评估器辨别力，再运行当前系统基线。
