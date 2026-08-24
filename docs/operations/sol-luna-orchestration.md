# Sol 主控、Luna/Terra 执行的项目协作方式

- 配置日期：2026-08-21
- 适用项目：AI Trend Radar RAG
- 目标：降低高价模型消耗，同时保留架构判断与最终验收质量

## 1. 结论

本项目采用三层能力路由，而不是“所有实现一律丢给 Luna”：

| 角色 | 模型 | 负责什么 |
|---|---|---|
| Controller | GPT-5.6 Sol / High | 产品目标、架构、计划、Stage Gate、整合、最终验收 |
| Efficient worker | GPT-5.6 Luna / Max | 范围清晰、接口已定、可独立验证的实现 |
| Complex worker | GPT-5.6 Terra / High | 跨模块、长上下文、共享接口、高风险或含歧义的实现 |

简单任务不派 Agent。一个实现默认只给一个 Writer；只有写入范围完全不重叠才允许并行。

## 2. 为什么不是无条件 Luna Max

OpenAI 官方将 Sol 定位为旗舰能力、Terra 定位为质量与成本平衡、Luna 定位为高吞吐工作负载；
官方也明确建议 `max` 只保留给最困难、质量优先且经过评估证明有增益的任务。因此 Luna Max
虽然单价低，但不等于总 token 必然最低。模糊任务、重复上下文和返工会吃掉节省。

社区流行的“Sol 规划、Luna 执行”方向成立，但部分 Codex 版本曾出现自定义 Agent TOML
被忽略、子 Agent 静默继承父模型的问题。因此本项目要求核验实际运行模型，不能只看配置文件。

## 3. 已完成配置

已安装：

- 项目级 `.codex/config.toml`：主控默认 `gpt-5.6-sol / high`，只影响受信任的当前仓库
- Codex marketplace：`sol-advisor`
- Plugin：`sol-advisor@sol-advisor`，安装时版本 `0.6.0`
- `~/.codex/agents/sol-advisor-luna-implementer.toml`
- `~/.codex/agents/sol-advisor-terra-implementer.toml`
- `~/.codex/agents/sol-advisor-sol-reviewer.toml`

安装器已执行 byte-for-byte `--check`，三个角色与插件模板完全一致。当前运行时还通过了
一次显式 `gpt-5.6-luna / max` smoke test，结果为 `LUNA_MAX_OK`，之后测试 Agent 已关闭。

本次没有修改 Docker、API Key、Provider、RAG 索引或产品代码。

## 4. 新任务如何使用

安装后的自定义角色只会在新建 Codex 任务时被发现。新任务中：

1. 从本仓库新建任务；受信任项目会自动读取 `.codex/config.toml`，主控应显示
   `GPT-5.6 Sol / High`。如未显示，先检查项目是否被标记为 trusted，再手动选择；
2. 对复杂、多模块或高风险任务使用：

   ```text
   Use $sol-advisor:orchestration to完成这个任务。先声明 SELECTIVE ROUTE，
   明确 done_when、写入范围、验证证据和停止条件，再决定直接执行、Luna Max、
   Terra High 或只读 Sol review。
   ```

3. 普通小改动不调用该 skill，避免编排开销；
4. 每个 Stage Gate 由 Sol 读取真实 diff 和测试证据后裁决，不接受 Worker 的口头 PASS。

## 5. 本项目的默认预算

- 默认 0 或 1 个执行 Agent；
- 原 Worker 最多一次聚焦修正；
- 只有 Stage Gate / 高风险变更才创建新鲜 Sol reviewer；
- 不让 Controller 与 Worker 重复读取整仓库；
- Worker 报告只返回：修改文件、需求覆盖、验证命令、结果、剩余风险；
- 模型不匹配、权限不明、范围冲突或验证失败时停止，不反复重试。

## 6. 验证与回退

检查角色文件：

```bash
plugin_dir="$(codex plugin list --json | jq -r '.installed[] | select(.pluginId == "sol-advisor@sol-advisor") | .source.path')"
sh "$plugin_dir/scripts/install-agents.sh" --check
```

如果新任务中 Luna 角色实际继承了 Sol/Terra：

1. 停止该 Agent；
2. 不把结果计入正式证据；
3. 改用当前 spawn API 的显式 `model=gpt-5.6-luna`、`reasoning_effort=max`；
4. 如果显式覆盖也失败，改成用户可见的独立 Luna 任务，不伪装成已降本。

卸载属于用户级配置删除，执行前必须单独列出插件与三个角色文件并再次确认。

## 7. 调研来源与证据边界

- [OpenAI GPT-5.6 model guidance](https://developers.openai.com/api/docs/guides/latest-model)：
  官方模型定位、reasoning effort 与 max 使用边界。
- [OpenAI Codex config basics](https://learn.chatgpt.com/docs/config-file/config-basic)：
  官方确认项目级 `.codex/config.toml` 的作用域与配置优先级。
- [OpenAI Codex app](https://openai.com/index/introducing-the-codex-app/)：
  官方多 Agent、隔离工作区与人工审阅方向。
- [OpenAI Cookbook ExecPlans](https://github.com/openai/openai-cookbook/blob/main/articles/codex_exec_plans.md)：
  持久化、可执行计划与证据驱动长任务方法。
- [Sol Advisor](https://github.com/DannyMac180/sol-advisor)：
  本次安装的第三方 MIT 插件及 fail-closed 角色安装器。
- [Codex issue #33881](https://github.com/openai/codex/issues/33881)：
  某些版本自定义 Agent 模型配置被忽略的已知风险。
- [X trend summary](https://x.com/i/trending/2084069564753596840)：
  “Sol 规划、Luna 执行”社区实践的发现入口；它是二手动态摘要，不作为配置正确性的证明。

第三方声称的 5–6 倍节省不是本项目实测，不能作为收益承诺。后续应记录 Controller 与 Worker
的调用数量、返工次数和验证通过率，再判断是否真正降低消耗。
