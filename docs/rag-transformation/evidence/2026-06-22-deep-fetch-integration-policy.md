# Evidence: P1 Deep Fetch Integration Policy

Date: 2026-06-22

## What Changed

Added a bounded deep-fetch policy and optional chat integration path.

The system can now:

- choose a small number of external citations for deep fetch;
- prioritize authoritative sources before weak sources;
- attach `deep_fetch` records to selected citations;
- expose a `deep_fetch` trace in `query_understanding`;
- include successful deep-fetch excerpts in the LLM evidence prompt;
- keep live URL fetching disabled unless a controlled fetcher is explicitly provided.

## Files Added

- `rag/deep_fetch_policy.py`
- `rag/tests/test_deep_fetch_policy.py`
- `docs/rag-transformation/plans/p1-deep-fetch-integration-policy.md`

## Files Updated

- `rag/chat_service.py`
- `rag/tests/test_chat_service.py`
- `package.json`
- `docs/rag-transformation/roadmap.md`

## Policy

Default maximum URLs:

- `2` external URLs per answer path.

Selection priority:

1. authoritative sources: `official`, `academic`, `developer`;
2. sources that require deeper verification: `generic`, `social`, `trusted_media`, or `needs_deep_fetch=true`;
3. remaining external URLs.

Default runtime behavior:

- chat does not perform live URL fetching unless `external_deep_fetcher` is provided;
- this keeps server behavior bounded until a runtime setting and live smoke are added.

## Product Interpretation

This module upgrades URL fetch from a standalone utility to an agent-ready evidence step.

It still preserves cost and latency control:

- search can run without deep fetch;
- deep fetch can be injected for benchmark or controlled runtime use;
- fetch failures are explicit instead of silently weakening the answer.

## Validation

### TDD Red Check

Command:

```bash
python3 -m unittest rag.tests.test_deep_fetch_policy -v
```

Initial result:

- Failed with `ModuleNotFoundError` because `rag.deep_fetch_policy` did not exist yet.

### Focused Tests

Command:

```bash
python3 -m unittest rag.tests.test_deep_fetch_policy rag.tests.test_chat_service -v
```

Result:

- 9 tests passed.

### Full Focused RAG Check

Command:

```bash
pnpm rag:check:p0
```

Result:

- 113 tests passed.
- Python compile check passed.

## Remaining Risk

- Live URL fetch is not enabled by default in the FastAPI server.
- No live deep-fetch smoke has been run.
- No source conflict resolution is implemented yet.
- Redirect-chain safety should be hardened before default live enabling.
