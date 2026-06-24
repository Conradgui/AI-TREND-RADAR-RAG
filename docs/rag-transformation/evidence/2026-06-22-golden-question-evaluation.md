# Evidence: Golden Question Evaluation Asset

## Date

2026-06-22

## Module

P0 / Module 5: Golden Question Evaluation

## What Was Verified

The first five golden questions now exist as a structured, machine-readable evaluation asset.

Files:

- `docs/rag-transformation/evals/golden-questions.md`
- `docs/rag-transformation/evals/golden-questions.json`
- `rag/eval_golden.py`
- `rag/tests/test_eval_golden.py`

## Focused Tests

Command:

```bash
python3 -m unittest rag.tests.test_eval_golden -v
```

Result:

```text
Ran 3 tests in 0.001s

OK
```

## P0 Focused Suite

Command:

```bash
python3 -m unittest rag.tests.test_eval_golden rag.tests.test_chat_service rag.tests.test_citations rag.tests.test_ingest rag.tests.test_graphrag_builder rag.tests.test_sync_corpus -v
```

Result:

```text
Ran 31 tests in 0.225s

OK
```

## Validation Command

Command:

```bash
python3 -m rag.eval_golden
```

Result:

```json
{
  "errors": [],
  "summary": {
    "total": 5,
    "answerability": {
      "insufficient": 0,
      "internal-only": 3,
      "needs-web": 2
    },
    "needs_conrad_review": 5,
    "current_status": {
      "dataset-ready-not-live-evaluated": 5
    }
  }
}
```

## Interpretation

The evaluation set is now structured enough for future benchmark runs. It is not yet a live quality score because the full runtime stack has not been evaluated against these questions.

## Conrad Review Needed

All five questions are marked `needs_conrad_review: true`.

Reason:

- Codex can propose evaluation labels and good/bad answer criteria.
- Conrad should confirm whether those criteria match the intended AIPM/product learning outcome.

## Residual Risk

The dataset currently validates structure and readiness. It does not yet run `/chat`, grade answers, or compare answer quality across versions.

## Reviewer Gate

Reviewer verdict: `Pass With Follow-ups`.

No P0 blocking issues were found.

P1 follow-ups before formal live benchmark:

- Deepen schema validation for nested fields.
- Separate P0 benchmark mode from future production web-search mode.
- Replace coarse `needs_conrad_review` boolean with a concrete Conrad review checklist.
