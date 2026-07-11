# P0 Agent, Search, And Citation Remediation

Date: 2026-07-11

## Purpose

Restore the shared local Agent path to a truthful, deterministic baseline before Stage 2.4 runtime acceptance.

## What Changed

- Restored one explicit Agent invocation contract for LangGraph-compatible and direct-LLM agents.
- Restored task-aware external-search parameters and research-paper query wording.
- Reconnected external citation refinement after merge.
- Corrected cache scope and trace semantics so cached evidence is not presented as a new search.
- Repaired time-sensitive test fixtures without weakening the production freshness filter.

## Verification Result

- Baseline: 191 tests, 5 failures, 2 errors.
- Focused remediation tests: 22 passed.
- Canonical P0 check: 193 passed.
- Docker: not started or changed.
- Live LLM/search calls: not performed.

## Checkpoint Status

- Local branch: `codex/claude-audit-remediation`.
- Local isolated commit: created with `fix(rag): restore agent search citation contracts`.
- GitHub push: `Checkpoint Blocked`. The sandbox could not resolve `github.com`; the approved-network retry was rejected because the current Codex account had reached its usage limit.
- This remediation must not be described as remotely backed up until a later successful push.

## Status

P0 remediation slice: `Locally Verified`.

Stage 2.4 itself remains `Implemented, Not Yet Locally Runtime Verified`; a passing deterministic suite is necessary but does not demonstrate the dashboard Agent flow with real configured runtime dependencies.

## Next Bottleneck

Engineering/runtime acceptance: run the explicit local Stage 2.4 dashboard and `/chat` smoke only after reviewing the existing local runtime configuration and Docker isolation plan.
