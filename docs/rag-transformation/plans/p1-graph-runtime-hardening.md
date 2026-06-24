# P1 Graph Runtime Hardening Plan

Date: 2026-06-23

## Module

P1 Graph Runtime Hardening

## Concept

Graph Runtime Hardening means proving that the graph path is not just present in code, but can contribute usable, citation-ready evidence to answers.

Because Docker is not available in the current machine environment, live Neo4j runtime verification is blocked for now. This module still advances the graph path by fixing deterministic graph retrieval behavior that can be tested without Neo4j.

## Definition of Done

Product behavior:

- Graph retrieval results can become citations rather than anonymous synthetic snippets.
- The project clearly records whether live Neo4j runtime is verified or blocked.

Engineering behavior:

- Hybrid graph search returns citation-ready metadata.
- Tests prove graph results include source, date, title, URL, citation ID, and evidence excerpt when available.

Evidence behavior:

- Execution log records Docker/Neo4j blocker.
- Roadmap does not claim live graph runtime until the blocker is resolved.

Evaluation behavior:

- Focused hybrid retriever tests pass.
- Canonical RAG check passes.

Non-goals:

- Do not install Docker automatically.
- Do not claim Neo4j live runtime verification.
- Do not implement full graph entity normalization in this slice.

Residual risks:

- Live Neo4j ingestion and querying still require Docker or another Neo4j instance.
- Current graph search still relies on full-text entity search rather than richer path reasoning.
