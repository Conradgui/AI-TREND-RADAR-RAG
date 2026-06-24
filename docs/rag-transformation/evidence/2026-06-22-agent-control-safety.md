# Evidence: P1 Agent Control and Safety

Date: 2026-06-22

## What Changed

Added a deterministic answer-policy layer for RAG chat responses.

The product purpose is to make every answer expose its evidence boundary:

- `internal_grounded`: the answer is based on AI Trend Radar internal corpus and returned citations.
- `needs_external_evidence`: the answer has internal evidence but still requires external sources before being treated as complete.
- `evidence_insufficient`: no usable internal citations were found, so the LLM should not be asked to invent an answer.

## Files Added

- `rag/answer_policy.py`
- `rag/eval_answer_policy.py`
- `rag/tests/test_answer_policy.py`
- `rag/tests/test_eval_answer_policy.py`
- `docs/rag-transformation/plans/p1-agent-control-safety.md`
- `docs/rag-transformation/evals/live-chat-rubric-2026-06-22.json`

## Files Updated

- `rag/chat_service.py`
- `rag/tests/test_chat_service.py`
- `package.json`
- `docs/rag-transformation/roadmap.md`

## Validation

### TDD Red Check

Command:

```bash
python3 -m unittest rag.tests.test_answer_policy rag.tests.test_chat_service rag.tests.test_eval_answer_policy -v
```

Initial expected result:

- Failed because `rag.answer_policy` and `rag.eval_answer_policy` did not exist.
- Failed because chat prompts did not yet include answer-policy instructions.

### Focused Unit Tests

Command:

```bash
python3 -m unittest rag.tests.test_answer_policy rag.tests.test_chat_service rag.tests.test_eval_answer_policy -v
```

Result:

- 11 tests passed.

### Full Focused RAG Check

Command:

```bash
pnpm rag:check:p0
```

Result:

- 66 tests passed.
- Python compile check passed.

### Live Benchmark

Command:

```bash
.venv/bin/python -m rag.eval_live_chat
```

Result:

```json
{
  "total": 5,
  "with_citations": 5,
  "without_citations": 0,
  "needs_web_questions": 2
}
```

### Answer-Policy Rubric

Command:

```bash
python3 -m rag.eval_answer_policy
```

Result:

```json
{
  "total": 5,
  "passed": 5,
  "failed": 0
}
```

## Snapshot Sanity Check

The latest live snapshot now starts answers with deterministic evidence-boundary disclosures:

- Q1: internal-only, 8 citations, internal corpus disclosure.
- Q2: needs-web, 10 citations, external evidence required disclosure.
- Q3: internal-only, 8 citations, internal corpus disclosure.
- Q4: internal-only, 8 citations, internal corpus disclosure.
- Q5: needs-web, 10 citations, external evidence required disclosure.

## Product Interpretation

This module does not make the agent more powerful. It makes the agent more accountable.

That is the correct order for this project: before adding web search and function calling, the system must first label whether an answer came from internal corpus only or whether it still needs external validation.

## Remaining Risk

- The rubric is rule-based. It verifies evidence-boundary discipline, not semantic answer quality.
- Real web search is still not implemented.
- Neo4j/Graph RAG runtime remains blocked locally because Docker/Neo4j is unavailable.
