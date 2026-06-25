# Stage 2.4 Local RAG Cockpit Implementation Plan

## Module

Stage 2.4 Local RAG Cockpit

## Objective

Use the existing AI Trend Radar Web UI as the local RAG product shell.

The implementation should make the local user flow coherent:

```text
open local dashboard -> read latest report -> ask Agent -> inspect citations -> review briefs -> inspect System status if needed
```

## Architecture Boundary Gate

1. Layer:
   - Integration and Runtime.
   - It consumes Data, Retrieval, Evidence, Agent, and Research Artifact layers.

2. Inputs:
   - `index.html`, `manifest.json`, `digests/`, `docs/rag-transformation/briefs/`, `/health`, `/chat`.

3. Outputs:
   - local dashboard page;
   - `/dashboard/status`;
   - `/briefs`;
   - optional `/briefs/trend`.

4. New boundaries:
   - local runtime UI behavior vs static GitHub Pages behavior;
   - user-facing status summary vs secret-bearing config.

5. Reuse:
   - reuse `index.html`, existing FastAPI server, existing Trend Brief artifacts, existing `/chat`;
   - do not introduce a frontend framework in this stage.

6. Future integration:
   - preserve Stage 2.5 optionality by keeping upstream data generation separate from local RAG runtime.

## Work Sequence

### Step 1: Local Dashboard Entry

Change:

- make FastAPI `/` serve the AI Trend Radar dashboard shell;
- keep the old `rag/web/chat.html` as fallback or legacy path if useful.

Verification:

- local service opens a report dashboard;
- no RAG backend behavior is changed.

### Step 2: Agent Local Routing

Change:

- replace hardcoded Worker chat endpoint with local-first endpoint detection;
- call `/chat` under local FastAPI;
- show a clear disabled state in static-only mode.

Verification:

- local Agent can send a message to `/chat`;
- static mode does not produce generic `Failed to fetch`.

### Step 3: Citation Rendering Review

Change:

- ensure chat citations render date, source, title or excerpt;
- citation clicks should navigate to a report when the target exists;
- otherwise keep the citation visible without a broken link.

Verification:

- mocked or local chat response with citations renders correctly.

### Step 4: System Status API And UI

Change:

- add `GET /dashboard/status`;
- add System view or drawer area in the existing UI;
- summarize provider, Neo4j, Chroma, retriever mode, search provider config, deep fetch, and corpus date.

Verification:

- focused API test;
- local UI smoke.

### Step 5: Briefs Index API And UI

Change:

- add `GET /briefs`;
- list existing Trend Brief artifacts;
- keep generation action disabled or absent until Step 6.

Verification:

- focused API test;
- UI lists existing brief metadata.

### Step 6: Optional Brief Generation Action

Change:

- add `POST /briefs/trend` only after read-only Briefs works;
- use existing Trend Brief generation code;
- return artifact metadata.

Verification:

- focused backend test with mocked generation path;
- local smoke only when runtime dependencies are available.

## Testing Policy

Use the Loop V2.2 cadence:

- docs-only or UI copy changes: `git diff --check` and targeted inspection;
- API changes: focused tests plus py_compile when relevant;
- shared RAG path changes: `pnpm rag:check:p0`;
- live local UI gate: one local smoke, not repeated benchmark tuning.

Do not run broad benchmark loops for Stage 2.4 unless a shared retrieval or answer-quality path changes.

## Definition Of Done

Product:

- local homepage is the AI Trend Radar dashboard;
- Agent is usable from that dashboard;
- System status exists but does not dominate the first screen;
- Briefs are discoverable;
- static mode fails gracefully for local-only features.

Engineering:

- no new frontend framework;
- no secret leakage;
- local/static environment logic is explicit;
- provider-specific logic does not leak into the UI beyond display labels.

Evidence:

- focused tests cover new API contracts;
- required canonical checks pass;
- one execution log records implementation evidence, residual risks, and next bottleneck.

## Non-Goals

- No online AI Trend Radar UI fix.
- No Stage 2.5 repo unification.
- No full local software packaging.
- No large UI rewrite.
- No new scraping replacement for GitHub Actions.
