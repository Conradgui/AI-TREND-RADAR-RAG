# Execution Log: P1 Citation Deduplication and Noise Filtering

Date: 2026-06-23

## Loop

### 1. Orient

Previous retrieval precision benchmark exposed repeated citations in Q1/Q2 and weak or distracting internal citations in Q5.

### 2. Explain

The fix should happen close to citation assembly and final chat citation preparation:

- repeated citations are created during citation assembly;
- needs-web internal noise can only be safely compressed after external evidence is available.

### 3. Define Done

Done criteria:

- focused RED tests fail before implementation;
- dedup/filter implementation passes focused tests;
- canonical RAG check passes;
- live hybrid verification is attempted and honestly recorded.

### 4. Implement

Implemented:

- semantic citation deduplication in `rag/citations.py`;
- needs-web internal noise filtering in `rag/chat_service.py`;
- official-source fallback continuation in `rag/chat_service.py`;
- focused tests in `rag/tests/test_citations.py` and `rag/tests/test_chat_service.py`.

### 5. Verify

Focused tests:

```text
python3 -m unittest rag.tests.test_citations rag.tests.test_chat_service -v
Ran 15 tests in 0.122s
OK
```

Official-source fallback:

```text
python3 -m unittest rag.tests.test_chat_service.ChatServiceTests.test_official_source_lookup_continues_until_official_citation -v
OK
```

Canonical:

```text
pnpm rag:check:p0
Ran 143 tests in 0.072s
OK
```

Live hybrid verification after dedup/noise filtering:

```json
{
  "with_citations": 5,
  "with_graph_citations": 4,
  "with_external_citations": 2
}
```

Retrieval precision after filtering:

```json
{
  "total": 3,
  "passed": 3,
  "failed": 0,
  "citation_count": 13,
  "distracting_count": 0
}
```

Claim/provider checks after filtering:

```text
provider-quality: 5/5 passed
claim-level: 7/8 passed; remaining issue is missing official source quality for Q5
```

Official-source fallback live rerun:

```json
{
  "provider": "brave",
  "attempts": ["tavily", "brave"],
  "official_source": "cloud.google.com"
}
```

Final matrices:

```text
retrieval precision: 3/3 passed
provider quality: 5/5 passed
claim level: 8/8 passed
canonical check: 143 tests passed
```

### 6. Review

The implementation is intentionally small:

- no index rebuild;
- no LangChain/LangGraph dependency;
- no new external service;
- no heavy semantic reranker.

### 7. Record Evidence

Evidence file:

- `docs/rag-transformation/evidence/2026-06-23-citation-dedup-noise-filtering.md`

### 8. Decide Next

Immediate next step:

- move to P1 Multi-Hop Graph Reasoning Seed.

Reason:

- current retrieval/citation quality gates are green;
- Graph RAG is still not proven to perform multi-hop reasoning over graph structure.
