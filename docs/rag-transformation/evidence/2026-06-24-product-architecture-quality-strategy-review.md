# Evidence: Product Architecture And Quality Strategy Review

Date: 2026-06-24

## Executive Judgment

The project should stop spending the next loop on broad benchmark tuning.

Current structure is strong enough to move toward the next product layer:

- local corpus sync and citation-ready ingestion exist;
- Chroma and Neo4j runtime paths are verified;
- hybrid retrieval returns citations across the expanded 12-question structural benchmark;
- external search/provider routing exists, but live answer benchmark is blocked by environment policy;
- answer-policy and evidence-boundary guardrails exist.

The next product objective should be a repeatable research workflow, not another round of isolated RAG plumbing.

## Product North Star

AI Trend Radar RAG should become a local AI research cockpit.

The first valuable workflow:

1. user chooses a research topic;
2. system gathers internal trend evidence;
3. system separates internal, graph, external, weak, and insufficient evidence;
4. system produces a structured trend brief;
5. user can inspect citations, source quality, uncertainty, and follow-up actions.

This is more useful than a generic chat box because it turns daily AI signals into reviewable research artifacts.

## Current Module Assessment

| Module | Role | Current Maturity | Main Failure Mode | Next Strategy |
| --- | --- | --- | --- | --- |
| Data sync | Bring AI Trend Radar corpus into this repo | Locally verified | stale corpus or upstream shape drift | keep sync measurable; do not rebuild upstream yet |
| Ingestion | Turn reports/topics into citation-ready chunks | CI ready | missing metadata breaks trust | maintain citation fields as contract |
| Vector index | Semantic retrieval over text chunks | Locally verified | noisy or redundant hits | improve only when benchmark exposes real precision loss |
| Graph index | Entity/topic/date/source relationships | Live smoke verified | shallow entity normalization | expand only for workflow needs |
| Query understanding | Route intent, source, time, web need | CI ready | draft questions overfitting routing | keep deterministic and conservative |
| Retrieval planning | Build filters and retrieval constraints | CI ready | incorrect source/time filters | test focused filter behavior |
| Evidence layer | Preserve citations, quality, uncertainty | CI ready | cited but unsupported conclusions | expand claim/contradiction seeds gradually |
| Tool routing | Bound external search/deep fetch | CI ready | uncontrolled cost or tool overuse | keep deterministic before LangGraph |
| Agent answer path | Compose answer from evidence | structurally verified | live answer quality not fully verified | use local structural plus explicit live gates |
| Evaluation | Prevent regressions | CI ready for structure | test-set overfitting | map tests to product risk |
| Product workflow | Turn RAG into research output | planned | chat remains a generic interface | build Trend Brief Workflow MVP |
| Integration/UI | Reduce two-project friction | planned later | deployment complexity distracts core | defer until workflow proves value |

## Quality Strategy

Quality should be managed by risk type:

1. Freshness risk
   - Check manifest/latest dates.
   - Fail clearly when corpus is stale.

2. Retrieval risk
   - Use focused retrieval precision seeds.
   - Add reranking only if live/structural snapshots show actual noise.

3. Evidence risk
   - Require citations with date/source/title/excerpt.
   - Keep source-quality and uncertainty visible.

4. Claim risk
   - Expand semantic contradiction seeds gradually.
   - Do not claim full semantic correctness.

5. Workflow risk
   - Evaluate whether the output artifact helps the user make a research decision.
   - This cannot be solved by retrieval tests alone.

6. Cost/runtime risk
   - Keep default checks local and deterministic.
   - Run live API checks only as explicit benchmark gates.

## What Should Not Be Prioritized Next

- More broad golden-question expansion before Conrad reviews Q6-Q12.
- LangChain/LangGraph adoption just to look more "agentic".
- Original AI Trend Radar UI integration.
- Stage 2.5 repo unification.
- Full desktop/local app.
- Semantic reranking without a current precision regression.

## Recommended Next Gate

P2 Trend Brief Workflow MVP Spec.

Reason:

- The core RAG structure is now good enough for a product-facing workflow.
- A trend brief will force the system to use retrieval, graph evidence, source review, uncertainty, and follow-up actions together.
- It creates a real artifact for Conrad to judge instead of only benchmark rows.

## Proposed MVP Output

For a topic such as `RAG`, `Claude`, `AI Agent`, or `OpenAI`, generate:

- scope and time window;
- key trend themes;
- internal evidence table;
- graph relationship summary;
- source quality notes;
- uncertainty and missing evidence;
- suggested follow-up questions;
- optional external-search plan.

## Conrad Decisions Still Needed

- Review Q6-Q12 product labels and good/bad answer criteria.
- Decide whether the first Trend Brief MVP should focus on `RAG`, `AI Agent`, `Claude`, or `OpenAI`.
- Decide whether the brief should be saved as Markdown first or exposed through a local UI later.

## Evidence Inputs Used

- `golden-questions-readiness-2026-06-24.json`: 12 questions; 9 internal-only, 2 needs-web, 1 insufficient.
- `hybrid-structural-chat-snapshot-2026-06-24-q12.json`: 12/12 citations and graph citations.
- `pnpm rag:check:p0`: 162 tests passed in the previous loop.
