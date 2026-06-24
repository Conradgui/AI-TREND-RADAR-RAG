# P1 Semantic Contradiction Detection Seed Plan

## Module

P1 Semantic Contradiction Detection Seed

## Why This Module Matters

RAG quality is not only about retrieving citations. A risky answer can still cite sources while overstating what those sources prove.

This module adds deterministic checks for high-risk answer contradictions:

- weak or mixed evidence but overconfident conclusions;
- external-paper claims without external citations;
- source-review warnings ignored by the final answer.

## Definition Of Done

Product behavior:
- The project can catch selected high-risk answer patterns before they become accepted benchmark results.

Engineering behavior:
- A semantic contradiction evaluator exists.
- The evaluator uses existing answer policy, source review, citations, and answer text.
- The evaluator is wired into the canonical local check.

Evidence behavior:
- Seed checks and matrix output are saved under `docs/rag-transformation/evals/`.
- Evidence and execution log record false-positive handling and residual risks.

Evaluation behavior:
- Focused tests prove bad patterns fail and conservative wording passes.
- The current hybrid after-filter snapshot passes the seed matrix.
- Canonical `pnpm rag:check:p0` passes.

Non-goals:
- No full automatic fact checker.
- No LLM-as-judge evaluator.
- No semantic entailment model.
- No claim that all hallucinations are detectable.

Residual risks:
- Coverage is narrow and seed-based.
- The quality of checks depends on carefully maintained marker lists and seed cases.
- Conrad should review future seed labels when product judgment is required.
