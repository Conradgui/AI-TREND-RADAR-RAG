# Evidence: Roadmap And Spec Governance Refresh

Date: 2026-06-22

## What Changed

Refreshed roadmap and specs after the P1 external evidence and deep-fetch work.

The update aligns documentation with the current project reality:

- P0 is no longer the active phase.
- P1 is now focused on controlled external evidence, deep fetch, provider adapters, graph runtime, and evaluation quality.
- The target system is described as layered architecture, not just a task list.
- Official or authoritative components are now preferred by policy.
- Capability status labels distinguish implemented, locally verified, live-smoke verified, CI-ready, production-ready, and not-claimed work.

## Files Added

- `docs/rag-transformation/specs/2026-06-22-target-architecture-spec.md`
- `docs/rag-transformation/decisions/0004-official-components-and-custom-code-boundary.md`

## Files Updated

- `docs/rag-transformation/roadmap.md`
- `docs/rag-transformation/specs/2026-06-21-quality-governance-spec.md`
- `docs/rag-transformation/specs/2026-06-22-execution-loop-spec.md`
- `docs/rag-transformation/README.md`

## Key Improvements

### Target Architecture

Added architecture layers:

- Data
- Index
- Retrieval
- Evidence
- Agent
- Evaluation
- Runtime
- Integration

### Official-First Component Policy

Added an ADR for component choice:

- use official SDKs and mature libraries for generic infrastructure;
- keep custom code focused on AI Trend Radar-specific policy and glue;
- record trade-offs when adding dependencies or expanding custom code.

### Status Labels

Added labels:

- `Planned`
- `Implemented`
- `Locally Verified`
- `Live Smoke Verified`
- `CI Ready`
- `Production Ready`
- `Not Claimed`

## Validation

Text checks confirmed:

- README now says current phase is P1.
- Execution loop current gate is P1 Live Deep Fetch Smoke and Runtime Toggle.
- Quality governance spec references the official-first ADR.
- Roadmap references the target architecture spec.

## Remaining Risk

- Historical P0 plan/evidence/execution-log files still mention Module 4 Chat Citations. This is intentional historical context, not current navigation.
- Future implementation loops must keep the current gate section updated.
