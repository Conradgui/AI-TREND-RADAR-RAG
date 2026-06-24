# Decision 0004: Official Components And Custom Code Boundary

## Status

Accepted for P1 and future work.

## Context

AI Trend Radar RAG should improve quality and speed by using official or authoritative components where they fit.

The project should not hand-roll mature infrastructure unless there is a project-specific reason.

At the same time, this project has product-specific behavior that generic frameworks will not provide out of the box:

- AI Trend Radar corpus semantics;
- evidence boundary wording;
- internal versus external citation separation;
- source quality policy;
- golden question expectations;
- cost-aware provider routing.

## Decision

Use an official-first, thin-custom-code approach.

### Prefer Official Or Authoritative Components For

- LLM provider clients and SDKs.
- Search provider APIs and official SDKs.
- Vector database clients.
- Graph database drivers.
- Workflow and agent orchestration frameworks when complexity warrants them.
- Web extraction libraries when basic extraction is no longer enough.
- Evaluation frameworks when deterministic project rubrics need a broader companion.
- Deployment and secret-management tooling.

### Keep Custom Code Focused On

- project-specific query understanding;
- AI Trend Radar corpus normalization;
- citation and evidence governance;
- provider routing policy;
- product-specific benchmark rules;
- small adapters that isolate provider differences;
- safety wrappers around tools such as URL fetch.

## Build-Vs-Buy Rule

Before building a non-trivial capability by hand, ask:

1. Is there an official SDK or mature library for this?
2. Does the library solve the actual problem, or only a generic version of it?
3. Does adding it reduce maintenance more than it adds dependency risk?
4. Can Conrad understand the operational trade-off?
5. Does this require new accounts, secrets, payment, deployment, or global install?

If the answer favors a library, prefer the library.

If the answer favors custom code, keep the code thin, tested, and replaceable.

## Framework-Specific Guidance

### LangChain

Use when it reduces boilerplate for model, retriever, or tool integration.

Do not use merely to claim the project "uses LangChain."

### LangGraph

Consider when the agent workflow needs explicit state, multi-step branching, retries, and durable traces.

Do not introduce it while deterministic routing is still enough.

### Chroma

Use official Chroma client APIs for vector storage.

Avoid custom vector-store abstractions unless needed to swap providers.

### Neo4j

Use the official Neo4j driver and established Cypher patterns.

Do not simulate graph behavior in ad hoc structures once Neo4j runtime is available.

### Web Extraction

The current custom URL fetch layer exists because security boundaries are project-specific.

If extraction quality becomes important, evaluate mature libraries such as readability-style extractors or other trusted HTML extraction tools before expanding custom parsing.

### Evaluation

Keep deterministic project rubrics because they encode product rules.

Consider Ragas, DeepEval, LangSmith, or similar tools only after the local rubric suite is stable and the added complexity is justified.

## Decision Boundary

Codex can independently add small project-level dependencies only when they are:

- necessary for the current module;
- scoped to this project;
- authoritative or widely trusted;
- free of account, secret, paid service, or global install requirements;
- recorded with reason and verification.

Conrad must decide before:

- adding major frameworks;
- changing architecture direction;
- adding services or paid APIs;
- changing deployment or production secret handling;
- changing the original AI Trend Radar UI.

## Product Implication

This keeps the project practical:

- faster implementation where official tools exist;
- less maintenance burden;
- fewer fragile custom systems;
- clearer story for interviews and product reviews.

## Engineering Implication

Custom code should be treated as policy and glue, not as a replacement for mature infrastructure.

When custom code grows beyond a thin layer, create a follow-up to evaluate a library or framework.
