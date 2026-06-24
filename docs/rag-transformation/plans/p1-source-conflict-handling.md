# P1 Source Conflict Handling Plan

Date: 2026-06-23

## Module

P1 Source Conflict Handling

## Concept

Source conflict handling means the system should not treat every citation as equally strong.

At this stage, the goal is not full automated fact arbitration. The goal is a minimal deterministic source review that tells the answer layer which sources are primary evidence, which sources are supporting context, and which sources require uncertainty.

## Definition of Done

Product behavior:

- Official, academic, and developer sources are treated as primary evidence.
- Trusted media can support claims but should not override primary sources.
- Generic and social sources are treated as weak context or as requiring verification.
- Answers receive explicit instructions when evidence is weak or mixed.

Engineering behavior:

- Add source review helper for citations.
- Add source review trace to `query_understanding`.
- Add source review instructions to the prompt.
- Keep behavior deterministic and testable.

Evidence behavior:

- Source review output exposes counts and source roles.
- Residual risks are recorded.

Evaluation behavior:

- Unit tests cover official-plus-generic, weak-only, and internal-only scenarios.
- Chat service test verifies source review reaches `query_understanding`.
- Canonical check passes.

Non-goals:

- Do not implement full semantic contradiction detection yet.
- Do not add a new LLM judge.
- Do not add a new framework.

Residual risks:

- Semantic contradictions still need a future claim-level comparison module.
- Source quality is domain-based and may misclassify edge cases.
