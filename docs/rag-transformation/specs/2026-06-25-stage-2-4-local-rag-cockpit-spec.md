# Stage 2.4 Local RAG Cockpit Spec

Date: 2026-06-25

## 1. Purpose

Stage 2.4 turns AI Trend Radar RAG from a set of working RAG capabilities into a usable local product flow.

The goal is not to design a new dashboard from scratch. The goal is to reuse the existing AI Trend Radar Web UI as the local cockpit shell, then connect the mature RAG capabilities that already exist: local corpus, `/chat`, citations, Trend Brief artifacts, health checks, ingestion, and provider status.

## 2. Product Position

The product should feel like:

> "I open one local AI Trend Radar cockpit, read the latest trend reports, ask the Agent follow-up questions, generate research briefs, and inspect whether the system is ready."

It should not feel like:

- a generic chatbot;
- a standalone system-health dashboard;
- a replacement for the original online AI Trend Radar GitHub Pages site;
- a full desktop app;
- a premature Stage 2.7 / former Stage 2.5 repo unification.

## 3. User Jobs

### 3.1 Read Latest Trends

The user opens the local service and sees the familiar AI Trend Radar report dashboard.

Expected behavior:

- load `manifest.json`;
- show latest reports in the existing sidebar;
- keep search, report rendering, dark mode, and navigation behavior;
- preserve the existing information-board style.

### 3.2 Ask Agent Follow-Up Questions

The user opens the Agent drawer and asks questions about recent AI trends, RAG, Claude, GitHub tools, or a current report.

Expected behavior:

- local mode calls FastAPI `/chat`;
- answers include citations when evidence exists;
- answers distinguish internal corpus evidence from external evidence when available;
- insufficient evidence is stated explicitly instead of hidden.

### 3.3 Generate Or Review Trend Briefs

The user can inspect existing Trend Brief artifacts and later trigger generation from the local UI.

Expected behavior:

- show generated briefs under `docs/rag-transformation/briefs/`;
- expose topic, generated date, mode, source quality status, and file path;
- provide a small action surface for generating a new brief only after backend support is ready.

### 3.4 Inspect System State

The user should know whether the local cockpit can answer questions reliably, but this must not be the default homepage.

Expected behavior:

- System view shows LLM provider, Neo4j status, Chroma chunk count, retriever mode, deep fetch status, search provider configuration, latest corpus date, and ingest status;
- status is actionable and concise;
- user-facing error messages should explain the missing prerequisite.

## 4. Scope Boundary

### In Scope

- Serve the AI Trend Radar `index.html` shell from the local FastAPI runtime.
- Replace the hardcoded MCP Worker chat URL with local-first chat routing.
- Add local-only status and brief endpoints.
- Add a System area for runtime readiness.
- Preserve static GitHub Pages compatibility.
- Keep the UI implementation in vanilla HTML/CSS/JS for this stage.

### Out Of Scope

- No original AI Trend Radar online repo modification.
- No Electron, Tauri, or native desktop shell.
- No full migration from GitHub Actions scraping into this project.
- No React/Vue rewrite.
- No LangChain/LangGraph adoption only for UI reasons.
- No new large dependency unless it clearly removes more complexity than it adds.

## 5. Product Architecture

Stage 2.4 belongs to the Integration and Runtime layers.

It consumes existing layers rather than rebuilding them:

- Data Layer: existing synced `manifest.json`, `digests/`, `topic-pool.json`, and search index.
- Index Layer: existing Chroma and Neo4j runtime state.
- Retrieval Layer: existing vector-only or hybrid retriever.
- Evidence Layer: existing citation, source quality, external evidence, and uncertainty logic.
- Agent Layer: existing `/chat` orchestration.
- Research Artifact Layer: existing Trend Brief Markdown artifacts.
- Runtime Layer: FastAPI local service.
- Integration Layer: AI Trend Radar Web UI shell plus local API wiring.

## 6. UI Structure

### 6.1 Default Landing: Radar

The default landing view remains the AI Trend Radar report dashboard.

This is important because user value starts from reading trend information, not from inspecting infrastructure.

### 6.2 Agent Drawer

The existing `AGENT` entry remains the primary chat surface.

Required improvements:

- use local `/chat` when running under the FastAPI local service;
- show answer, citations, and evidence boundary;
- keep report navigation from citation clicks when possible;
- show a clear local-service-required state when opened from static GitHub Pages.

### 6.3 Briefs View

Briefs should be a lightweight product area, not a separate research pipeline.

Required fields:

- brief title;
- topic;
- generated date;
- mode: `local-only`, `internal-plus-external-plan`, or `live-external`;
- source quality status when available;
- artifact path or open action.

### 6.4 System View

System view is for readiness, not the default experience.

Required fields:

- configured;
- provider;
- Neo4j connected;
- Chroma chunk count;
- retriever mode;
- deep fetch enabled;
- configured search providers;
- latest corpus date;
- local service version when available.

## 7. Backend API Contract

### Existing APIs To Reuse

- `GET /health`
- `POST /chat`
- `POST /ingest`

### New Minimal APIs

#### `GET /dashboard/status`

Purpose:

- provide one UI-friendly status object instead of making the frontend infer readiness from multiple sources.

Recommended response shape:

```json
{
  "service": "ok",
  "configured": true,
  "provider": "deepseek",
  "neo4j_connected": true,
  "chromadb_chunks": 1234,
  "retriever_mode": "hybrid",
  "deep_fetch_enabled": true,
  "search_providers": ["tavily", "brave", "exa", "github"],
  "latest_corpus_date": "2026-06-21"
}
```

#### `GET /briefs`

Purpose:

- list local Trend Brief artifacts in a UI-friendly shape.

Recommended response shape:

```json
{
  "briefs": [
    {
      "title": "Trend Brief: RAG",
      "topic": "RAG",
      "generated_date": "2026-06-25",
      "mode": "live-external",
      "source_quality": "mixed",
      "path": "docs/rag-transformation/briefs/trend-brief-rag-source-quality-2026-06-25.md"
    }
  ]
}
```

#### `POST /briefs/trend`

Purpose:

- trigger the existing Trend Brief generation workflow from the UI after the backend can safely expose it.

Stage 2.4 default:

- implement only after `GET /briefs` and local dashboard wiring are stable;
- keep it explicit, not auto-run on page load;
- return artifact metadata instead of raw console output.

## 8. Data Flow

### 8.1 Report Reading

```text
index.html -> manifest.json -> digests/YYYY-MM-DD/*.md -> rendered report
```

### 8.2 Agent Chat

```text
Agent drawer -> POST /chat -> chat_service -> retriever/tools -> answer + citations -> UI
```

### 8.3 System Status

```text
System view -> GET /dashboard/status -> /health + local corpus metadata + provider summary -> UI
```

### 8.4 Brief Review

```text
Briefs view -> GET /briefs -> docs/rag-transformation/briefs/*.md metadata -> UI
```

## 9. Failure Modes

### Missing Local Service

If the user opens the static GitHub Pages version, the Agent should not call the placeholder Worker URL.

Expected behavior:

- show "Local RAG service is not running" or equivalent;
- do not show a generic `Failed to fetch`.

### Missing LLM Key

Expected behavior:

- System view shows provider configuration is incomplete;
- Agent returns an actionable local configuration message;
- no key is printed.

### Neo4j Unavailable

Expected behavior:

- fallback to vector-only mode when possible;
- System view shows retriever mode as `vector-only`;
- do not describe Graph RAG as active when Neo4j is disconnected.

### Empty Or Stale Corpus

Expected behavior:

- show latest corpus date;
- if no local manifest exists, keep a clear report-loading error;
- recommend corpus sync or ingest action.

## 10. Implementation Modules

### Module 1: Local Dashboard Entry

Goal:

- local FastAPI `/` serves the AI Trend Radar dashboard shell instead of the old experimental chat page.

Acceptance:

- opening local service shows the report dashboard;
- report navigation and search still work.

### Module 2: Local Agent Wiring

Goal:

- Agent drawer calls local `/chat` in local runtime.

Acceptance:

- local chat works without editing a Worker URL;
- citations render without breaking existing report navigation;
- static mode fails gracefully.

### Module 3: System Status

Goal:

- add `/dashboard/status` and a System UI area.

Acceptance:

- System shows runtime readiness without becoming the homepage;
- provider and search status are summarized without exposing secrets.

### Module 4: Briefs Index

Goal:

- add `/briefs` and a simple Briefs view for existing artifacts.

Acceptance:

- generated brief artifacts are discoverable from the UI;
- no new brief generation is required for this module.

### Module 5: Brief Generation Action

Goal:

- optionally expose existing Trend Brief generation from the UI.

Acceptance:

- user explicitly triggers generation;
- API returns created artifact metadata;
- long-running or external mode failures are surfaced cleanly.

## 11. Verification Plan

### Focused Checks

- API shape tests for `/dashboard/status`.
- API shape tests for `/briefs`.
- Agent frontend routing logic tested through local smoke or a minimal JS check when practical.

### Canonical Check

- Run `pnpm rag:check:p0` after shared backend or RAG path changes.

### Local Smoke

- Start `pnpm rag:serve`.
- Open local URL.
- Verify:
  - default page is the AI Trend Radar dashboard;
  - latest report loads;
  - Agent calls local `/chat`;
  - System shows provider, Neo4j, Chroma, retriever mode, and corpus date;
  - Briefs lists existing artifacts.

### Static Compatibility Smoke

- Open `index.html` statically or inspect static mode behavior.
- Verify:
  - reports still load in GitHub Pages-style usage;
  - Agent does not call the placeholder Worker URL;
  - local-only functions show a clear disabled state.

## 12. Stage Gate

Stage 2.4 is complete when:

- local service opens into the AI Trend Radar dashboard;
- Agent can answer through local `/chat`;
- citations are visible and useful;
- System status is available but not the default page;
- existing Trend Brief artifacts are visible;
- static GitHub Pages compatibility is not broken;
- focused checks and required canonical checks pass;
- execution log records implementation evidence and residual risks.

## 13. Residual Risks

- The original `index.html` is a single static file, so adding too much behavior there can hurt maintainability.
- Directly mixing static GitHub Pages behavior with local FastAPI behavior can create confusing environment branches.
- Brief generation may become slow or external-API-dependent; it should stay explicit and observable.
- Stage 2.4 improves product flow but does not prove research-quality semantic correctness by itself.

## 14. Relationship To Roadmap

Stage 2.4 sits between P2 Trend Brief / Evidence foundation and the later Agent/Evidence/Workspace stages.

- P2 creates research workflows and artifacts.
- Stage 2.4 makes those capabilities usable from a local cockpit.
- Stage 2.5 improves Agent ability inside the cockpit.
- Stage 2.6 improves evidence selection quality after real Agent usage exposes the highest-value retrieval failures.
- Stage 2.7, formerly recorded as Stage 2.5, later reduces two-project deployment friction.

This prevents the project from jumping directly from backend capability work to repo unification before the local product experience is proven.
