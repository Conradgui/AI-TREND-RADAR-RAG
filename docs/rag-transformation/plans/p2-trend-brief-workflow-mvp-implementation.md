# P2 Trend Brief Workflow MVP Implementation Plan

## Module

P2 Trend Brief Workflow MVP Implementation

## Definition Of Done

Product behavior:
- A user can generate a Markdown trend brief for a topic, starting with `RAG`.
- The brief distinguishes supported signals, uncertainty, graph coverage, and follow-up actions.
- The brief does not overclaim graph evidence as causality, adoption, or commercial success.

Engineering behavior:
- Reuse existing query understanding, citations, answer policy, source review, and graph reasoning modules.
- Avoid LangChain/LangGraph or LLM-assisted writing in the first deterministic MVP.
- Keep runtime dependencies lazy so unit tests do not require Neo4j or ChromaDB.

Evidence behavior:
- Focused unit tests cover the brief schema and evidence boundaries.
- `pnpm rag:check:p0` includes the new module and tests.
- A local smoke should generate a real Markdown artifact under `docs/rag-transformation/briefs/` when local service execution is permitted.

Non-goals:
- No UI dashboard.
- No original AI Trend Radar UI integration.
- No external search or DeepSeek call.
- No Stage 2.5 repo unification.

Residual risks:
- Deterministic assembly can organize evidence but cannot prove semantic correctness.
- Runtime smoke depends on local Neo4j/Chroma access.
