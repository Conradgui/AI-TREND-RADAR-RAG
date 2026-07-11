# P0 Agent, Search, And Citation Remediation Plan

Date: 2026-07-11

## Why This Exists

The preserved Claude snapshot has a shared Stage 2.4 Agent-path regression: 191 deterministic P0 tests produce 5 failures and 2 errors. This plan is limited to restoring truthful Agent invocation, external-search, and citation/trace contracts. It does not advance Stage 2.5, 2.6, or 2.7.

## Architecture Boundary

- Layers: Agent, Evidence, Runtime.
- Inputs: grounded prompt messages, deterministic query plans, provider routing results, provider citations, and optional cached search results.
- Outputs: an Agent answer, citations actually used by that answer, and a tool trace that distinguishes a current execution from cached evidence reuse.
- No new framework, provider, secret, or user-facing product scope is introduced.

## Definition Of Done

Product behavior:

- The local Agent returns a grounded answer when internal evidence is available.
- Needs-web answers show external citations only when they are actually used, and disclose whether they were searched now or reused from the short-lived cache.

Engineering behavior:

- Direct-LLM and LangGraph-compatible agents share `ainvoke(payload, config=None)`.
- Tavily request parameters respect task type: recent-news searches use freshness constraints; paper and official-source lookups do not.
- Citation refinement remains active after external evidence is merged.

Evaluation behavior:

- Focused chat-service and provider-adapter tests cover all three contracts.
- The canonical `pnpm rag:check:p0` passes without changing production policies merely to accommodate stale fixtures.

Non-goals:

- No live provider call, dashboard smoke, Docker start, or Stage 2.5+ feature work.

Residual risks:

- Passing deterministic checks cannot validate live API credentials, provider availability, or semantic answer quality; those require a later explicit local-runtime gate.

## Execution Sequence

1. Restore the contract and add regression coverage.
2. Run focused tests for Agent/chat and provider request behavior.
3. Run the canonical P0 check and review its diff.
4. Write evidence and execution log, then make one isolated `fix(rag)` checkpoint.
