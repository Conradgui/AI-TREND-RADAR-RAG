# P1 Claim-Level Evaluation Seed Plan

## Module

P1 Claim-Level Evaluation Seed

## Why This Module Matters

Current quality checks can verify citation structure, provider routing, source review traces, and whether external evidence exists. They do not yet check whether a final answer supports or avoids specific high-risk claims.

This module adds a small deterministic seed for claim-level checks. It is not a full semantic judge. It is a guardrail that catches obvious regressions such as unsupported performance claims, missing external evidence for needs-web questions, or failure to mark uncertainty.

## Definition Of Done

Product behavior:
- The project has an explicit seed of claim-level expectations for selected golden questions.
- Answers can be checked for required support, forbidden overclaims, and uncertainty language.

Engineering behavior:
- A local CLI can score a chat snapshot against the claim seed.
- The focused unit tests and canonical P0 RAG check include the claim evaluator.

Evidence behavior:
- The generated matrix records claim pass/fail status and residual product-review needs.
- Evidence and execution logs are saved under `docs/rag-transformation/`.

Evaluation behavior:
- Focused tests cover support, external-citation requirement, forbidden overclaim detection, uncertainty language, and summary counts.
- The current hybrid live snapshot is scored against the seed.

Non-goals:
- No LLM-as-judge.
- No full semantic contradiction detection.
- No claim extraction automation.
- No original AI Trend Radar UI change.

Residual risks:
- Seed wording is a product artifact and needs Conrad review later.
- Deterministic text checks can miss paraphrases.
- Passing this matrix does not prove full factual correctness.

## Verification Table

1. Add claim evaluator tests -> verify focused unit test passes.
2. Add deterministic evaluator CLI -> verify matrix generation works on the existing hybrid snapshot.
3. Wire canonical check -> verify `pnpm rag:check:p0` passes.
4. Record evidence -> verify roadmap/spec/evidence/execution-log are updated.
5. Run secret scan -> verify no local API key prefix appears in committed docs/code/eval output.
