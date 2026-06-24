# Evidence: Stage 2.5 Unified Local Demo Workspace Decision

Date: 2026-06-23

## What Changed

Accepted the B plan for reducing two-project deployment friction after the current RAG core and Nexus-like iteration mature.

The project will not jump directly into a full local desktop/software product.

Instead, the roadmap now includes Stage 2.5:

- one RAG repo as the user-facing local workspace;
- original AI Trend Radar included or referenced as an upstream module;
- one local command/workflow for data preparation, sync, ingest, dashboard, and Agent;
- internal boundaries preserved between data production and knowledge application.

## Files Added

- `docs/rag-transformation/decisions/0005-stage-2-5-unified-local-demo-workspace.md`

## Files Updated

- `docs/rag-transformation/roadmap.md`
- `docs/rag-transformation/specs/2026-06-22-target-architecture-spec.md`
- `docs/rag-transformation/README.md`

## Product Interpretation

This decision balances user experience and implementation cost.

It acknowledges that asking users to deploy two projects is awkward, but avoids prematurely building a full software product with scheduler, desktop shell, background lifecycle, and complete data-production replacement.

Stage 2.5 is a demo/workspace unification step, not final softwareization.

## Current Boundary

Current P1/P2 work remains focused on RAG core quality:

- retrieval;
- evidence governance;
- external tools;
- deep fetch;
- graph runtime;
- evaluation.

Stage 2.5 comes later, after Nexus-like iteration.

## Remaining Risk

- The best technical form is not yet chosen: local upstream folder, submodule, subtree, or package extraction.
- The original AI Trend Radar project has not yet been cloned or evaluated for Stage 2.5 integration.
- A full local app remains future vision, not a current commitment.
