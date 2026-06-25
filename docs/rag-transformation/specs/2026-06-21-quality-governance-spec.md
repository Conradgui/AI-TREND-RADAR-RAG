# AI Trend Radar RAG Quality Governance Spec

## 1. Purpose

This spec defines how AI Trend Radar RAG work should be executed, reviewed, tested, and recorded.

Roadmap controls direction. Plans control module sequence. This spec controls quality.

The goal is not to maximize review activity. The goal is to prevent silent quality decay while keeping the project moving.

## 2. Scope

This spec applies to:

- P0 Fresh Corpus Sync + RAG Grounding
- P1 retrieval quality and agent control work
- P2 research workflow work
- Stage 2.4 local product/dashboard closure
- Stage 2.5 Agent ability closure
- Stage 2.6 evidence selection quality
- Stage 2.7 unified local demo workspace
- future local app work if repeated real use proves it is worth the cost

It covers:

- Stage gates
- Testing depth
- Code review depth
- Reviewer agent usage
- Bug handling
- Dead code and unfinished feature handling
- Token and progress control
- Cross-agent handoff

It does not cover:

- General product positioning
- Interview preparation narrative
- UI redesign details
- Deployment secrets or account-level setup

## 3. Operating Model

Use three layers of project documents:

1. `roadmap.md`
   - Defines long-term direction and priorities.
   - Answers: what are we building and in what order?

2. `plans/*.md`
   - Defines module-level implementation steps.
   - Answers: what do we do next?

3. `specs/*.md`
   - Defines quality rules and acceptance boundaries.
   - Answers: what does good enough mean?

New AI coding assistants must also read `AGENTS.md` and `docs/rag-transformation/AI_HANDOFF.md` before changing code. Those files summarize the current route, operating loop, and cross-tool handoff expectations.

A module is not complete because code runs once. A module is complete only when its behavior, business logic, and evidence are all acceptable for its stage.

## 4. Quality Principles

### 4.1 Business Logic Before Code Cleverness

RAG quality is not just code execution. Every module must preserve the product logic:

- Fresh corpus must really be fresh.
- Ingestion must not silently drop evidence.
- Retrieval must return relevant material, not merely any material.
- Citations must point to actual source evidence.
- Agent behavior must remain controllable and explainable.

### 4.2 Targeted Verification By Default

Do not run broad global tests after every small edit.

Default to precise verification:

- Changed a pure function: run its focused unit tests.
- Changed corpus sync: run sync tests and one dry-run or small real sync.
- Changed ingestion schema: run ingestion tests and inspect one real corpus sample.
- Changed server/chat behavior: run API-level smoke tests.
- Changed shared config or CI: run the broader affected suite.

### 4.3 Expand Testing Only When Risk Expands

Broader tests are required when a change touches:

- Shared configuration
- Dependency loading
- GitHub Actions
- Server entrypoints
- Data schema
- Retrieval ranking
- Citation extraction
- Security-sensitive boundaries
- Cross-project integration

### 4.4 Fix Blocking Problems Before Continuing

If a bug, security issue, schema mismatch, unfinished implementation, dead code path, or business logic contradiction affects the current module's correctness, stop and fix it before moving forward.

If an issue is real but does not block the current module, record it as follow-up work instead of turning the module into uncontrolled refactoring.

### 4.5 Official Components Before Custom Infrastructure

Prefer official SDKs, authoritative libraries, and mature frameworks for generic infrastructure.

Custom code should focus on AI Trend Radar-specific policy and glue:

- corpus normalization;
- evidence boundary rules;
- internal versus external citation separation;
- source quality policy;
- provider routing;
- golden-question rubrics;
- safety wrappers around tools.

Before expanding a custom implementation, check `decisions/0004-official-components-and-custom-code-boundary.md`.

If a mature component can reduce maintenance without hiding product logic, prefer the component.

If custom code is still chosen, keep it thin, tested, replaceable, and documented.

### 4.6 Cross-Agent Continuity

Project governance must not live only in chat history.

When a module or stage changes product direction, architecture boundaries, evidence standards, or execution-loop behavior, update the handoff path:

- `AGENTS.md` for high-level agent rules;
- `docs/rag-transformation/AI_HANDOFF.md` for current route and operating constraints;
- `roadmap.md` for delivery sequence;
- the relevant spec, plan, decision, evidence, or execution-log file.

Do not scatter new governance rules only in one assistant's private context.

## 5. Stage Gates

### Gate A: Small Change Gate

Use for narrow code or documentation changes.

Required checks:

- Explain what changed.
- Run the smallest relevant verification.
- Confirm no obvious orphan imports, unused helpers, or broken assumptions were introduced.

Review depth:

- Self-review only.
- No reviewer agent unless the change touches risky shared behavior.

### Gate B: Module Completion Gate

Use when a P0/P1/P2/P3 module is claimed complete.

Required checks:

- Run targeted tests for the module.
- Inspect relevant code diff.
- Record evidence under `docs/rag-transformation/evidence/`.
- Record execution notes under `docs/rag-transformation/execution-log/`.
- Check whether business logic matches the module goal.

Review depth:

- Use a reviewer pass.
- Reviewer may be the main agent for small modules.
- Use a separate reviewer agent for complex modules or risky changes.

### Gate C: Phase Completion Gate

Use when finishing a whole phase such as P0.

Required checks:

- Run all focused tests created during the phase.
- Run one end-to-end smoke path where feasible.
- Review roadmap and plan drift.
- Review unresolved risks and follow-up backlog.

Review depth:

- Use a separate reviewer agent with product, architecture, and full-stack perspectives.

### Gate D: Cross-Project Integration Gate

Use before touching the original AI Trend Radar UI, Worker backend, deployment, or secrets.

Required checks:

- Confirm project boundary decision still holds.
- Confirm API contract.
- Confirm secrets are not exposed to browser code.
- Confirm UI failure states are explicit.
- Confirm data freshness and citation behavior are preserved.

Review depth:

- Separate reviewer agent required.
- Broader integration tests required.

## 6. Reviewer Agent Protocol

The reviewer agent is not always on.

Use it when:

- A module reaches Gate B and has meaningful code/data behavior.
- A phase reaches Gate C.
- A change touches CI, deployment, secrets, retrieval ranking, citations, or agent tool routing.
- The main agent is uncertain about business logic or architecture.

Do not use it for:

- Simple documentation updates.
- Single-function edits with focused tests.
- Evidence file creation.
- Trivial typo fixes.

### Reviewer Persona

The reviewer should act as:

- A senior AI product manager
- A senior AI product architect
- A senior full-stack engineer

### Reviewer Focus

The reviewer must check:

- User value
- Business logic consistency
- RAG grounding and citation logic
- Data freshness and schema correctness
- Error handling
- Security boundaries
- Test adequacy
- Dead code, orphan code, and unfinished features
- Over-engineering risk

### Reviewer Output Format

Reviewer output should be short and actionable:

```text
Verdict: Pass / Pass With Follow-ups / Blocked

P0 Findings:
- ...

P1 Findings:
- ...

Non-blocking Notes:
- ...

Required Before Continuing:
- ...
```

The reviewer should not rewrite the whole project plan unless the plan itself is wrong.

## 7. Bug And Quality Issue Policy

### Blocking Issues

Fix before continuing:

- Code path cannot run.
- Tests for current module fail.
- Data schema mismatch causes missing evidence.
- Citation or retrieval behavior is misleading.
- Secret or token could leak.
- Agent can call unsafe tools or loop without control.
- A feature is only partially wired but appears complete.

### Non-Blocking Issues

Record and continue:

- Cosmetic code style issue.
- Low-risk naming improvement.
- Unrelated old test framework inconsistency.
- Future optimization.
- Optional refactor.

### Dead Code And Residual Feature Policy

Do not leave new dead code created during the current task.

If old dead code is discovered:

- Mention it.
- Do not delete it unless it blocks the current module.
- Record it as follow-up work if relevant.

If a feature is intentionally incomplete:

- Mark its boundary clearly.
- Ensure it cannot be mistaken for complete product behavior.

## 8. Testing Strategy

### Test Pyramid For This Project

1. Pure unit tests
   - Schema normalization
   - Chunking
   - citation extraction helpers
   - sync planning

2. Local smoke tests
   - Dry-run sync
   - small real sync
   - ingest sample inspection
   - server endpoint smoke checks

3. Integration tests
   - Retrieval against local store
   - Graph query behavior
   - chat response with citations

4. Phase-level checks
   - Golden questions
   - evidence quality review
   - CI workflow validation

### Global Test Rule

Do not use global tests as the default reflex.

Run global or broad tests when:

- Completing a phase
- Changing CI
- Changing dependency loading
- Changing shared server or config paths
- Preparing integration back to the original AI Trend Radar UI

## 9. Token And Progress Control

To avoid review overload:

- Use concise evidence summaries instead of pasting huge logs.
- Prefer targeted diffs over full-file rereads when context is known.
- Use reviewer agent only at gates.
- Keep review findings prioritized.
- Avoid turning low-risk follow-ups into immediate refactors.

Borrow the useful idea from token-compression tools: compress routine review output, but do not compress teaching explanations so much that Conrad loses the learning thread.

## 10. External Skill And Tool Policy

External skill repositories can be used as references, not automatic dependencies.

For now:

- Do not install `ComposioHQ/awesome-codex-skills`.
- Do not install `JuliusBrussee/caveman`.
- Borrow useful ideas selectively:
  - targeted CI review skills
  - PR review patterns
  - concise review output
  - stage-gated execution

Before installing any large dependency, external skill, system-level tool, deployment tool, or service connector:

- Explain what it is for.
- List what will be installed or moved.
- Explain the trade-off.
- Get explicit approval.

Small project-level dependencies may be added without stopping for approval when they are necessary, scoped to the current module, authoritative or widely trusted, and do not require accounts, secrets, paid services, or global system changes. The reason and verification must be recorded.

The original AI Trend Radar UI must not be changed until the RAG project has completed its core corpus, citation, evaluation, tool-boundary, and stability work.

## 11. Component Selection Policy

Use the official-first boundary in `decisions/0004-official-components-and-custom-code-boundary.md`.

### 11.1 Prefer Components For Generic Capabilities

Examples:

- LLM SDKs and official provider clients.
- Chroma client APIs for vector storage.
- Neo4j official driver for graph runtime.
- Search provider APIs or SDKs.
- Web extraction libraries when lightweight extraction is no longer enough.
- LangGraph or similar workflow frameworks when deterministic routing becomes too limited.
- Evaluation frameworks when local deterministic rubrics need broader coverage.

### 11.2 Keep Custom Logic Where Product-Specific

Examples:

- AI Trend Radar corpus schema adaptation.
- Question intent labels for the first golden set.
- Internal/external evidence wording.
- Provider routing policy.
- Source quality scoring policy.
- Benchmark rules for this product's expected behavior.

### 11.3 Required Trade-Off Note

When adding a new dependency or choosing custom code for non-trivial capability, record:

- what problem it solves;
- alternatives considered;
- engineering trade-off;
- product implication;
- verification performed.

## 12. Acceptance Checklist For Each Module

Before marking a module complete:

- [ ] The module goal is restated in plain language.
- [ ] The smallest relevant tests or smoke checks pass.
- [ ] The code diff was reviewed for obvious dead code and orphan changes.
- [ ] Business logic still matches the roadmap and plan.
- [ ] Component choice follows the official-first policy or records why custom code is appropriate.
- [ ] Evidence is recorded.
- [ ] Execution log is recorded.
- [ ] Blocking issues are fixed.
- [ ] Non-blocking issues are recorded or intentionally deferred.
