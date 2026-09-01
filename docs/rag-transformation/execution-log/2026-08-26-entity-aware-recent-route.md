# Entity-aware recent route 执行记录

## 变更

1. 近期主体+趋势表达补入确定性新闻发现规则。
2. `RouteContractV2` 从既有 QueryPlan 继承 7/14 天相对窗口，Gateway 再转换为现有日期过滤格式。
3. `important_news` 映射为 `product_release`，修复官方发布证据被标为 `unclassified` 的问题。
4. 将 Claude/Anthropic、ChatGPT/OpenAI 作为不同主体；增加 `developed_by`、`product_of` 关系扩展及权重。
5. 保留旧事件抽取的 ID 兼容层，避免历史图谱和旧测试被破坏。
6. 新增版本化 `entity_registry.json`，补入 Gemini/Google/Google DeepMind、Grok/Grok Bot/xAI/X、SpaceX、Antigravity；仅 `verified` 关系进入运行时扩展。
7. 在检索唯一排序汇合点加入主体层级：直接命中 > 已确认关系扩展 > 背景候选；每层内部仍按新鲜度、重要性和上游分数排序。
8. 查询入口改为从版本化注册表识别主体，长名称优先匹配，避免把产品变体误拆成公司或父产品。
9. Graph Reasoning 读取 `scope=entity_registry` 的影子关系，并把它们作为独立关系证据输出；正式新闻证据和关系证据仍分开。

## 验证证据

- focused routing/evidence/retrieval tests：通过；
- earlier route checkpoint：`876 passed, 36 subtests passed`；
- entity registry slice：`21 passed`，覆盖主体不合并、Gemini/Grok 受控扩展、歧义主体不自动扩展；
- 注册表装入 Docker app 后：app 与 Neo4j 均 `healthy`；未重建 Neo4j、未删除数据卷、未重建正式索引。
- 主体分层排序 slice：`19 passed`；全量回归：`882 passed, 36 subtests passed`；排序逻辑已装入 healthy app 容器。
- Docker app：仅更新 app 镜像，Neo4j 和数据卷未重建；
- 真实请求：最终 app 镜像重建后执行 `最近Claude有什么新的趋势吗?`，HTTP 200，约 18.8 秒；
- 真实结果：命中确定性 `important_news` 执行路径（未调用生成模型或 Agent 工具），返回 3 条条目级引用，其中包含 Anthropic 官方 Claude 动态；请求链路记录的检索耗时约 2.0 秒，其余时间主要来自服务端响应封装与运行时链路。
- 主体注册表投影安全 slice：`18 passed`，覆盖整批事务、失败回滚、禁止覆盖已有实体属性、版本/作用域隔离及非法配置预检；
- 真实 Neo4j 回滚探针：`REAL_NEO4J_ROLLBACK_PROBE=PASS`；测试节点未残留；
- 重启后基础设施恢复：现有 app 与 Neo4j 容器均 `healthy`，`/health` 返回 `neo4j_connected=true`、`retriever_mode=hybrid`、`chromadb_chunks=4133`、`index_status=ready`；未重建索引、未删除数据卷；
- 本轮完整回归：`894 passed, 36 subtests passed in 11.02s`；`git diff --check` 通过。
- 主体关系诊断回归集：8 条查询样例，覆盖 Claude/Anthropic、ChatGPT/OpenAI、Gemini/Google、Grok/xAI、SpaceX、Antigravity；主体入口和关联规则测试通过。
- 在查询入口修复后重新回归：`896 passed, 36 subtests passed in 6.70s`；`git diff --check` 通过。
- 新 app 镜像已重建并启动；Neo4j 未重建，`/health` 返回 healthy / hybrid / ready；容器内 Gemini、Grok、SpaceX 主体识别冒烟通过，SpaceX 无未授权扩展。
- 8 条主体关系诊断样例的排序测试通过：直接主体在关联主体分数更高时仍排在前面；
- 本轮完整回归：`897 passed, 36 subtests passed in 5.95s`；`git diff --check` 通过。
- 后端整合后 app 镜像重建完成，Neo4j 未重建；真实 Graph Reasoning 冒烟 `Claude → Anthropic / developed_by` 通过。

## 结论

本模块 `Locally Verified` + `Live Smoke Verified`。不宣称实体全量链接、图谱关系完整或整体召回率已达到目标；当前 8 条集合是诊断回归集，不是独立盲测集。下一阶段应冻结一份不参与调参的独立实体关系盲测集，再评估误扩展率和漏识别率。

## 断点恢复结论（2026-08-26）

- Docker 重启后的连接问题已通过既有 `/runtime/reconnect-databases` 运行时重连能力恢复，不需要重建容器；
- Neo4j 注册表投影代码已完成安全边界修复，但尚未作为启动流程自动执行，也未把注册表关系写入正式图谱；这保持了“先验证、后改变生产数据”的边界；
- 主体关系影子投影、查询扩展、主体层级排序和 Graph Reasoning 证据输出已打通；独立盲测和未知主体负例仍是后续评估工作，不阻塞当前链路运行。

## 影子投影运行探针（2026-08-26）

- 已完成本地事务与真实 Neo4j 回滚验证；
- 初次真实投影探针暴露性能问题：逐条写入在预期窗口内未返回，未据此宣称成功；
- 已改为同一事务内两次 `UNWIND` 批量写入，专项测试 `12 passed`；
- 批量影子投影已成功：`21` 个主体、`9` 条关系，Neo4j 实际查询也返回 `9` 条 `scope=entity_registry` 关系；
- 已移除临时复制进 app 容器的代码和注册表文件；正式索引未重建，现有检索路径不读取影子关系；
- 投影后的 `/health` 仍为 `neo4j_connected=true`、`retriever_mode=hybrid`、`index_status=ready`。
