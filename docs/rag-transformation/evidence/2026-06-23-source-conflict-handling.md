# Evidence: P1 Source Conflict Handling

Date: 2026-06-23

## What Changed

- Added deterministic source review in `rag/source_review.py`.
- Added source roles:
  - `primary_evidence`
  - `supporting_context`
  - `weak_context`
- Added source review guidance to the chat system prompt.
- Added `query_understanding.source_review` to chat responses.
- Added unit tests for internal-only, mixed-quality, weak-only, and prompt formatting scenarios.

## Validation

Focused tests:

```text
python3 -m unittest rag.tests.test_source_review rag.tests.test_chat_service -v
Ran 10 tests
OK
```

Canonical check:

```text
pnpm rag:check:p0
Ran 126 tests
OK
```

## Product Behavior

The answer layer now receives deterministic source-quality guidance.

Examples:

- Official, academic, and developer sources are primary evidence.
- Trusted media is supporting context.
- Generic and social sources are weak context.
- Mixed official plus generic evidence tells the answer to use primary sources for strong claims and treat generic sources as context.
- Weak-only evidence tells the answer to state uncertainty and avoid strong factual claims.

## What This Does Not Claim

This is not full semantic contradiction detection.

The current module does not yet compare claim-by-claim statements such as:

- source A says a feature launched on one date;
- source B says another date;
- source C disputes the relationship between two frameworks.

That requires a later claim-level comparison module.

## Residual Risks

- Domain-based source quality can misclassify edge cases.
- Prompt guidance relies on the LLM following instructions.
- Future evaluation should add answer-quality checks for weak-only and mixed-source scenarios.
