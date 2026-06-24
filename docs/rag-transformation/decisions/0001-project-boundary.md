# Decision 0001: Project Boundary Between AI Trend Radar And AI Trend Radar RAG

## Decision

Keep AI Trend Radar and AI Trend Radar RAG as separate but linked projects.

AI Trend Radar is the upstream data production project. It collects AI signals, scores topics, generates markdown/html/json artifacts, and publishes them through GitHub Pages.

AI Trend Radar RAG is the downstream knowledge application project. It consumes the published artifacts, builds retrieval and graph layers, powers an agent, and supports research workflows.

## Why This Decision

Replacing AI Trend Radar RAG with AI Trend Radar would look simpler in the short term but would blur two responsibilities:

- Data production: fetch, score, report, publish.
- Knowledge application: sync, index, retrieve, cite, evaluate, answer, research.

Keeping the boundary makes the system easier to reason about and closer to a real product architecture.

## Current Consequence

P0 work happens inside AI Trend Radar RAG. The original AI Trend Radar web UI Agent is not fixed in P0.

The RAG project should first sync fresh corpus from AI Trend Radar Pages and prove local RAG quality. After that, a later phase can connect the original web UI Agent to the mature RAG backend.

## Risks

- Cross-project coordination adds overhead.
- The RAG project can fall stale if corpus sync is not explicit.
- The same static UI code may exist in both projects and create confusion.

## Mitigation

- Treat AI Trend Radar Pages as the source of truth for public corpus.
- Build a sync step into AI Trend Radar RAG.
- Record every cross-project integration decision in this folder.
