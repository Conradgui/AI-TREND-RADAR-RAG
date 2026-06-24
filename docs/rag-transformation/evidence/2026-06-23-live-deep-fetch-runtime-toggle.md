# Evidence: P1 Live Deep Fetch Runtime Toggle

Date: 2026-06-23

## What Changed

- Added explicit `RAG_ENABLE_DEEP_FETCH` runtime flag.
- Added `is_deep_fetch_enabled()` in `rag/config.py`.
- Added `select_external_deep_fetcher()` in `rag/runtime_tools.py`.
- Wired `rag/server.py` so the live `fetch_url` function is passed to chat only when deep fetch is explicitly enabled.
- Added `deep_fetch_enabled` to `/health`.
- Added `rag/eval_deep_fetch_live.py` for chat-level live smoke.
- Added `rag/eval_deep_fetch_url_live.py` for URL-level live smoke.
- Added regression tests for the deep-fetch runtime selector.
- Updated URL fetch safety to allow public hostnames resolved through managed proxy addresses while still rejecting direct proxy/private/local IP targets.

## Validation

Focused tests:

```text
python3 -m unittest rag.tests.test_url_fetch rag.tests.test_deep_fetch_policy rag.tests.test_server_deep_fetch_toggle -v
Ran 11 tests
OK
```

Canonical check:

```text
pnpm rag:check:p0
Ran 118 tests
OK
```

Live URL deep-fetch smoke:

```text
.venv/bin/python -m rag.eval_deep_fetch_url_live
attempted: true
selected_count: 1
success_count: 1
failure_count: 0
status_code: 200
content_type: text/html; charset=utf-8
title: How the Open Knowledge Format can improve data sharing | Google Cloud Blog
text_excerpt_length: 3000
```

Output:

- `docs/rag-transformation/evals/deep-fetch-url-live-smoke-2026-06-23.json`

## Search Discovery Smoke Result

Initial chat-level smoke with the OKF/ALM question ran before Brave live adapter support and did not discover external citations:

```text
external_search_attempted: true
external_citation_count: 0
deep_fetch_attempted: false
reason: no_external_citations
```

Output:

- `docs/rag-transformation/evals/deep-fetch-live-smoke-2026-06-23.json`

This is not recorded as an end-to-end deep-fetch success. It shows provider discovery volatility and supports the next module: implement additional live search provider adapters.

After Brave live adapter support was added, the same smoke improved:

```text
external_search_attempted: true
provider: brave
external_citation_count: 2
answer_policy_mode: internal_and_external_grounded
deep_fetch_attempted: true
deep_fetch_selected_count: 2
deep_fetch_success_count: 1
deep_fetch_failure_count: 1
```

The current end-to-end status is therefore:

- provider fallback plus external citation merge: `Live Smoke Verified`;
- deep fetch execution from chat-level external citations: `Live Smoke Verified`;
- perfect URL fetch success for every selected source: `Not Claimed`.

## Product Interpretation

This module proves the runtime safety/control layer:

- deep fetch is default-off;
- the server can explicitly enable it;
- the URL fetcher can inspect a real official page;
- traces are recorded for success and failure.

It does not prove that a single provider can always find the right official source.

## Residual Risks

- Search discovery still depends primarily on Tavily; it returned zero citations for the OKF/ALM query during this run.
- Brave, Exa, and GitHub are configured as providers but do not yet have live adapter implementations.
- Redirect-chain target validation remains a future hardening item.
- Full browser-rendered pages are not supported by the lightweight fetcher.
