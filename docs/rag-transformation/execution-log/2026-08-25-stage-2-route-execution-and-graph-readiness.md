# Stage 2：路线执行策略与 Graph 就绪检查执行记录

- 日期：2026-08-25
- 状态：Gate 通过
- 范围：后端编排、Graph 主动检验与降级；未重建 Docker、索引或数据卷

## 已实现合同

| 路线 | 执行合同 |
|---|---|
| A 精确导航 | Lexical / ID，确定性渲染，0 次模型调用 |
| B 重要动态 | Structured recent，确定性渲染；强制联网只补证据，0 次模型调用 |
| B 趋势聚类 | 首轮候选上的受限 Graph 扩展，最多 1 次 Direct Composer |
| C 时间与关系 | Lexical + Vector + 必需 Graph，最多 1 次 Direct Composer |
| D 主张核验 | 文本证据优先，按需 Web，最多 1 次 Direct Composer |
| E 证据研究 | 文本证据优先，证据不足时按需 Web，最多 1 次 Direct Composer |

普通路线不再回退 ReAct。Direct Composer 不可用时明确返回
`generation_unavailable`，不会用多轮 Agent 掩盖运行时故障。

## Graph 就绪边界

- 启动时执行最小只读查询，并校验关键全文索引为 `ONLINE`；
- 启动时验证 `Observation` 与 `Content` 核心标签存在数据；
- 运行时只做带 TTL 缓存的轻量探针；
- C 路线在 Graph 不可用时显式降级/失败，不静默伪装完整关系回答；
- B 趋势聚类只对已排序候选 ID 做图扩展；
- Schema 初始化只创建约束和索引，不再夹带数据清理；
- 连接异常不会自动重建容器、镜像或索引。

## Gate 中发现并修复的阻断

1. 初审发现执行策略尚未完全被聊天主链消费，Graph 就绪检查缺少索引与核心标签验证；已补齐。
2. 复审发现强制联网的 `important_news` 会绕过零生成路径；已改为联网完成后仍确定性渲染。
3. 外部近期证据必须有可验证发布时间，抓取时间不能冒充事件时间；测试候选补齐发布时间，未放宽生产准入规则。
4. 最终复审发现 Composer 初始化失败时 C/D/E 会回退 ReAct；已改为确定性 fail-closed，并新增失败回归测试。

## 验证证据

```text
844 passed, 36 subtests passed in 15.80s
python -m compileall -q rag: PASS
git diff --check: PASS
独立质量监管关键 Gate: 101 passed, PASS
```

公共 `/chat` seam 已覆盖 A–E；重要动态强制联网、Composer 缺失、Graph 就绪与策略预算均有回归测试。

## 证据边界与下一阶段

- 已证明：静态路线预算、公共聊天路径、Graph 就绪识别和 fail-closed 行为。
- 尚未证明：真实 DeepSeek 下的端到端时延、分阶段超时与取消请求指标。
- 下一阶段：审计并补齐 Answer Envelope、证据 ID 校验和确定性 Renderer；随后进入分路线超时与可观测性。
