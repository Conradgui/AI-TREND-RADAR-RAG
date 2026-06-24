# Evidence: P1 External Evidence Merge Into Chat

Date: 2026-06-22

## What Changed

Needs-web chat answers can now use live external Tavily evidence when a configured search provider is available.

The chat path now separates:

- internal AI Trend Radar corpus citations;
- external web citations;
- answer-policy mode after external evidence is actually retrieved.

## Product Behavior

Before this module, needs-web answers could only say that external evidence was required.

After this module, a Q5-style question can:

- search internal corpus first;
- call Tavily through the provider registry;
- merge Tavily citations into the evidence prompt;
- mark the answer as `internal_and_external_grounded` when external citations exist.

## Files Updated

- `rag/chat_service.py`
- `rag/server.py`
- `rag/tests/test_chat_service.py`
- `rag/eval_external_chat_smoke.py`
- `package.json`
- `docs/rag-transformation/evals/external-chat-smoke-2026-06-22.json`
- `docs/rag-transformation/roadmap.md`

## Important Fix During Gate

The first live smoke attempted external search but returned zero external citations.

Observed result:

```json
{
  "citation_count": 10,
  "internal_citation_count": 10,
  "external_citation_count": 0,
  "answer_policy_mode": "needs_external_evidence",
  "external_search_attempted": true
}
```

Root cause:

- The chat integration sent the full Chinese user question plus internal retrieval terms to Tavily.
- That query was too long and mixed several sub-questions.
- Tavily itself was available, but the chat-specific request returned a network-level failure.

Fix:

- Added a concise external-search query builder.
- Internal RAG can still use the richer retrieval query.
- External web search now receives shorter task-specific terms such as `Google OKF ALM Wiki knowledge framework user preference`.

## Validation

### Focused Unit/Contract Tests

Command:

```bash
python3 -m unittest rag.tests.test_chat_service rag.tests.test_search_provider_adapters rag.tests.test_tool_routing -v
```

Result:

- 16 tests passed.

### Full Focused RAG Check

Command:

```bash
pnpm rag:check:p0
```

Result:

- 101 tests passed.
- Python compile check passed.

### Live External Chat Smoke

Command:

```bash
.venv/bin/python -m rag.eval_external_chat_smoke
```

Final result:

```json
{
  "citation_count": 12,
  "internal_citation_count": 10,
  "external_citation_count": 2,
  "answer_policy_mode": "internal_and_external_grounded",
  "external_search_attempted": true
}
```

External citation sanity check:

- Tavily returned 2 external citations.
- One was an official `cloud.google.com` source.
- One was a generic secondary source.
- The official source used the longer official-source excerpt policy.

## Product Interpretation

This is the first working version of hybrid evidence:

- internal corpus gives project-specific context;
- external search updates or verifies claims that the local corpus cannot fully support;
- the answer policy records whether external evidence actually arrived.

This is still not a production-quality web research agent. It is a working P1 slice.

## Remaining Risk

- Only Tavily has a live provider implementation.
- Brave, Exa, SerpAPI, and GitHub are routed but not yet implemented as live clients.
- URL fetch/extract is not implemented, so provider snippets are used directly.
- Source conflict resolution is prompt-level only.
- A single live smoke proves the pipe works, not that answer quality is consistently good.
