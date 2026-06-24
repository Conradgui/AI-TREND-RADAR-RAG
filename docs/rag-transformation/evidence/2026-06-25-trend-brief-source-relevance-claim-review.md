# Evidence: P2 Trend Brief Source Relevance And Claim Review

Date: 2026-06-25

## Module

P2 Trend Brief Source Relevance And Claim Review

## Purpose

Add a deterministic evidence-relevance layer on top of source-domain quality.

The previous module proved that source quality could move from `weak_only` to `mixed_quality` and `research_quality_verified`. This module checks whether each external source actually supports the Trend Brief topic and claim family.

## External API Budget Strategy

External search API calls in this module: 0.

The module reused the existing live artifact:

```text
docs/rag-transformation/briefs/trend-brief-rag-source-quality-2026-06-25.md
```

Any future external evidence expansion should be planned as a batch before calling APIs.

## What Changed

Code changed:

- `rag/source_relevance.py`
  - adds deterministic source relevance classification.
  - supports `direct_support`, `partial_support`, `weak_context`, `irrelevant_context`, and `not_applicable`.
  - can inspect a saved Trend Brief Markdown artifact.
- `rag/trend_brief.py`
  - adds `source_relevance` into the machine-readable appendix for newly generated briefs.
- `rag/generate_trend_brief.py`
  - adds `source_relevance` into CLI summary.
- `package.json`
  - includes source relevance tests and py_compile in P0 checks.

Tests changed:

- `rag/tests/test_source_relevance.py`
- `rag/tests/test_trend_brief.py`
- `rag/tests/test_generate_trend_brief.py`

Artifacts/evals generated:

- `docs/rag-transformation/evals/trend-brief-source-relevance-2026-06-25.json`

## Verification

Focused:

```text
python3 -m unittest rag.tests.test_source_relevance rag.tests.test_trend_brief rag.tests.test_generate_trend_brief -v
```

Result:

- 19 tests passed.

Canonical:

```text
pnpm rag:check:p0
```

Result:

- 183 tests passed.
- `py_compile` passed.

Artifact relevance inspection:

- external citations: 3
- direct support: 1
- partial support: 1
- weak context: 1
- irrelevant context: 0
- relevance status: `relevance_verified`

## Artifact First Review

The saved RAG Trend Brief external sources now have a relevance matrix:

- `arxiv.org`: direct support for RAG retrieval/evaluation/benchmark claims.
- `braintrust.dev`: partial support for RAG evaluation tooling context.
- `en.wikipedia.org`: weak context for definition/background only.

This prevents a definition page from being treated as equal to claim-supporting evidence.

## Next-Step Bias

Next bottleneck: batched evidence acquisition planning.

The next module should not call external APIs one at a time. It should first list the claims and source types that need stronger support, then run a planned batch if external search is needed.

## Residual Risks

- Deterministic relevance scoring is keyword-based and coarse.
- It does not prove full semantic correctness.
- It is currently strongest for RAG-topic artifacts and should be generalized cautiously.
