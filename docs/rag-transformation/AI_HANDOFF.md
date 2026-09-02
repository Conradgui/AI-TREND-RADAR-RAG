# AI Development Handoff

> 唯一动态状态入口：[CURRENT_CONTROL.md](CURRENT_CONTROL.md)。恢复工作先看它，再读当前计划与受影响 spec；不要从下方历史阶段列表推断当前待办。

> 当前正式执行合同：[G0–G4 收敛实施计划与 Stage Gate](plans/2026-08-26-g0-g4-implementation-and-stage-gates.md)。G0、G1、G2 已通过；G3 的 Runner、PR/Pages、无变化幂等性和 Docker 单日期复核已通过，仅真实新日期首写仍待上游增量；G4 用户部署验收本批暂不推进。

> 当前续接入口（2026-09-02）：先读取 [CURRENT_CONTROL.md](CURRENT_CONTROL.md)、当前计划和受影响 spec，再参考下方历史流程。不要重做已接通的 A–E 路由/原子入库，也不要在没有新上游日期时重复同步或重建 Docker；代码发布分支按用户要求为 main。G3 证据见 [Runner 与 canary 执行记录](execution-log/2026-09-01-g3-runner-and-canary.md)。

Initial document date: 2026-06-25 · Dynamic status: 2026-09-02

## 1. Purpose

This document lets a new AI coding assistant continue AI Trend Radar RAG without relying on prior chat history.

It summarizes the product direction, execution loop, evidence policy, roadmap sequence, and operating constraints that must be preserved across Codex, Claude Code, Cursor, or other AI coding tools.

## 2. Read Order For New Agents

Read these files before making changes:

1. `AGENTS.md`
2. `docs/rag-transformation/AI_HANDOFF.md`
3. `docs/rag-transformation/roadmap.md`
4. `docs/rag-transformation/specs/2026-06-22-target-architecture-spec.md`
5. `docs/rag-transformation/specs/2026-06-22-execution-loop-spec.md`
6. `docs/rag-transformation/specs/2026-06-21-quality-governance-spec.md`
7. The current module spec or plan.

Use `rg`, `jq`, and focused summaries before reading long raw artifacts.

## 3. Product Direction

AI Trend Radar RAG should become a local AI research cockpit.

The current product path is:

```text
fresh AI Trend Radar corpus
    -> citation-ready ingestion
    -> vector + graph retrieval
    -> controlled Agent/tool routing
    -> evidence-governed Trend Brief artifacts
    -> local dashboard cockpit
    -> stronger Agent ability
    -> better evidence selection
    -> unified local demo workspace
```

The project should not become a generic search chatbot, benchmark-only project, detached UI redesign exercise, premature desktop app, or tangled merge of AI Trend Radar and AI Trend Radar RAG.

## 4. Current Stage Sequence

1. P2 Trend Brief / Evidence foundation
   - Existing RAG evidence and Trend Brief capabilities provide the research-artifact foundation.

2. Stage 2.4 Local Product Flow And Dashboard Closure
   - Reuse AI Trend Radar `index.html`.
   - Make the local FastAPI runtime open into the report dashboard.
   - Wire Agent to local `/chat`.
   - Add Briefs and System areas.

3. Stage 2.5 Agent Ability Closure
   - Add report context, task modes, compact tool traces, better failure behavior, and cost/latency guardrails.

4. Stage 2.6 Evidence Selection Quality
   - Improve relevance, reranking, source quality weighting, deduplication, source diversity, freshness, and real-failure evaluation.

5. Stage 2.7 / Former Stage 2.5 Unified Local Demo Workspace
   - Reduce two-project friction after local cockpit and Agent value are proven.
   - Do not start with a full app or deep code merge.

6. Future Local App
   - Only after repeated real use proves the cost is justified.

## 5. Current Stage 2.4 Intent

Stage 2.4 is not "make a new design."

It means:

- use the existing AI Trend Radar Web UI as product shell;
- serve it from the local RAG runtime;
- keep report reading as the first screen;
- connect local Agent, citations, Briefs, and System status;
- avoid breaking static GitHub Pages mode.

Current Stage 2.4 source documents:

- `docs/rag-transformation/specs/2026-06-25-stage-2-4-local-rag-cockpit-spec.md`
- `docs/rag-transformation/plans/stage-2-4-local-rag-cockpit-implementation.md`

## 6. Loop V2.2 Summary

Each substantial module follows:

1. Orient.
2. Explain.
3. Define Done.
4. Implement Minimally.
5. Verify Precisely.
6. Review At The Right Gate.
7. Record Evidence At The Right Granularity.
8. Decide Next.
9. Checkpoint To GitHub At Stage Gates.

The loop prevents two failures: hacking features until they merely run, and over-testing or over-documenting until product progress stalls.

## 7. Evidence Policy

Evidence is required, but evidence is not always the mainline.

Use evidence to prove corpus freshness, citation grounding, retrieval behavior, source quality, API/runtime behavior, artifact usefulness, and residual risks.

Do not repeatedly tune a draft benchmark as if it were the product, expand architecture to satisfy one draft test, treat "has citations" as research quality, or hide weak evidence behind successful runtime checks.

For live external modules, distinguish:

- `research_quality_verified`: key claims have relevant primary or high-quality sources;
- `runtime_verified`: workflow ran, but evidence is weak, mixed, or incomplete;
- `blocked`: core claims cannot be supported safely.

## 8. Planning And Spec Policy

Roadmap, spec, and plan have different jobs:

- roadmap: what to build and in what order;
- spec: quality bar, architecture boundary, and acceptance rules;
- plan: concrete implementation sequence;
- decision: durable tradeoff or direction choice;
- evidence: proof and residual risk;
- execution log: what happened.

Do not use a plan as proof that work is done.

Update large planning documents at stage gates, module completion, major product/architecture decisions, live artifact gates, or user-requested governance refresh.

## 9. Review And Quality Gates

Use the gate that matches risk:

- Small change: self-review and focused check.
- Module completion: focused tests, evidence, execution log, and maintainability review.
- Phase/stage completion: broader smoke, residual risk review, roadmap update, checkpoint.
- Cross-project integration: explicit product/architecture review, secret safety review, integration tests.

Before important code, answer:

1. Which layer is this? Data / Index / Retrieval / Evidence / Agent / Evaluation / Runtime / Research Artifact / Integration.
2. What are the inputs and outputs?
3. Does it introduce a data or evidence boundary?
4. Does it reuse existing modules?
5. Does it make future UI, Stage 2.7, or local app integration harder?
6. Is there an official or authoritative component that should be reused?

## 10. Verification Policy

Use the cheapest sufficient verification:

- docs/config/eval artifacts: schema or text checks;
- single module behavior: focused tests;
- shared RAG path: `pnpm rag:check:p0`;
- local runtime behavior: local smoke;
- DeepSeek/search live behavior: explicit live gate with saved evidence.

Do not run global checks after every small edit.

Run broad checks when touching shared runtime path, retrieval/citation/answer policy, server endpoints, provider routing, secrets/deployment boundaries, or cross-project integration.

## 11. Decision Boundaries

AI assistants may decide narrow implementation details, focused tests, small docs structure, local helper modules, and small trusted dependencies when necessary and documented.

Ask Conrad before major product direction changes, large dependency or framework adoption, LangChain/LangGraph introduction, original AI Trend Radar online UI changes, paid services or new secrets, destructive file operations, or treating draft evaluation questions as official gates.

## 12. Coding Style And Maintainability

Use existing project patterns.

Avoid provider-specific logic leaking into core RAG logic, hidden global state, inconsistent citation/evidence schemas, dead flags, orphan code, custom infrastructure where official components are sufficient, and broad refactors unrelated to the module.

If a long-term issue does not block the current module, record it as residual risk or follow-up.

## 13. Git And Checkpoint Protocol

Checkpoint branch:

```text
codex/rag-transformation-checkpoints
```

Checkpoint after a completed stage, completed roadmap module with shared-path impact, live smoke verified artifact, major spec/roadmap/architecture update, or critical shared-path bug fix.

Before checkpoint:

- inspect `git status --short`;
- run `git diff --check`;
- run the minimum verification required by risk;
- scan for secrets;
- review staged file list.

Do not commit `.env`, `.venv/`, `node_modules/`, caches, local DB/vector artifacts, or real API keys/tokens.

## 14. Known Documentation Drift To Watch

Some older files use "Stage 2.5" to mean unified local demo workspace.

The current route treats that content as:

```text
Stage 2.7 / Former Stage 2.5 Unified Local Demo Workspace
```

Do not delete older decision history. Add clarifying notes or new decisions when needed.

Some older files describe the RAG implementation as LangGraph-based. Current implementation should be verified from code before claiming LangGraph is actually used.

## 15. Current Worktree Caution

Before editing:

- check `git status --short`;
- avoid mixing unrelated historical dirty files into a checkpoint;
- stage only current-module files unless doing a deliberate baseline checkpoint.

## 16. Communication With Conrad

Use Chinese.

Explain concepts before implementation.

For technical decisions, cover:

1. what the decision is about;
2. alternatives and why they exist;
3. engineering tradeoffs;
4. product meaning.

Do not over-praise or blindly agree. Push back when a request increases scope, cost, or architectural risk without enough product value.
