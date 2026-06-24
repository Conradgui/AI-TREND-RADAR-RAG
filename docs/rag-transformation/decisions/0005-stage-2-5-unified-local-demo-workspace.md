# Decision 0005: Stage 2.5 Unified Local Demo Workspace

## Status

Accepted as post-Nexus-like direction.

## Context

The current architecture keeps two projects separate:

- AI Trend Radar produces trend corpus through its existing automation.
- AI Trend Radar RAG consumes that corpus and provides local RAG/Agent analysis.

This is acceptable for the current P1/P2 work because it keeps the RAG core focused and reduces early complexity.

However, the user experience of deploying or understanding two projects is awkward. Conrad's medium-term product goal is a local-first research cockpit where the user can see trends and ask an Agent follow-up questions from one local experience.

The long-term vision could become a unified local app that handles:

- trend collection;
- scoring and report generation;
- local knowledge storage;
- RAG/Agent analysis;
- dashboard interaction.

But implementing the full software now would add too much product and engineering scope.

## Decision

After the current RAG core and Nexus-like iteration are mature, add a Stage 2.5: Unified Local Demo Workspace.

Stage 2.5 means:

- keep AI Trend Radar RAG as the main repo the user clones;
- include or reference the original AI Trend Radar project as an upstream module;
- provide a single local setup and run experience;
- preserve internal module boundaries between data production and knowledge application.

Stage 2.5 does not mean:

- full desktop software;
- complete replacement of GitHub Actions;
- production-grade local scheduler;
- multi-user SaaS;
- long-running background app lifecycle management.

## Candidate Integration Shapes

Use one of these after a focused evaluation:

1. `external/ai-trend-radar`
   - clone the original project into a clearly named folder;
   - simplest mental model;
   - easiest to inspect and replace.

2. Git submodule
   - keeps upstream history and version pinning;
   - adds Git workflow complexity.

3. Git subtree
   - keeps code inside one repo;
   - easier for users than submodule;
   - harder to sync cleanly.

4. Package extraction
   - extract original data-production logic into a package;
   - cleaner long term;
   - too early unless the integration proves valuable.

## Recommended First Implementation

Start with a simple `external/ai-trend-radar` or equivalent local upstream folder.

Expose one local command sequence from the RAG repo:

```text
prepare upstream data
sync corpus
ingest indexes
start local dashboard and Agent
```

The command names should be decided later, but the user-facing goal is:

```text
clone one repo -> configure one .env -> run one local workflow
```

## Product Implication

This reduces demo and self-use friction without prematurely building a full software product.

It supports Conrad's AIPM goal because it demonstrates:

- scope control;
- staged product thinking;
- local-first workflow design;
- awareness of deployment friction;
- refusal to overbuild before core value is proven.

## Engineering Implication

Keep boundaries explicit:

- data production module;
- corpus sync module;
- indexing module;
- RAG/Agent module;
- dashboard module.

Do not merge code just to make the repository look unified.

One repo experience is not the same as one tangled codebase.

## Roadmap Implication

The roadmap should no longer imply that P3 is simply "connect back to original GitHub Pages UI."

Instead:

- P1/P2: mature RAG core and Nexus-like local cockpit.
- Stage 2.5: single-repo local demo workspace.
- Future Vision: unified local app or desktop software only if repeated real use proves it is worth the cost.
