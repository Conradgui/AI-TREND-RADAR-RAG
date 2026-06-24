# Execution Log: P1 External Evidence Merge Into Chat

Date: 2026-06-22

## Loop

1. Reviewed the module plan:
   - `docs/rag-transformation/plans/p1-external-evidence-merge-into-chat.md`
2. Verified current routing state:
   - provider strategy exists;
   - Tavily live adapter exists;
   - other providers remain planned or disabled.
3. Ran full focused RAG check before live smoke.
4. Ran live external chat smoke.
5. Found external search was attempted but no external citations reached the answer.
6. Diagnosed the failure as a chat-specific external query problem.
7. Added a concise external-search query builder in `rag/chat_service.py`.
8. Added regression coverage in `rag/tests/test_chat_service.py`.
9. Re-ran focused local tests.
10. Re-ran live external chat smoke.
11. Recorded evidence and updated roadmap.

## Key Design Decision

Do not reuse the internal retrieval query as the external search query.

Reason:

- Internal retrieval benefits from the full user question and expanded terms.
- External search APIs work better with short, entity-heavy, task-specific queries.

Current examples:

- `official_source_lookup`: entity + topic + `knowledge framework` + `user preference`
- `research_paper`: topic + `evolution` + `papers` + `survey`
- `github_repo`: GitHub/source terms + `AI` + `trending repositories`
- `recent_web`: entity/topic + `latest update`

## Verification

Focused local tests:

- `python3 -m unittest rag.tests.test_chat_service rag.tests.test_search_provider_adapters rag.tests.test_tool_routing -v`
- Result: 16 passed.

Focused RAG check:

- `pnpm rag:check:p0`
- Result: 101 passed.

Live smoke:

- `.venv/bin/python -m rag.eval_external_chat_smoke`
- Result: 12 total citations, 10 internal citations, 2 external citations.
- Answer policy: `internal_and_external_grounded`.

## Residual Risks

- External answer quality rubric is still missing.
- External source snippets are not full-page extracted content.
- Multi-provider fallback is not fully live because Brave/Exa/GitHub clients are not implemented.
- Live smoke consumes real API quota and should stay low-volume until benchmark policy is finalized.

## Next Recommended Loop

P1 External Evidence Answer Quality Benchmark.

Goal:

- Evaluate whether final answers correctly separate internal vs external evidence;
- check that unsupported claims are still constrained;
- make Q2/Q5 quality measurable instead of anecdotal.
