# AI Trend Radar RAG Target Architecture Spec

Date: 2026-06-22

## 1. Purpose

This spec defines the target architecture for AI Trend Radar RAG.

It exists to keep implementation work aligned with the product goal: a grounded AI research cockpit, not a generic chatbot with scattered tools.

## 2. Target Product Shape

AI Trend Radar RAG should become an internal-first, evidence-governed research system.

The mature system should:

- sync fresh AI Trend Radar corpus;
- retrieve and cite internal evidence;
- use external search only when internal evidence is insufficient or freshness is required;
- inspect high-value external sources through safe deep fetch;
- separate internal evidence, external evidence, conflicts, and uncertainty;
- support repeatable trend research workflows;
- later reduce two-project friction through a unified local demo workspace;
- consider a full local app only if repeated use proves it is worth the cost.

## 3. Architecture Layers

### 3.1 Data Layer

Role:

- bring AI Trend Radar reports, topic pools, search index, and manifest data into this project.

Current state:

- fresh corpus sync exists;
- local digest files and manifest are available;
- topic-pool compatibility exists.

Target state:

- corpus sync is automated and CI-visible;
- data freshness is measurable;
- sync failures are explicit.

### 3.2 Index Layer

Role:

- turn corpus data into retrievable vector and graph indexes.

Current state:

- ChromaDB vector path is populated and verified locally;
- Neo4j graph runtime is verified through Docker Compose and local structural benchmark.

Target state:

- Chroma vector index and Neo4j graph index are both populated and tested;
- entities, topics, sources, dates, and evidence relationships are normalized;
- graph edges preserve evidence and confidence.

### 3.3 Retrieval Layer

Role:

- choose how to retrieve evidence for a question.

Current state:

- deterministic query understanding exists;
- metadata filters and vector-only fallback exist;
- hybrid retrieval slice 1 exists.

Target state:

- hybrid vector plus graph retrieval is reliable;
- reranking is evaluated;
- retrieval quality is benchmarked against golden questions.

### 3.4 Evidence Layer

Role:

- preserve source truth and prevent unsupported claims.

Current state:

- internal citations exist;
- external citation schema exists;
- source quality classification exists;
- Tavily external evidence can be merged into chat;
- safe URL fetch and injectable deep fetch exist.

Target state:

- external source fetching is runtime-gated;
- deep-fetch results are evaluated;
- source conflict handling exists;
- answer generation always exposes evidence boundary and uncertainty.

### 3.5 Agent Layer

Role:

- coordinate tools without losing control.

Current state:

- deterministic tool routing contract exists;
- external search and fetch_url steps are traceable;
- full LangGraph-style workflow is not implemented.

Target state:

- simple questions stay cheap;
- complex questions follow a bounded multi-step workflow;
- tool calls have budgets, traces, fallback behavior, and failure reasons;
- LangGraph or a similar official framework is considered only when workflow complexity justifies it.

### 3.6 Evaluation Layer

Role:

- make quality measurable.

Current state:

- golden questions exist;
- corpus availability, query plan, live chat, answer policy, tool routing, external evidence, and external answer quality checks exist.

Target state:

- golden questions expand beyond the first five;
- benchmarks compare internal-only, internal-plus-external, and research-workflow modes;
- evaluation outputs guide roadmap priority.

### 3.6.1 Research Artifact Layer

Role:

- convert retrieved evidence into durable, reviewable research outputs.

Current state:

- deterministic Trend Brief Markdown assembly exists;
- `python -m rag.generate_trend_brief` exists;
- the module is wired into the canonical P0 check;
- first real local artifact smoke generated `trend-brief-rag-2026-06-24.md`.
- explicit `--mode live-external` request planning exists and is P0-covered;
- live external Trend Brief runtime smoke generated `trend-brief-rag-live-external-2026-06-24.md`;
- live external source quality remains weak/generic.

Target state:

- topic briefs can be generated from local corpus and graph evidence;
- generated briefs are reviewed as product artifacts, not only as test outputs;
- optional LLM-assisted summaries remain live-gated and evidence-bounded.

### 3.7 Runtime Layer

Role:

- make local and future deployed behavior predictable.

Current state:

- vector-only local runtime is verified;
- DeepSeek LLM access is verified;
- focused RAG check exists;
- live deep fetch is not enabled by default.

Target state:

- runtime toggles control external search and deep fetch;
- CI separates deterministic checks from live API checks;
- secrets remain server-side only.

### 3.8 Integration Layer

Role:

- reduce deployment friction and eventually decide whether a unified local app is warranted.

Current state:

- original UI integration and unified local workspace are explicitly out of scope for current P1 work.

Target state:

- Stage 2.5 provides a single-repo local demo workspace after the RAG core and Nexus-like cockpit mature;
- the upstream AI Trend Radar project can be included or referenced as a module;
- a full local app or desktop shell remains future vision, not current scope.

## 4. Capability Status Labels

Use these labels in roadmap and evidence files:

- `Planned`: not implemented yet.
- `Implemented`: code or data path exists.
- `Locally Verified`: deterministic local tests or smoke checks passed.
- `Live Smoke Verified`: a low-volume real API/runtime check passed.
- `CI Ready`: deterministic checks are wired into the canonical check command.
- `Production Ready`: deployable with monitoring, failure modes, cost controls, and security review.
- `Not Claimed`: intentionally not represented as complete.

Do not use "done" without specifying the status label.

## 5. Current Architecture Status

As of 2026-06-25:

- Data Layer: `Locally Verified`
- Index Layer: vector path `Locally Verified`; graph citation-ready retrieval and graph relationship paths `Live Smoke Verified`
- Retrieval Layer: query planning, first hybrid slice, mixed-source metadata filtering, citation-ready graph result metadata, live hybrid retrieval, and graph question planner service evidence `Live Smoke Verified`
- Evidence Layer: internal citations, multi-provider external citations, provider fallback, live URL deep fetch, claim-level seed checks, retrieval precision checks, and seed-level semantic contradiction checks `CI Ready`; full semantic correctness `Not Claimed`
- Agent Layer: deterministic routing `Locally Verified`; full workflow agent `Not Claimed`
- Evaluation Layer: expanded 12-question draft asset, provider quality matrix, claim-level seed, semantic contradiction seed, retrieval precision, graph reasoning, and graph question planner checks `CI Ready`
- Research Artifact Layer: deterministic Trend Brief generator `CI Ready`; first real generated artifact `Live Smoke Verified`; live external runtime `Live Smoke Verified`; external source quality gate `Live Smoke Verified`; source relevance review `Locally Verified`; batched external evidence acquisition `Live Batch Verified`
- Runtime Layer: vector-only local runtime `Live Smoke Verified`; live deep fetch toggle `CI Ready`
- Integration Layer: Stage 2.5 unified local demo workspace `Planned`; full local app `Not Claimed`

## 6. Near-Term Priority

The next useful work should focus on:

1. Integrate the live batch evidence into the Trend Brief path, prioritizing academic/official/developer citations.
2. Consider source deepening for weak external citations.
3. Add LLM-assisted summary only if deterministic output is structurally useful but too hard to read.
4. Expanded live answer benchmark only when the execution environment permits external LLM data transfer.
5. Semantic reranking or source-aware reranking only if retrieval precision regresses again.
6. Richer graph question coverage when required by the trend brief workflow.
7. Stage 2.5 single-repo local demo workspace after Nexus-like iteration.
