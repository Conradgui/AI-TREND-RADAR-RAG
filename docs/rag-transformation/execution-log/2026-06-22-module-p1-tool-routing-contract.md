# Execution Log: P1 Tool Routing Contract

Date: 2026-06-22

## Loop

1. Created module plan:
   - `docs/rag-transformation/plans/p1-tool-routing-contract.md`
2. Added failing tests for deterministic tool routing:
   - `rag/tests/test_tool_routing.py`
   - `rag/tests/test_chat_service.py`
3. Implemented route planning:
   - `rag/tool_routing.py`
4. Attached routing trace to chat responses:
   - `query_understanding.tool_routing`
5. Added routing rubric:
   - `rag/eval_tool_routing.py`
   - `rag/tests/test_eval_tool_routing.py`
6. Added package scripts:
   - `rag:eval:tool-routing`
   - updated `rag:test:p0`
   - updated `rag:check:p0`
7. Regenerated live chat snapshot.
8. Ran routing rubric and saved output.
9. Updated roadmap and evidence.

## Key Decision

External web tools are planned but unavailable in this module.

This is deliberate. The agent should not claim external research until real web-search and URL-fetch tools exist, return external citations, and pass their own benchmarks.

## Verification

- Module tests: 11 passed.
- Full focused RAG check: 73 passed.
- Live chat benchmark: 5/5 questions returned citations.
- Tool-routing rubric: 5/5 passed.

## Blockers

- Neo4j runtime verification remains blocked because local Docker/Neo4j is unavailable.
- Real web search requires a future decision on tool/provider and external citation policy.

## Next Recommended Loop

P1 External Search Tool Stub and Citation Schema.

The next module should add a non-network external evidence schema and a disabled tool adapter first:

- external citation fields;
- web-search unavailable error shape;
- `needs-web` fallback tests;
- then, only after the contract is stable, implement real web search.
