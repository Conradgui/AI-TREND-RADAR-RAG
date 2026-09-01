# Stage 4：分路线预算、进度事件与可观测性执行记录

- 日期：2026-08-25
- 状态：Gate 通过
- 范围：运行时等待边界、流事件、外部搜索并发和超时指标；未重建 Docker 或索引

## 已实现合同

- 低置信语义路由：8 秒硬上限；
- A–E 路线分别配置检索、生成和总预算；
- HTTP / stream 最终安全兜底：70 秒；
- 进度事件统一为 `route_ready`、`retrieval_ready`、`retrieval_degraded`、
  `generation_started`、`failed`；
- Gateway 主动报告 timeout 与 `asyncio` 超时使用同一失败语义并记录指标；
- 外部最多 2 个 Provider 并发，只有通过证据准入门槛的结果可以早停；
- 同步 deep fetch 进入工作线程，不阻塞事件循环；
- UI 只展示执行阶段，不展示隐藏思维链。

## Gate 中发现并修复的阻断

1. Gateway 返回 `status=timeout` 曾被当作正常完成，未发失败事件、未记录指标；已统一处理。
2. 普通联网任务曾允许最快的 generic 结果抢跑并取消 official Provider；已把权威准入作为所有路线的早停门槛。

## 验证证据

```text
858 passed, 36 subtests passed in 26.03s
python -m compileall -q rag: PASS
git diff --check: PASS
独立质量监管关键 Gate: 82 passed, 3 subtests passed, PASS
```

## 下一阶段

只重建一次应用容器，保留数据卷与索引；随后用真实 DeepSeek 执行 A–E Canary，记录耗时、路线、模型调用次数与引用完整性。
