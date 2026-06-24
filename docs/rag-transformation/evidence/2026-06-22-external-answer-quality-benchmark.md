# Evidence: P1 External Evidence Answer Quality Benchmark

Date: 2026-06-22

## What Changed

Added a deterministic benchmark for answers that use external evidence.

This benchmark checks whether a needs-web answer:

- includes both internal and external citations when marked `internal_and_external_grounded`;
- labels internal evidence and external evidence in the answer;
- preserves required citation fields;
- records that external search was actually attempted;
- uses uncertainty language when weak external sources are present.

## Files Added

- `rag/eval_external_answer_quality.py`
- `rag/tests/test_eval_external_answer_quality.py`
- `docs/rag-transformation/plans/p1-external-answer-quality-benchmark.md`
- `docs/rag-transformation/evals/external-answer-quality-rubric-2026-06-22.json`

## Files Updated

- `package.json`
- `docs/rag-transformation/roadmap.md`

## Product Interpretation

This benchmark moves the project from "external search is wired" to "external evidence is governed."

It does not prove full factual correctness. It proves that the answer respects basic evidence boundaries:

- internal corpus is not confused with external search;
- weak or generic sources require caution;
- citation metadata stays visible for auditing.

## Validation

### TDD Red Check

Command:

```bash
python3 -m unittest rag.tests.test_eval_external_answer_quality -v
```

Initial result:

- Failed with `ModuleNotFoundError` because the evaluator did not exist yet.

### Focused Tests

Command:

```bash
python3 -m unittest rag.tests.test_eval_external_answer_quality -v
```

Final result:

- 4 tests passed.

### Benchmark Run

Command:

```bash
pnpm rag:eval:external-answer-quality
```

Result:

```json
{
  "total": 1,
  "passed": 1,
  "failed": 0,
  "failure_counts": {}
}
```

### Full Focused RAG Check

Command:

```bash
pnpm rag:check:p0
```

Result:

- 105 tests passed.
- Python compile check passed.

## Remaining Risk

- This is a deterministic rubric, not full factuality grading.
- It currently evaluates one live external-chat smoke artifact.
- It does not fetch full source pages.
- It does not compare multiple providers.
- It does not yet use an LLM-as-judge layer.
