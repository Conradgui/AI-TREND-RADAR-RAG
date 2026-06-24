# Evidence: P1 Evaluation Set Expansion Draft

Date: 2026-06-24

## Scope

Expanded the golden-question set from 5 to 12 questions.

The new draft questions cover:

- AI Agent graph relationship coverage;
- AI coding and developer tools;
- Product Hunt source-specific discovery;
- OpenAI trend synthesis;
- repeated cross-source themes;
- commercial-success evidence sufficiency;
- source-signal comparison.

## Files Added Or Updated

- `docs/rag-transformation/evals/golden-questions.json`
- `docs/rag-transformation/evals/golden-questions.md`
- `docs/rag-transformation/evals/golden-questions-readiness-2026-06-24.json`
- `rag/query_understanding.py`
- `rag/retrieval_planning.py`
- `rag/answer_policy.py`
- related focused tests

## Readiness Summary

Golden-question validation:

```json
{
  "total": 12,
  "answerability": {
    "internal-only": 9,
    "needs-web": 2,
    "insufficient": 1
  },
  "needs_conrad_review": 12
}
```

Query-plan summary:

```json
{
  "total": 12,
  "needs_web_search": 2,
  "with_metadata_filter": 10,
  "intents": {
    "evidence_sufficiency": 1,
    "learning_map": 1,
    "product_update": 1,
    "recent_trend": 5,
    "source_specific_discovery": 3,
    "technical_comparison": 1
  }
}
```

Corpus-availability summary:

```json
{
  "total": 12,
  "likely_has_corpus_evidence": 11,
  "likely_missing_corpus_evidence": 1,
  "needs_web_but_has_local_signals": 2
}
```

## Focused Verification

Command:

```bash
python3 -m unittest rag.tests.test_retrieval_planning rag.tests.test_query_understanding rag.tests.test_eval_query_plans -v
```

Result:

```text
Ran 19 tests in 0.028s
OK
```

## Canonical Verification

Command:

```bash
pnpm rag:check:p0
```

Result:

```text
Ran 161 tests in 0.283s
OK
```

## Issues Found And Fixed

1. Mixed-source comparison questions only retained the GitHub filter.
   - Fix: retrieval planning now supports `$or` filters for GitHub plus Product Hunt.

2. Evidence-sufficiency questions were treated as ordinary internal-grounded questions.
   - Fix: answer policy now has `evidence_sufficiency_review`.

## Interpretation

The evaluation set is broader and better aligned with the intended research-cockpit product.

Q6-Q12 are still review drafts. They should guide development, but final product judgment remains with Conrad.

## Residual Risks

- No live 12-question LLM benchmark has been run yet.
- Keyword-based corpus availability does not prove semantic sufficiency.
- Q11 intentionally tests insufficiency even though the corpus contains commercial-signal keywords.
