# Evidence: P1 Retrieval Precision / Reranking Seed

Date: 2026-06-23

## Scope

Added a deterministic retrieval precision benchmark for selected golden questions.

This module classifies citations as:

- `relevant`: directly matches the question's expected evidence terms;
- `redundant`: repeats an already relevant title/source;
- `distracting`: matches known off-topic signals;
- `weak`: structurally valid but not clearly relevant to the seeded question.

## Files Added Or Updated

- `rag/eval_retrieval_precision.py`
- `rag/tests/test_eval_retrieval_precision.py`
- `docs/rag-transformation/evals/retrieval-precision-seed-2026-06-23.json`
- `docs/rag-transformation/evals/retrieval-precision-matrix-2026-06-23.json`
- `docs/rag-transformation/plans/p1-retrieval-precision-reranking-seed.md`
- `package.json`

## Focused Verification

Command:

```bash
python3 -m unittest rag.tests.test_eval_retrieval_precision -v
```

Result:

```text
Ran 4 tests in 0.000s
OK
```

Covered behaviors:

- relevant, redundant, distracting, and weak citation classification;
- pass case when relevant count and noise rate are acceptable;
- failure case when distracting rate is too high;
- summary counts for failures and distracting citations.

## Snapshot Evaluation

Command:

```bash
python3 -m rag.eval_retrieval_precision --input docs/rag-transformation/evals/hybrid-live-chat-snapshot-2026-06-23.json --seed docs/rag-transformation/evals/retrieval-precision-seed-2026-06-23.json --output docs/rag-transformation/evals/retrieval-precision-matrix-2026-06-23.json
```

Result:

```json
{
  "total": 3,
  "passed": 0,
  "failed": 3,
  "citation_count": 32,
  "distracting_count": 3,
  "failure_counts": {
    "redundant_rate_too_high": 2,
    "distracting_rate_too_high": 1,
    "weak_rate_too_high": 1
  }
}
```

## Findings

Q1:

- enough relevant citations;
- failed because repeated topics such as `safishamsi/graphify` and `mindsdb/minds-platform` inflate redundancy.

Q2:

- enough relevant citations and external academic references;
- failed because repeated generic `ai-topic-radar` and repeated project citations inflate redundancy.

Q5:

- only 2 clearly relevant citations, both external;
- 3 distracting citations were detected: DiffusionGemma, GLM, and Vue3 coding-practice items;
- 7 weak citations were detected, mostly broad Google/agent ecosystem context rather than direct OKF/ALM evidence.

## Canonical Verification

Command:

```bash
pnpm rag:check:p0
```

Result:

```text
Ran 140 tests in 0.070s
OK
```

## Interpretation

The evaluator itself is working and CI-ready. The retrieval result quality is not yet acceptable under this seed.

This is a benchmark failure, not a test-suite failure. It should drive the next implementation module: citation deduplication and noise filtering before or during reranking.

## Residual Risks

- Term-based relevance is coarse and needs Conrad review.
- Some weak Q5 citations may provide useful background context, but they should not dominate the citation set.
- A future reranker may need both deterministic filters and semantic scoring.
