# P1 Evaluation Set Expansion Plan

## Module

P1 Evaluation Set Expansion Draft

## Why This Module Matters

The original five golden questions validated the first RAG path, but they were too narrow for ongoing product-quality control.

This module expands the evaluation set to cover:

- graph relationship trend questions;
- developer-tool and Product Hunt discovery;
- company-centered synthesis;
- repeated cross-source signals;
- evidence-sufficiency refusal behavior;
- source-signal comparison.

## Definition Of Done

Product behavior:
- The evaluation set covers more realistic research-cockpit usage scenarios.
- New questions remain marked for Conrad review until product judgment is confirmed.

Engineering behavior:
- JSON and Markdown golden-question assets are synchronized.
- Query understanding recognizes the new question types where needed.
- Retrieval planning supports mixed source filters such as GitHub plus Product Hunt.
- Evidence-sufficiency questions have a dedicated answer policy mode.

Evidence behavior:
- A readiness summary is saved under `docs/rag-transformation/evals/`.
- Evidence and execution logs record test results and residual risks.

Evaluation behavior:
- Golden-question validation passes.
- Query-plan and corpus-availability focused tests pass.
- Canonical `pnpm rag:check:p0` passes.

Non-goals:
- No claim that Q6-Q12 are final product labels.
- No live 12-question LLM benchmark in this module.
- No semantic reranker.

Residual risks:
- Q6-Q12 require Conrad review.
- Corpus availability is keyword-based and can detect local signals without proving sufficiency.
- Live behavior over all 12 questions still needs a separate benchmark run.
