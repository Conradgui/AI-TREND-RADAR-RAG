# AI Trend Radar RAG Agent Operating Contract

This file is the first handoff entry for AI coding assistants working in this repository.

If you are an AI coding assistant, read this file before editing code. Then read:

1. `docs/rag-transformation/CURRENT_HANDOFF.md`
2. `docs/rag-transformation/AI_HANDOFF.md`
3. `docs/rag-transformation/roadmap.md`
4. `docs/rag-transformation/specs/2026-06-22-execution-loop-spec.md`
5. `docs/rag-transformation/specs/2026-06-21-quality-governance-spec.md`
6. `docs/rag-transformation/specs/2026-06-22-target-architecture-spec.md`

## Product North Star

AI Trend Radar RAG is becoming a local AI research cockpit.

It should let the user read fresh AI Trend Radar reports, ask an Agent grounded in local corpus/graph/external evidence, generate and inspect Trend Brief artifacts, and later reduce two-project friction through a unified local demo workspace.

It is not a generic chatbot, public SaaS, or full desktop app yet.

## Current Delivery Sequence

Use this sequence unless a newer roadmap explicitly supersedes it:

```text
P2 Trend Brief / Evidence foundation
    ↓
Stage 2.4 Local Product Flow And Dashboard Closure
    ↓
Stage 2.5 Agent Ability Closure
    ↓
Stage 2.6 Evidence Selection Quality
    ↓
Stage 2.7 / Former Stage 2.5 Unified Local Demo Workspace
```

The current priority is Stage 2.4: reuse the existing AI Trend Radar `index.html` dashboard as the local RAG cockpit shell.

## Operating Loop

Use Loop V2.2:

1. Orient from roadmap, target architecture, current spec, current plan, and recent evidence.
2. Explain the module in plain Chinese before implementation.
3. Define done across product, engineering, evidence, evaluation, non-goals, and residual risks.
4. Implement minimally using existing project patterns.
5. Verify precisely with the cheapest sufficient check.
6. Review at the right gate.
7. Record evidence at module or stage close, not after every tiny edit.
8. Decide the next bottleneck: product, architecture, engineering, evidence, or evaluation.
9. Checkpoint to GitHub at stage gates or major shared-path/module gates.

Do not turn tests, evidence polishing, or benchmark tuning into the main work unless the roadmap says evidence quality is the current bottleneck.

## Decision Rules

Conrad is a non-coding learner aiming at AIPM capability. Explain key architecture, framework, API, and data-structure decisions in Chinese before or alongside implementation.

Do not simply agree with Conrad's proposed direction. Treat it as a hypothesis and review it from:

- senior AI product manager: user value, scope, timing, opportunity cost;
- senior AI product architect: data flow, boundaries, maintainability, future integration;
- senior full-stack engineer: implementation cost, reliability, dependency risk, operability.

Ask Conrad before major roadmap changes, architecture shifts, large frameworks, LangChain/LangGraph introduction, original AI Trend Radar online UI/deployment changes, paid services, new secrets, destructive file operations, or system-level installs.

Small trusted project dependencies may be added when necessary, scoped, authoritative, and verified.

## Engineering Boundaries

Prefer official SDKs, authoritative libraries, and mature components for generic infrastructure.

Keep custom code focused on AI Trend Radar-specific policy:

- corpus normalization;
- internal/external evidence boundaries;
- citation schema;
- source quality;
- provider routing;
- answer policy;
- evaluation rubrics;
- local cockpit UI glue.

Avoid broad refactors unrelated to the module.

## Verification Ladder

Use the cheapest sufficient verification:

1. `schema`: docs/config/eval shape checks.
2. `focused`: tests for changed module behavior.
3. `canonical`: `pnpm rag:check:p0` for shared RAG path changes or module gates.
4. `local structural`: local runtime/retrieval checks without external LLM when possible.
5. `live external`: DeepSeek/search-provider calls only for explicit live gates, with saved evidence.

Do not run broad tests after every small edit.

## Evidence And Documentation

Durable records live under `docs/rag-transformation/`:

- `roadmap.md`: stage sequence and product direction.
- `AI_HANDOFF.md`: cross-agent operating manual.
- `specs/`: quality, loop, architecture, and module specs.
- `plans/`: implementation plans.
- `decisions/`: durable decisions and tradeoffs.
- `evidence/`: verification notes and audit records.
- `execution-log/`: what was done and why.
- `evals/`: golden questions and benchmark artifacts.
- `briefs/`: generated research artifacts.

Update full docs at module or stage gates. During active implementation, prefer concise status messages and focused evidence files only when useful.

## Git And Secret Safety

Default checkpoint branch:

```text
codex/rag-transformation-checkpoints
```

Before checkpoint:

- run `git status --short`;
- run `git diff --check`;
- run the minimum required verification;
- scan for API keys and tokens;
- review staged files.

Never commit `.env`, `.venv/`, `node_modules/`, Python caches, local DB/vector artifacts, or real API keys/tokens.

## Current UI Direction

Stage 2.4 reuses the existing AI Trend Radar `index.html`.

The local dashboard should open to the AI Trend Radar report view, keep report navigation/search/dark mode, wire the existing Agent drawer to local `/chat`, add Briefs discovery, move provider/Neo4j/Chroma/search/deep-fetch state into System, and preserve static GitHub Pages compatibility.

Do not replace the dashboard with a generic chat page.
