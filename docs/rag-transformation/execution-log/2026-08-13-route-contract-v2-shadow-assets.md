# Route Contract v2 影子资产执行记录

- 日期：2026-08-13
- 状态：完成；Stage Gate `APPROVE`
- 正式流量影响：无
- 正式检索/索引影响：无

## 产品确认

- B `trend_discovery`：回答“最近发生了什么、什么值得关注”；
- C `temporal_relation_exploration`：回答“如何演变、彼此有什么关系、跨时间或跨实体形成什么结构”；
- “最近有什么趋势”默认进入 B；明确要求演变、关系或结构时进入 C。

## 产物

- `docs/rag-transformation/specs/route-contract-v2.schema.json`
- `docs/rag-transformation/specs/route-contract-v2-expected-projection.schema.json`
- `docs/rag-transformation/evals/route-contract-v2-development-2026-08-13.json`
- `rag/route_contract_validation.py`
- `rag/tests/test_route_contract_v2_assets.py`

## TDD 证据

### Red

首次运行 5 项合同测试时，Schema 和开发集尚不存在，5 项全部失败。强化阶段再次先加入真实 Schema 校验和退化 mutation；由于语义校验器尚不存在，测试在收集阶段失败。

### Green

执行：

```bash
PYTHONPATH=.test-deps:. python3 -m pytest -q rag/tests/test_route_contract_v2_assets.py
```

结果：

```text
7 passed, 28 subtests passed in 0.21s
```

另外完成：两个 Schema、开发集均通过 JSON 解析；`git diff --check` 通过。

## 测试环境

仓库路径包含 `:`，Python 拒绝在该路径创建 venv。测试依赖因此安装到被 `.gitignore` 排除的项目隔离目录 `.test-deps`；`jsonschema` 同步加入 `rag/requirements-dev.txt`，避免 CI 和新环境缺少合同验证依赖。

## 独立质量监管

首次结论为 `BLOCK`，原因是：Expected 不是完整合同、Schema 没有约束 A–E 跨字段一致性、测试无法识别退化。修订后最终结论为 `APPROVE`。

允许进入：不接正式检索链的 Route Contract v2 影子理解器。

仍未证明：实体、主题、时间和来源约束抽取质量。这些字段需在影子阶段增加人工 Gold 与单独指标后才能评价。

## 影子理解器最终 Gate

独立监管连续发现并要求关闭：联网否定反转、未知实体、上下文引用未进入合同、A 路由辅助任务不可执行、模糊指代高置信、左右位置与多次 `它` 漏检。所有阻断项均先补失败探针再最小修复。

最终验证：

```text
66 passed, 28 subtests passed
开发集五条路线各 5/5
Schema / semantic / route / answer mode / policy fields = 100%
protected_terms micro F1 = 97.93%
```

最终监管结论：`APPROVE`。允许冻结影子资产并创建全新 query-only sealed blind test；仍禁止生产接入。

注意：25 条开发集和已经解封的 50 条挑战集都只能作为校准证据，不得作为泛化成绩。
