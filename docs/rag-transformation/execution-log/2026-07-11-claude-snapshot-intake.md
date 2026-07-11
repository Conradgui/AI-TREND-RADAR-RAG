# Claude Snapshot Intake And Audit Boundary

Date: 2026-07-11

## Purpose

This record separates the preserved Claude handoff snapshot from subsequent Codex audit and remediation work.

It is not a completion claim, release claim, or production-readiness claim.

## Preserved Source

- Source branch: `claude/rag-transformation-checkpoints`
- Preserved source commits:
  - `d772d49 feat: complete project review and open-source standards`
  - `f61c930 feat: complete project verifier 6-phase verification`
  - `7a47b1c fix: update test results after network recovery`
- Remediation branch: `codex/claude-audit-remediation`
- Branch relationship: the remediation branch starts from the preserved Claude snapshot. No commit has been merged into `main`.

## Intake Verification

The deterministic Python test suite was rerun against the preserved Claude snapshot:

- total: 191 tests;
- result: 5 failures and 2 errors;
- affected shared paths: Agent invocation, external-search routing and Tavily request configuration.

Therefore, the snapshot is classified as `Implemented, Not Locally Verified` for the changed shared RAG paths.

## Audit Rules

1. Do not treat generated reports, scores, pass rates, or benchmark claims as evidence until they can be reproduced from code and saved artifacts.
2. Do not continue Stage 2.5, Stage 2.6, or Stage 2.7 feature work until the Stage 2.4 Agent path has passed its focused and local-runtime gates.
3. Keep every remediation concern isolated:
   - `audit(rag):` for review evidence and correction of false claims;
   - `fix(rag):` for one production contract or regression at a time;
   - `checkpoint(rag):` only after a module or stage gate.
4. Each remediation commit must state the source snapshot, changed boundary, verification result, and residual risk in its associated execution log or evidence record.

## Next Gate

P0 is to restore a truthful, testable local Agent path:

1. define one `ainvoke` contract that works for both LangGraph and direct-LLM fallback agents;
2. verify external-search query and provider request contracts before changing test expectations;
3. verify citation output represents the evidence actually used by the answer;
4. add focused regression tests for each repaired contract;
5. rerun the canonical shared-RAG verification before declaring Stage 2.4 locally verified.

## Residual Risks

- The snapshot includes broad product, runtime, retrieval, UI, documentation and verification changes in a small number of commits.
- Existing completion and benchmark documents may contain unreproducible claims and must not be used as release or interview evidence before audit correction.
- Docker runtime isolation requires a separate review before any container is started.
