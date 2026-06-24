# Plan: Loop V2.1 GitHub Checkpoints

Date: 2026-06-24

## Goal

Upgrade the project operating loop so important nodes are backed up to GitHub and future development is controlled by architecture, maintainability, and anti-rabbit-hole gates.

## Scope

In scope:

- update execution-loop spec to V2.1;
- add decision record for checkpoint and maintainability governance;
- add evidence and execution log for the baseline checkpoint;
- create or use `codex/rag-transformation-checkpoints`;
- run baseline verification;
- commit and push the current transformation state.

Out of scope:

- changing the original AI Trend Radar UI;
- changing RAG runtime behavior;
- adding new product features;
- promoting draft golden questions into official quality gates.

## Architecture Boundary Gate

Layer:

- Research Artifact
- Runtime Governance

Inputs:

- existing roadmap/spec/evidence/execution-log documents;
- current dirty worktree;
- current test command and secret-scan expectations.

Outputs:

- Loop V2.1 execution-loop spec;
- decision record;
- evidence file;
- execution log;
- checkpoint commit and push result.

Data boundary:

- no new RAG corpus, citation, or retrieval data boundary.

Evidence boundary:

- adds checkpoint metadata as evidence: branch, commit hash, push status, verification results.

Reuse decision:

- reuse `docs/rag-transformation/` rather than adding a new governance system.

Future integration impact:

- should reduce Stage 2.5 and local app integration risk by keeping module history auditable.

Official component check:

- no new framework or dependency is needed for this governance module.

## Steps

1. Update execution-loop spec to V2.1.
2. Add decision record.
3. Add this plan.
4. Add evidence and execution-log placeholders.
5. Confirm checkpoint branch.
6. Run baseline verification.
7. Stage files and review staged inventory.
8. Commit baseline checkpoint.
9. Push checkpoint branch.
10. Record actual checkpoint hash and push result.
11. Commit the evidence update if needed.

## Verification

Baseline checkpoint requires:

- `git status --short`
- `git diff --check`
- `pnpm rag:check:p0`
- secret scan for known key patterns
- staged-file review for forbidden local artifacts

## Anti-Rabbit-Hole Rule For This Plan

If verification fails:

- shared-path bug: fix with focused coverage;
- docs formatting issue: fix documentation only;
- provider/data issue: record as residual risk;
- push failure: record `Checkpoint Blocked` and stop claiming backup success.

Do not change RAG architecture to satisfy this governance checkpoint.
