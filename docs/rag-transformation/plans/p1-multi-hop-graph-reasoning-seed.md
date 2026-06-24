# P1 Multi-Hop Graph Reasoning Seed Plan

## Module

P1 Multi-Hop Graph Reasoning Seed

## Why This Module Matters

Current Graph RAG verification proves that graph citations can be returned. It does not prove that the system can reason over graph structure.

This module adds a deterministic seed for graph relationship coverage:

- entity to topic;
- topic to date;
- topic to source;
- repeated topic/entity appearances across dates.

## Definition Of Done

Product behavior:
- The project can distinguish graph citation retrieval from multi-hop graph relationship readiness.

Engineering behavior:
- A CLI can query Neo4j and score seeded entity/topic/date/source relationships.
- The evaluator is covered by focused tests and canonical compile checks.

Evidence behavior:
- A graph reasoning matrix is saved under `docs/rag-transformation/evals/`.
- Evidence and execution log record whether the current graph layer supports seeded multi-hop paths.

Evaluation behavior:
- Focused tests pass.
- Live Neo4j graph reasoning matrix is generated.
- Canonical RAG check passes.

Non-goals:
- No full graph question-answer planner yet.
- No LLM answer rewrite.
- No graph schema migration unless the seed exposes a blocking gap.

Residual risks:
- This seed proves relationship availability, not final natural-language reasoning quality.
- More graph-specific questions are needed later.

## Verification Table

1. Add graph reasoning tests -> verify RED then GREEN.
2. Add graph reasoning seed and CLI -> verify live Neo4j matrix.
3. Wire canonical check -> verify local deterministic suite passes.
4. Record evidence and update roadmap/spec.
5. Run secret scan.
