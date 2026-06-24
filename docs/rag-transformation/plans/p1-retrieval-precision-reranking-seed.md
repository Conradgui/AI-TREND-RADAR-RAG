# P1 Retrieval Precision / Reranking Seed Plan

## Module

P1 Retrieval Precision / Reranking Seed

## Why This Module Matters

The system now returns citations, graph citations, external citations, and passes initial claim-level checks. The next risk is citation relevance: a retrieved citation can be structurally valid but still distract from the user's question.

This module creates a small deterministic benchmark for citation relevance. It does not change retriever ranking yet. It makes the ranking problem measurable first.

## Definition Of Done

Product behavior:
- The project can distinguish relevant, redundant, weak, and distracting citations for selected golden questions.

Engineering behavior:
- A local CLI can score retrieval precision from a chat snapshot.
- Focused unit tests cover citation classification and summary behavior.
- The evaluator is wired into local scripts and canonical compile checks.

Evidence behavior:
- A retrieval precision matrix is generated from the current hybrid live snapshot.
- Any noisy retrieval behavior is recorded as a quality gap instead of hidden.

Evaluation behavior:
- Focused unit tests pass.
- Canonical RAG check passes after adding the evaluator.

Non-goals:
- No reranking implementation in this module.
- No LLM-as-judge.
- No retriever architecture refactor.
- No original AI Trend Radar UI change.

Residual risks:
- Term-based relevance is coarse and can miss semantic relevance.
- Seed terms need product review and expansion.
- Fixing noisy citations belongs to the next reranking/filtering module.

## Verification Table

1. Add focused tests -> verify RED then GREEN.
2. Add retrieval precision evaluator -> verify focused tests pass.
3. Add seed and CLI script -> verify matrix generation on current hybrid snapshot.
4. Wire canonical check -> verify `pnpm rag:check:p0` passes.
5. Record evidence -> verify roadmap/spec/evidence/execution-log are updated.
6. Run secret scan -> verify no API key prefixes appear in code/docs/eval output.
