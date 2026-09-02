# AI Trend Radar RAG Transformation

## 当前缺口与下一轮计划入口（2026-09-02）

请先阅读[当前推进控制面](CURRENT_CONTROL.md)和[全局缺口与后续收敛基线](plans/2026-08-26-global-gap-and-closure-baseline.md)：前者记录当前状态，后者记录已知缺口、知识反哺边界、候选阶段验收及模型分工。下方旧阶段说明保留为历史，不能据此判断最新功能尚未实现。当前 G0、G1、G2 已通过；G3 的 Runner、PR/Pages、无变化幂等性和 Docker 单日期复核已通过，新日期首写待上游实际增量；G4 用户部署验收暂不在本批范围内。

This folder is the durable project record for turning AI Trend Radar RAG from an experimental fork into a reliable personal AI research cockpit.

It exists for three reasons:

1. Keep the roadmap, decisions, plans, execution notes, and evidence outside chat history.
2. Make each module understandable before implementation, especially for a non-coding learner.
3. Prevent project drift by checking every execution step against the same source of truth.

## AI Handoff Entry

If a new AI coding assistant takes over this project, it must start from:

1. `AGENTS.md`
2. `docs/rag-transformation/AI_HANDOFF.md`
3. `docs/rag-transformation/roadmap.md`
4. `docs/rag-transformation/specs/2026-06-22-execution-loop-spec.md`
5. `docs/rag-transformation/specs/2026-06-21-quality-governance-spec.md`
6. `docs/rag-transformation/specs/2026-06-22-target-architecture-spec.md`

Do not rely on chat history as the source of truth.

## Current Product Boundary

AI Trend Radar is the data production system. It fetches AI signals, scores topics, generates reports, and publishes them to GitHub Pages.

AI Trend Radar RAG is the knowledge application system. It consumes AI Trend Radar's published corpus, builds retrieval and graph layers, powers an agent, and supports research workflows.

For the current phase, do not fix the Agent entry in the original AI Trend Radar web UI. First make AI Trend Radar RAG itself fresh, runnable, grounded, and testable.

Medium-term direction:

- keep two projects separate during current RAG core work;
- first close the Stage 2.4 local product/dashboard flow inside this RAG project;
- then improve Agent ability and evidence selection quality;
- after Nexus-like iteration and local cockpit validation, reduce deployment friction through the former Stage 2.5 unified local demo workspace, now treated as a later Stage 2.7 direction;
- do not jump directly into a full desktop/local software product unless repeated real use proves it is worth the cost.

## Folder Map

- `roadmap.md`: P0/P1/P2/P3 transformation roadmap.
- `AI_HANDOFF.md`: compact operating manual for future AI coding assistants.
- `plans/`: module-level implementation plans.
- `specs/`: quality governance and acceptance rules.
- `decisions/`: durable product and technical decisions.
- `execution-log/`: what was executed, when, why, and how it was verified.
- `evidence/`: command output summaries, screenshots, links, and verification notes.
- `evals/`: golden questions, expected behavior, and evaluation records.

面试与架构复盘入口：[Agentic RAG 面试能力矩阵（2026-08-28）](evidence/2026-08-28-agentic-rag-interview-readiness.md)。它把常见 RAG / Agent 问题映射到本项目的真实实现、证据边界和待补缺口，不能替代运行测试。

## Operating Protocol

Every substantial module must include:

1. Concept: what this module means in the RAG system.
2. Role: why it matters to the whole product.
3. Principle: how it works in plain language.
4. Business questions: what a senior AI PM or reviewer would ask.
5. Failure modes: how it can go wrong in real use.
6. Verification: how we prove the module improved the system.
7. Evidence: where the execution result is recorded.

## Roadmap vs Execution

The roadmap is not the implementation.

Use `roadmap.md` as the long-term direction and priority contract. Use files under `plans/` as the module-level execution guides. Use files under `specs/` as quality and execution rules. A module is not considered done because it is written in a plan; it is done only when the related code or data change has been verified and recorded under `evidence/` and `execution-log/`.

Use `specs/2026-06-22-target-architecture-spec.md` to understand the intended system layers:

- data;
- index;
- retrieval;
- evidence;
- agent;
- evaluation;
- runtime;
- integration.

Use `decisions/0004-official-components-and-custom-code-boundary.md` before expanding custom infrastructure. Generic capabilities should prefer official SDKs, authoritative libraries, or mature frameworks. Custom code should stay focused on AI Trend Radar-specific policy and glue.

For this project, each module should follow the execution loop in `specs/2026-06-22-execution-loop-spec.md`:

1. Orient.
2. Explain.
3. Define done.
4. Implement minimally.
5. Verify precisely.
6. Review at the right gate.
7. Record evidence.
8. Decide next.

## Current Phase

G3: 自动语料同步、发布幂等性与运行一致性收口；当前只等待上游出现真实新日期以完成首写观察，G4 用户部署验收暂不推进。

P0/P1 grounding and P2 Trend Brief / Evidence foundation exist. The current work has moved into G3 automated corpus sync and runtime consistency; the existing local cockpit, `/chat`, Briefs and System readiness surfaces remain the product boundary while the next real upstream date is observed.

# 当前执行计划

当前按 [G0–G4 收敛实施计划与 Stage Gate](plans/2026-08-26-g0-g4-implementation-and-stage-gates.md) 管理；G0、G1、G2 已通过，G3 为条件通过，严格新日期首写待外部来源增量；本批暂不推进 G4。
