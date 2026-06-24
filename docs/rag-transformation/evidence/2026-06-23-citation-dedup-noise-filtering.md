# Evidence: P1 Citation Deduplication and Noise Filtering

Date: 2026-06-23

## Scope

Implemented the first deterministic fix for retrieval precision issues found in `retrieval-precision-matrix-2026-06-23.json`.

Changes:

- deduplicate repeated topic/project citations by semantic key: title, source, URL;
- after external evidence exists for a needs-web query, remove obvious distracting internal citations and keep only a small amount of focused internal context.
- for official-source lookup, continue to fallback providers when the first provider returns only generic citations.

## Files Added Or Updated

- `rag/citations.py`
- `rag/chat_service.py`
- `rag/tests/test_citations.py`
- `rag/tests/test_chat_service.py`
- `docs/rag-transformation/plans/p1-citation-dedup-noise-filtering.md`

## RED Verification

Before implementation, focused tests failed as expected:

```text
test_build_citations_deduplicates_repeated_topic_title_source_and_url ... FAIL
AssertionError: 2 != 1
```

```text
test_build_chat_response_demotes_internal_noise_when_external_evidence_exists ... FAIL
AssertionError: GLM citation unexpectedly present
```

## GREEN Verification

After implementation:

```text
python3 -m unittest rag.tests.test_citations.CitationTests.test_build_citations_deduplicates_repeated_topic_title_source_and_url -v
OK
```

```text
python3 -m unittest rag.tests.test_chat_service.ChatServiceTests.test_build_chat_response_demotes_internal_noise_when_external_evidence_exists -v
OK
```

Related focused suite:

```text
python3 -m unittest rag.tests.test_citations rag.tests.test_chat_service -v
Ran 15 tests in 0.122s
OK
```

Official-source fallback focused test:

```text
python3 -m unittest rag.tests.test_chat_service.ChatServiceTests.test_official_source_lookup_continues_until_official_citation -v
OK
```

Canonical check:

```text
pnpm rag:check:p0
Ran 143 tests in 0.072s
OK
```

## Live Verification

After Docker Desktop was started, generated an after-filter hybrid live snapshot:

```bash
.venv/bin/python -m rag.eval_hybrid_live_chat --output docs/rag-transformation/evals/hybrid-live-chat-snapshot-2026-06-23-after-filter.json
```

Result:

```json
{
  "total": 5,
  "with_citations": 5,
  "with_graph_citations": 4,
  "with_external_citations": 2,
  "needs_web_questions": 2
}
```

Retrieval precision after filtering:

```json
{
  "total": 3,
  "passed": 3,
  "failed": 0,
  "citation_count": 13,
  "distracting_count": 0,
  "failure_counts": {}
}
```

Before filtering, the same benchmark was:

```json
{
  "total": 3,
  "passed": 0,
  "failed": 3,
  "citation_count": 32,
  "distracting_count": 3
}
```

Provider quality after filtering:

```json
{
  "total": 5,
  "passed": 5,
  "failed": 0,
  "with_graph_citations": 4,
  "with_external_citations": 2
}
```

Claim-level after filtering:

```json
{
  "total": 8,
  "passed": 7,
  "failed": 1,
  "failure_counts": {
    "missing_required_source_quality": 1
  }
}
```

The remaining claim-level failure is Q5 official-source quality. A deterministic fallback fix was added so official-source lookup continues past generic Tavily results to a fallback provider when needed.

## Official-Source Fallback Live Verification

After usage restored, reran the hybrid live snapshot.

Q5 external search trace now shows Tavily first and Brave fallback second:

```json
{
  "provider": "brave",
  "attempts": [
    {"provider": "tavily", "available": true, "citation_count": 2},
    {"provider": "brave", "available": true, "citation_count": 2}
  ]
}
```

Q5 external citations now include official Google Cloud evidence:

```json
{
  "provider": "brave",
  "source": "cloud.google.com",
  "source_quality": "official",
  "quality_score": 0.95
}
```

Final after-filter matrices:

```json
{
  "retrieval_precision": {"total": 3, "passed": 3, "failed": 0},
  "provider_quality": {"total": 5, "passed": 5, "failed": 0},
  "claim_level": {"total": 8, "passed": 8, "failed": 0}
}
```

Canonical check:

```text
pnpm rag:check:p0
Ran 143 tests in 0.111s
OK
```

Interpretation:

- citation deduplication and needs-web noise filtering are live-smoke verified;
- official-source fallback is live-smoke verified;
- claim-level, provider-quality, and retrieval-precision gates pass on the after-filter snapshot.

## Residual Risks

- The filter is intentionally conservative and deterministic.
- Semantic reranking may still be needed later for deeper relevance control.
- Graph RAG is still mostly citation-producing; deeper multi-hop graph reasoning is not yet benchmarked.
