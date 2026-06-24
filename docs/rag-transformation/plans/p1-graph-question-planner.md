# P1 Graph Question Planner Plan

## Module

P1 Graph Question Planner

## Why This Module Matters

Graph RAG should not only store graph data. It needs to recognize when a user question is asking for relationship evidence.

Example:

- "RAG 相关主题是否跨多个日期和来源反复出现？"

This question should use entity/topic/date/source relationships, not only ordinary vector retrieval.

## Definition Of Done

Product behavior:
- The project can detect graph relationship questions for seeded entities such as RAG, OpenAI, and AI Agent.
- The system can produce graph-derived evidence for entity/topic/date/source questions.

Engineering behavior:
- A deterministic graph question planner exists.
- A service helper can query Neo4j for graph relationship evidence and format it as citation-ready evidence.
- A live smoke evaluator can verify the planner against local Neo4j.

Evidence behavior:
- Live graph planner output is saved under `docs/rag-transformation/evals/`.
- Evidence and execution logs record the test results and residual risks.

Evaluation behavior:
- Focused planner/service tests pass.
- Canonical `pnpm rag:check:p0` passes.
- Live graph planner smoke passes for at least one seeded question.

Non-goals:
- No LangGraph-style workflow agent.
- No broad natural-language-to-Cypher parser.
- No original AI Trend Radar UI integration.
- No claim that semantic answer correctness is fully solved.

Residual risks:
- Planner coverage is intentionally narrow.
- Graph entity normalization remains shallow.
- Chat UI does not yet expose a dedicated graph-reasoning mode.

## Verification Table

1. Add planner tests -> verify graph questions are detected and generic questions are not.
2. Add graph reasoning service tests -> verify graph evidence and citation formatting.
3. Add live graph planner smoke -> verify Neo4j graph evidence is retrievable.
4. Wire canonical scripts -> verify deterministic suite and compile checks.
5. Record evidence, execution log, roadmap/spec updates, and secret scan.
