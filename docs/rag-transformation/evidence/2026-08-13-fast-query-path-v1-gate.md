# Fast Query Path v1 离线 Gate

- 日期：2026-08-13
- 状态：`APPROVE`（只允许进入 Lean 3 条 API Canary）
- 正式链路影响：无

## 固定样本

- 6 条必须由 Fast Path 接受：4 条 A 导航、1 条禁网 B 趋势、1 条禁网 D 核验。
- 3 条复合任务必须明确返回 `fallback_required`：B+关系、B+核验、D+上下文反证。

## 结果

- 6/6 接受样本的 route、answer mode、权限、resolved references、protected terms 全部与校准 Gold 一致。
- 3/3 复合负例正确拒绝，没有静默坍缩到 E。
- 10 个 pytest 全部通过。
- 9000 次调用平均 `0.0103ms`，p50 `0.0088ms`，p95 `0.0123ms`；一次调度异常使 max 为 `23.0165ms`，均值远低于 `<10ms` Gate。

## 产品意义

高置信路径可以在无需模型、近乎无感延迟下完成；只有复合或低置信 Query 才需要付出模型调用成本。Fast Path 没有加入样本实体白名单，依靠定位器、硬约束和任务动作结构。

## 仍未证明

Fast Path 只是 9 条校准 Gate，不是泛化证据，也未接生产。Lean fallback 未通过前不能组合评估 12 条。
