# P1 Deep Fetch Integration Policy Plan

Date: 2026-06-22

## Goal

Connect URL deep-fetch capability to external evidence in a bounded, testable way.

## Product Meaning

Not every external citation should trigger page fetching.

Deep fetch should be used when it improves trust enough to justify latency and risk:

- official or academic sources should be inspected first because they carry high authority;
- weak/generic sources should be inspected when budget remains because they require verification;
- failures should be recorded, not hidden;
- the LLM prompt should show deep-fetch excerpts only when available.

## Scope

1. Add a deterministic deep-fetch selection policy.
2. Attach deep-fetch records to selected external citations.
3. Expose deep-fetch trace in `query_understanding`.
4. Include deep-fetch excerpts in the evidence prompt.
5. Keep live fetch optional through dependency injection.

## Out of Scope

- Enabling live URL fetch by default in the server.
- Browser rendering.
- Multi-page crawling.
- Source conflict resolution.

## Definition Of Done

Product behavior:
- The chat path can use deep-fetch evidence when a bounded fetcher is provided.

Engineering behavior:
- A policy function selects at most a small number of external URLs.
- Deep-fetch success and failure are recorded.
- Prompt formatting includes deep-fetch evidence without replacing original provider snippets.

Evidence behavior:
- Evidence file records policy, tests, and limitations.

Evaluation behavior:
- Focused tests pass.
- `pnpm rag:check:p0` passes.
