# Entity-aware recent route 小步计划

## 目标

修复“最近 Claude 有什么趋势”被误分为通用研究、时间条件丢失、官方外部证据无法进入正式引用的问题；同时建立产品与公司的可扩展关系，不把二者当作同义词。

## 范围

- `QueryRouteResolver` 的自然语言近期动态路由；
- `RouteContractV2` 的相对时间窗口传递；
- 外部发布类证据的准入映射；
- 产品/公司主体分离与低权重关系扩展；
- 旧事件记录的读取兼容。

## 非目标

- 不全量重建 ChromaDB/Neo4j；
- 不降低外部证据质量门槛；
- 不引入 LangChain/LangGraph 或新的检索引擎；
- 不重写 Web UI；
- 不把所有相关主体无条件合并到主答案。

## Definition of Done

- `最近 + 主体 + 趋势/动向` 无需模型调用即可进入 `trend_discovery`；
- `Claude`、`Anthropic`、`ChatGPT`、`OpenAI` 在查询层保持独立主体；
- 主体关系以带方向、权重的扩展记录表达；
- 最近 14 天条件进入 Route Contract 并投影到实际检索过滤；
- `important_news` 的官方发布证据可进入正式准入流程；
- 旧事件抽取测试和全量回归不退化；
- Docker 中真实 Claude 查询返回条目级引用。

## 后续待做

- ✅ 将实体注册表从 Python 常量迁移为版本化配置；
- 将注册表配置投影到图谱并提供管理校验；
- 为关系扩展增加主结果、补充结果的排序权重；
- 增加未知实体的 AI 兜底消歧与缓存；
- 用独立盲测集评估实体链接准确率和误扩展率。

## 本轮新增边界

- 已登记 Gemini、Google、Google DeepMind、Grok、Grok Bot、xAI、X、SpaceX、Antigravity；
- Gemini/Grok 的已确认关系可受控扩展；
- Antigravity、SpaceX 暂不自动扩展，避免把歧义主体或组织关联直接污染检索；
- `entity_registry.json` 是配置源，关系只有 `status=verified` 才进入运行时扩展。
