# Evidence: P1 Graph Question Planner

Date: 2026-06-24

## Scope

Added a deterministic graph question planner and service-layer graph evidence retrieval.

The module detects relationship-style questions and routes them to graph evidence over:

- Entity -> Topic
- Topic -> DailyDigest date
- Topic -> Source

## Files Added Or Updated

- `rag/graph_question_planning.py`
- `rag/graph_reasoning_service.py`
- `rag/eval_graph_question_planner_live.py`
- `rag/tests/test_graph_question_planning.py`
- `rag/tests/test_graph_reasoning_service.py`
- `docs/rag-transformation/evals/graph-question-planner-live-2026-06-24.json`
- `docs/rag-transformation/plans/p1-graph-question-planner.md`
- `package.json`

## Focused Verification

Command:

```bash
python3 -m unittest rag.tests.test_graph_question_planning rag.tests.test_graph_reasoning_service -v
```

Result:

```text
Ran 6 tests in 0.024s
OK
```

## Canonical Verification

Command:

```bash
pnpm rag:check:p0
```

Result:

```text
Ran 152 tests in 0.199s
OK
```

## Live Graph Planner Smoke

Command:

```bash
.venv/bin/python -m rag.eval_graph_question_planner_live --output docs/rag-transformation/evals/graph-question-planner-live-2026-06-24.json
```

Result:

```json
{
  "passed": true,
  "failed_checks": []
}
```

Observed graph evidence:

- Question: `RAG 相关主题是否跨多个日期和来源反复出现？`
- Entity: `rag`
- Topics: 18
- Dates: 14
- Sources: 4

## Interpretation

The service layer can now produce graph-derived relationship evidence for a seeded graph question.

This is a meaningful Graph RAG step because the system can separate graph relationship evidence from ordinary text snippets.

## Residual Risks

- Planner coverage is narrow and deterministic; it does not parse arbitrary graph questions.
- Entity normalization is still shallow and should be expanded later.
- Chat UI does not yet expose a dedicated graph reasoning mode.
- This verifies structural graph evidence, not final semantic answer correctness.
