# AI Trend Radar RAG Transformation

This folder is the durable project record for turning AI Trend Radar RAG from an experimental fork into a reliable personal AI research cockpit.

It exists for three reasons:

1. Keep the roadmap, decisions, plans, execution notes, and evidence outside chat history.
2. Make each module understandable before implementation, especially for a non-coding learner.
3. Prevent project drift by checking every execution step against the same source of truth.

## Current Product Boundary

AI Trend Radar is the data production system. It fetches AI signals, scores topics, generates reports, and publishes them to GitHub Pages.

AI Trend Radar RAG is the knowledge application system. It consumes AI Trend Radar's published corpus, builds retrieval and graph layers, powers an agent, and supports research workflows.

For the current phase, do not fix the Agent entry in the original AI Trend Radar web UI. First make AI Trend Radar RAG itself fresh, runnable, grounded, and testable.

Medium-term direction:

- keep two projects separate during current RAG core work;
- after Nexus-like iteration, reduce deployment friction through a Stage 2.5 unified local demo workspace;
- do not jump directly into a full desktop/local software product unless repeated real use proves it is worth the cost.

## Folder Map

- `roadmap.md`: P0/P1/P2/P3 transformation roadmap.
- `plans/`: module-level implementation plans.
- `specs/`: quality governance and acceptance rules.
- `decisions/`: durable product and technical decisions.
- `execution-log/`: what was executed, when, why, and how it was verified.
- `evidence/`: command output summaries, screenshots, links, and verification notes.
- `evals/`: golden questions, expected behavior, and evaluation records.

## Operating Protocol

Every substantial module must include:

1. Concept: what this module means in the RAG system.
2. Role: why it matters to the whole product.
3. Principle: how it works in plain language.
4. Business questions: what a senior AI PM or reviewer would ask.
5. Failure modes: how it can go wrong in real use.
6. Verification: how we prove the module improved the system.
7. Evidence: where the execution result is recorded.

## Roadmap vs Execution

The roadmap is not the implementation.

Use `roadmap.md` as the long-term direction and priority contract. Use files under `plans/` as the module-level execution guides. Use files under `specs/` as quality and execution rules. A module is not considered done because it is written in a plan; it is done only when the related code or data change has been verified and recorded under `evidence/` and `execution-log/`.

Use `specs/2026-06-22-target-architecture-spec.md` to understand the intended system layers:

- data;
- index;
- retrieval;
- evidence;
- agent;
- evaluation;
- runtime;
- integration.

Use `decisions/0004-official-components-and-custom-code-boundary.md` before expanding custom infrastructure. Generic capabilities should prefer official SDKs, authoritative libraries, or mature frameworks. Custom code should stay focused on AI Trend Radar-specific policy and glue.

For this project, each module should follow the execution loop in `specs/2026-06-22-execution-loop-spec.md`:

1. Orient.
2. Explain.
3. Define done.
4. Implement minimally.
5. Verify precisely.
6. Review at the right gate.
7. Record evidence.
8. Decide next.

## Current Phase

P1: Retrieval Quality + Agent Control.

P0 local grounding is complete as a focused-test baseline. The current work is improving controlled external evidence, deep fetch, provider routing, graph runtime hardening, and evaluation quality before any original AI Trend Radar UI integration.
