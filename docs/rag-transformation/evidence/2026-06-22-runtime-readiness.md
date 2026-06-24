# Evidence: P1 Runtime Readiness

## Date

2026-06-22

## Module

P1: Runtime Readiness / Live Local Retrieval Smoke

## What Changed

Runtime setup:

- Created project-local `.env` for DeepSeek runtime configuration.
- Created project-local `.venv` with bundled Python 3.12.13.
- Installed `rag/requirements.txt` into `.venv`.
- Downloaded Chroma's default local embedding model.

Code changes:

- Added vector-only ingestion path: `python -m rag.ingest --vector-only`.
- Added `source_family` normalization for topic candidates.
- Fixed Chroma metadata filters:
  - date windows now use string `$in` lists instead of unsupported string `$gte/$lte`.
  - GitHub source filtering now uses `source_family=GitHub`.
- Added DeepSeek base URL configuration via `DEEPSEEK_BASE_URL`.
- Added vector-only chat fallback for when Neo4j is unavailable.
- Added retrieval evidence context to chat generation.

## Configuration

Provider:

- `LLM_PROVIDER=deepseek`
- `DEEPSEEK_MODEL=deepseek-v4-flash`
- `DEEPSEEK_BASE_URL=https://api.deepseek.com`

Secret handling:

- The test API key is stored only in local `.env`.
- The key is not copied into this evidence file.
- `.env` is ignored by git.

## Runtime Checks

### Dependency Import Check

Command:

```bash
.venv/bin/python - <<'PY'
import fastapi
import chromadb
import neo4j
import langchain
import langchain_openai
import langchain_anthropic
import langgraph
import dotenv
from langgraph.prebuilt import create_react_agent
print('runtime imports: ok')
PY
```

Result:

```text
runtime imports: ok
```

### DeepSeek Smoke

Command:

```bash
.venv/bin/python - <<'PY'
from langchain_openai import ChatOpenAI
from rag.config import DEEPSEEK_API_KEY, DEEPSEEK_BASE_URL, DEEPSEEK_MODEL
llm = ChatOpenAI(model=DEEPSEEK_MODEL, api_key=DEEPSEEK_API_KEY, base_url=DEEPSEEK_BASE_URL, temperature=0)
resp = llm.invoke('只回复 OK')
print('deepseek_smoke:', resp.content[:80])
PY
```

Result:

```text
deepseek_smoke: OK
```

### Vector-Only Ingestion

Command:

```bash
.venv/bin/python -m rag.ingest --vector-only
```

Result:

```text
[ingest:vector] ChromaDB total: 1346 chunks
[ingest:vector] Done. Ingested 1346 chunks.
```

### Real Vector Retrieval Smoke

Questions checked:

- 最近 RAG 领域有什么值得关注的新动向？
- Claude 最近有没有上线什么新功能？
- 过去一周 GitHub 热榜上有什么值得关注的选题？

Result:

- ChromaDB chunks: 1346
- Q1: 5 hits, 5 citations
- Q3: 5 hits, 5 citations
- Q4: 5 hits, 5 citations after `source_family` fix

Q4 example citations:

- `2026-06-20 / GitHub Search:rag / langchain-ai/langchain`
- `2026-06-19 / GitHub Search:ai-agent / ZhuLinsen/daily_stock_analysis`
- `2026-06-20 / GitHub Search:ai-agent / ZhuLinsen/daily_stock_analysis`

### FastAPI Health

Command:

```bash
curl -s http://127.0.0.1:8001/health
```

Result:

```json
{
  "status": "ok",
  "configured": true,
  "neo4j_connected": false,
  "chromadb_chunks": 1346,
  "provider": "deepseek",
  "retriever_mode": "vector-only"
}
```

### FastAPI Chat

Command:

```bash
curl -s -X POST http://127.0.0.1:8001/chat \
  -H 'Content-Type: application/json' \
  -d '{"message":"过去一周 GitHub 热榜上有什么值得关注的选题？","history":[]}'
```

Result:

- HTTP 200
- Returned grounded answer.
- Returned citations.
- Returned query understanding.
- Ran in `vector-only` mode because Neo4j was unavailable.

## Verification

Focused command:

```bash
.venv/bin/python -m unittest rag.tests.test_chat_service rag.tests.test_hybrid_retriever rag.tests.test_retrieval_planning -v
```

Result:

```text
Ran 10 tests

OK
```

Canonical command:

```bash
pnpm rag:check:p0
```

Result:

```text
Ran 56 tests

OK
```

## Runtime Bugs Found And Fixed

### Chroma Date Filter Bug

Problem:

- Chroma rejected `{"date": {"$gte": "2026-06-15", "$lte": "2026-06-21"}}`.

Root cause:

- Chroma requires each operator expression to have one operator.
- Chroma also requires `$gte/$lte` operands to be numeric, not date strings.

Fix:

- Convert last-seven-days windows into exact string date lists:
  - `{"date": {"$in": ["2026-06-15", ..., "2026-06-21"]}}`

### GitHub Source Filter Bug

Problem:

- Q4 returned 0 hits after source/date filtering.

Root cause:

- Actual source metadata used values like `GitHub Search:rag`, not plain `GitHub Search`.

Fix:

- Add `source_family=GitHub` during ingestion.
- Filter GitHub questions by `source_family`.

## Blockers

### Neo4j

Current blocker:

- `docker` command is not available in the current shell.
- Neo4j is not running on `localhost:7687`.

Impact:

- Full Graph RAG and LangGraph tool-agent mode are not yet live.
- The system currently runs through vector-only chat fallback.

Non-blocking because:

- Chroma vector retrieval, citations, DeepSeek generation, and `/chat` are now live and verified.

## Next Recommended Module

P1 Live Answer Quality Benchmark:

- Run all five golden questions through `/chat`.
- Store answer/citation/query-understanding snapshots.
- Grade each result manually or with a rubric.
- Identify where vector-only mode is enough and where Graph RAG or web search is required.
