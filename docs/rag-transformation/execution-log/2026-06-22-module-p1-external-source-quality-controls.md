# Execution Log: P1 External Source Quality Controls and Excerpt Policy

Date: 2026-06-22

## Loop

1. Reviewed fixed 600-character excerpt cap risk.
2. Created module plan:
   - `docs/rag-transformation/plans/p1-external-source-quality-controls.md`
3. Added failing tests:
   - `rag/tests/test_external_source_quality.py`
   - updates to `rag/tests/test_search_provider_adapters.py`
4. Implemented source quality module:
   - `rag/external_source_quality.py`
5. Integrated source-aware excerpt policy into Tavily adapter.
6. Added Tavily official-source request builder with include/exclude domains.
7. Updated live smoke to use official-domain routing for Google/OKF queries.
8. Ran full focused RAG check.
9. Ran Tavily live smoke.
10. Saved evidence and roadmap update.

## Key Decision

Do not keep fixed 600-character truncation as the final policy.

Use source-aware excerpt limits:

- preserve more context for official, academic, and developer sources;
- keep social/noisy sources shorter;
- mark social/generic results as needing deeper fetch or replacement before strong claims.

## Verification

- Source quality tests: passed.
- Full focused RAG check: 100 passed.
- Tavily live smoke: returned one `cloud.google.com` official citation, 1 credit used.

## Next Recommended Loop

P1 External Evidence Merge Into Chat.

The system can now retrieve a live official external citation, but final `/chat` answers still only use internal corpus citations.

Next step:

- for needs-web questions, call Tavily through the routing/adapter layer;
- merge internal and external citations with clear labels;
- update answer policy to say external evidence was actually used;
- add benchmark checks for Q2 and Q5.
