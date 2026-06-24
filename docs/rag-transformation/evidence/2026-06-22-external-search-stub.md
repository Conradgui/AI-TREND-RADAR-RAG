# Evidence: P1 External Search Tool Stub and Citation Schema

Date: 2026-06-22

## What Changed

Added the external evidence contract needed before real web search is implemented.

This module does not perform live web search. It defines:

- the required external citation fields;
- schema validation for external evidence;
- a stable disabled `web_search` result shape;
- a readiness check that verifies the contract.

## Files Added

- `rag/external_evidence.py`
- `rag/eval_external_evidence.py`
- `rag/tests/test_external_evidence.py`
- `rag/tests/test_eval_external_evidence.py`
- `docs/rag-transformation/plans/p1-external-search-stub.md`
- `docs/rag-transformation/evals/external-evidence-readiness-2026-06-22.json`

## Files Updated

- `package.json`
- `docs/rag-transformation/roadmap.md`

## External Citation Contract

Required fields:

- `evidence_type`
- `source`
- `title`
- `url`
- `retrieved_at`
- `excerpt`

Optional fields for future implementation:

- `published_at`
- `author`
- `source_type`

## Validation

### TDD Red Check

Command:

```bash
python3 -m unittest rag.tests.test_external_evidence -v
```

Initial expected result:

- Failed because `rag.external_evidence` did not exist.

### Focused Module Tests

Command:

```bash
python3 -m unittest rag.tests.test_external_evidence rag.tests.test_eval_external_evidence -v
```

Result:

- 5 tests passed.

### Full Focused RAG Check

Command:

```bash
pnpm rag:check:p0
```

Result:

- 78 tests passed.
- Python compile check passed.

### External Evidence Readiness

Command:

```bash
python3 -m rag.eval_external_evidence
```

Result:

```json
{
  "output": "docs/rag-transformation/evals/external-evidence-readiness-2026-06-22.json",
  "passed": true
}
```

## Product Interpretation

This is a quality gate for future Function Calling.

The project is now prepared to accept external evidence later, but it still refuses to imply that external search has already happened.

## Remaining Risk

- Real web search is still not implemented.
- External source ranking, deduplication, and primary-source preference are not implemented.
- Fetching URLs and extracting external content are not implemented.
