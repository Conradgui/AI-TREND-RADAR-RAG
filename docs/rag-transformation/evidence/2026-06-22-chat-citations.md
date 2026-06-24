# Evidence: Chat Citations

## Date

2026-06-22

## Module

P0 / Module 4: Chat Citations

## What Was Verified

The chat citation path now has:

- Pure citation extraction from retrieval metadata.
- Conservative evidence-insufficient answer behavior.
- Mocked chat response smoke coverage without real FastAPI, Neo4j, ChromaDB, or LLM services.
- Server wiring that retrieves citations before returning `/chat`.
- Syntax-level validation for the modified server file.

## Focused Tests

Command:

```bash
python3 -m unittest rag.tests.test_chat_service rag.tests.test_citations rag.tests.test_ingest rag.tests.test_graphrag_builder rag.tests.test_sync_corpus -v
```

Result:

```text
Ran 28 tests in 0.023s

OK
```

## Syntax Check

Command:

```bash
PYTHONPYCACHEPREFIX=/tmp/ai_trend_rag_pycache python3 -m py_compile rag/citations.py rag/chat_service.py rag/server.py
```

Result:

```text
OK
```

## Representative Citation Sample

Command:

```bash
python3 - <<'PY'
from dataclasses import dataclass
from rag.citations import build_citations

@dataclass
class Chunk:
    text: str
    metadata: dict

chunks = [Chunk(
    text='Claude Code Artifacts\nPreview and share your coding work live as it happens',
    metadata={
        'content_type': 'topic_candidate',
        'date': '2026-06-21',
        'source': 'Product Hunt',
        'title': 'Claude Code Artifacts',
        'url': 'https://www.producthunt.com/r/ZKUSXUIDPQQBDF',
        'score': 80,
        'category': 'AI 产品与用户入口',
        'citation_id': '2026-06-21/topic-pool/0',
        'evidence': '来源：Product Hunt\n热度信号：451 / 14\n发布时间：2026-06-19',
    }
)]
print(build_citations(chunks)[0])
PY
```

Result:

```text
{
  'date': '2026-06-21',
  'source': 'Product Hunt',
  'title': 'Claude Code Artifacts',
  'citation_id': '2026-06-21/topic-pool/0',
  'excerpt': '来源：Product Hunt\n热度信号：451 / 14\n发布时间：2026-06-19',
  'url': 'https://www.producthunt.com/r/ZKUSXUIDPQQBDF',
  'score': 80,
  'category': 'AI 产品与用户入口'
}
```

## Interpretation

`/chat` can now return citations derived from retrieval metadata instead of fabricated LLM text. When no usable citation evidence is available, the system returns an evidence-insufficient answer.

The core `/chat` orchestration is covered through `rag.chat_service.build_chat_response()` with mocked agent and retriever objects. This avoids needing live FastAPI, Neo4j, ChromaDB, or LLM dependencies for the P0 smoke test.

## Residual Risk

This module has not yet completed a full live `/chat` end-to-end run with FastAPI, Neo4j, ChromaDB, and an LLM provider all available. That requires the full runtime stack and secrets/configuration. The current verification covers citation extraction, mocked chat wiring, server wiring syntax, and representative metadata behavior.

Retriever failures currently become empty citations, which surface as evidence-insufficient answers. This is conservative but may later need a distinct retrieval-error response.

## Reviewer Gate

Initial reviewer verdict: `Pass With Follow-ups`.

Follow-up requested:

- Add mocked `/chat` smoke coverage for citation and evidence-insufficient branches.

Fix applied:

- Added `rag/chat_service.py`.
- Added `rag/tests/test_chat_service.py`.
- `rag/server.py` now acts as a thin wrapper around `build_chat_response()`.

Final reviewer verdict: `Pass`.

Reviewer note:

- This is not a FastAPI `TestClient` endpoint test, but it is sufficient for P0 because the server wrapper is thin and the chat orchestration is now covered without live runtime dependencies.
