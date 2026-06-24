# AI Trend Radar RAG Execution Loop Spec

## 1. Purpose

This spec defines the repeatable loop for moving AI Trend Radar RAG from an experimental codebase into a reliable AI research system.

The loop exists to prevent two failure modes:

- Moving fast but leaving ungrounded, untested, or half-finished behavior.
- Reviewing so heavily that the project stops progressing.

## 2. Core Loop

Current version: V2.1.

Every substantial module should follow this loop:

1. Orient
   - Read the roadmap, target architecture spec, current plan, quality spec, and latest execution logs.
   - Confirm the current module and why it matters.

2. Explain
   - Explain the module in plain Chinese before implementation.
   - Cover: concept, role in the RAG system, principle, business value, and likely failure modes.

3. Define Done
   - Write or restate the module's Definition of Done.
   - Include product behavior, engineering checks, evidence, and evaluation expectations.

4. Implement Minimally
   - Make the smallest useful change that advances the current module.
   - Prefer existing project patterns.
   - Prefer official or authoritative components for generic infrastructure.
   - Avoid unrelated refactors.

5. Verify Precisely
   - Run focused tests or smoke checks for the changed behavior.
   - Use broader tests only when the risk expands.

6. Review At The Right Gate
   - Use light self-review for small changes.
   - Use module gate review for completed modules.
   - Use reviewer agent only when required by the quality governance spec.

7. Record Evidence
   - Save evidence under `docs/rag-transformation/evidence/`.
   - Save execution notes under `docs/rag-transformation/execution-log/`.
   - Record residual risks instead of hiding them.

8. Decide Next
   - If blocked, fix blocking issues before continuing.
   - If complete, return to the roadmap and move to the next module.
   - If user decision is required, stop and ask Conrad.

9. Checkpoint To GitHub
   - Run the minimum required verification for the module risk level.
   - Run secret scan and staged-file review before commit.
   - Commit to `codex/rag-transformation-checkpoints`.
   - Push the checkpoint branch to GitHub.
   - Record branch, commit hash, push status, verification result, and residual risks in evidence and execution log.
   - If push fails, record `Checkpoint Blocked`; do not claim the work is backed up.

## 2.1 Loop V2 Efficiency Rule

Use scripts before model reading whenever possible.

Preferred evidence tools:

- `rg` for locating text and files.
- `jq` for JSON summaries.
- `awk` or small Python scripts for counts and simple transformations.
- focused unit tests for changed local behavior.
- canonical checks only at module gates or shared-path risk points.
- live API benchmarks only as explicit benchmark gates.

Use model judgment for:

- product judgment;
- architecture tradeoffs;
- ambiguous failure classification;
- roadmap priority;
- user-facing synthesis.

Do not spend model context reading long raw artifacts when a command can summarize the required fact.

## 2.2 Loop V2 Draft-Test Rule

Draft tests are coverage maps, not automatic architecture requirements.

When a draft test exposes a problem, classify it before coding:

- `clear shared-path bug`: fix with focused tests;
- `product judgment`: stop and ask Conrad;
- `nice-to-have refinement`: record as residual risk;
- `architecture shift`: stop and ask Conrad.

Q6-Q12 are currently accepted as draft golden questions.

They should guide exploration, but they should not force broad architecture changes until Conrad reviews the product labels and good/bad answer criteria.

## 2.3 Loop V2.1 Architecture Boundary Gate

Before writing important code, answer these questions:

1. Which layer does this module belong to?
   - Data / Index / Retrieval / Evidence / Agent / Evaluation / Runtime / Research Artifact / Integration
2. What are its inputs and outputs?
3. Does it introduce a new data boundary or evidence boundary?
4. Does it reuse an existing module or create a new module? Why?
5. Will it make future UI, Stage 2.5, or local app integration harder?
6. Is there an official or authoritative component that should be reused instead of custom infrastructure?

If the answers reveal an architecture shift, stop and ask Conrad before implementation.

## 2.4 Loop V2.1 Anti-Rabbit-Hole Rule

When a test failure or artifact-quality issue appears, classify it before coding:

1. `shared-path bug`
   - Fix immediately.
   - Add or update focused coverage.
2. `artifact quality bug`
   - Fix display, filtering, or formatting logic.
   - Do not widen architecture unless the issue repeats across modules.
3. `provider/data quality issue`
   - Record the evidence.
   - Continue to the next module unless the module explicitly targets provider or corpus quality.
4. `product judgment`
   - Stop and ask Conrad.
5. `future optimization`
   - Record as residual risk.
   - Do not block the current gate.

Limits:

- The same issue can be fixed for at most two consecutive rounds.
- If the third round is still unsatisfactory, convert it to residual risk or a new module.
- Do not modify multiple architecture layers to satisfy one draft test.

## 2.5 Loop V2.1 Maintainability Review Gate

Before closing an important module, check:

- Is there duplicated logic?
- Did the change add hidden global state?
- Did provider-specific logic leak into the core RAG layer?
- Did citation or evidence schema become inconsistent?
- Are there orphan code paths, dead flags, or unused parameters?
- Does a temporary strategy need a decision record or residual-risk entry?

Small issues should be fixed inside the current module.

Architecture-level issues should be recorded as follow-up modules instead of hidden behind passing tests.

## 2.6 Loop V2.1 Artifact Quality Extension

Use these rules when a module produces a user-facing research artifact, especially P2 Trend Brief outputs.

Do not apply the full artifact gate to small helper changes unless they affect artifact content, evidence, or user-facing claims.

### Artifact First Gate

If a module produces a user-facing artifact, inspect the artifact before closing the module.

Acceptable inspection methods:

- script-based structural inspection for required sections, counts, and schema;
- focused human review for readability, claims, and source adequacy;
- both, when the artifact is used as phase-gate evidence.

Tests can prove that the artifact was generated. They do not prove that the artifact is useful.

### Evidence Quality Gate

For `live external` modules, do not treat "has external citation" as sufficient.

The source-quality label must be part of the gate result:

- `research_quality_verified`: artifact has relevant primary or high-quality sources for the key claims;
- `runtime_verified`: artifact runs and cites sources, but source quality is weak, mixed, or insufficient;
- `blocked`: artifact cannot support its core claims safely.

`weak_only` can pass runtime verification, but it cannot pass research-quality verification.

### Artifact Consistency Check

For generated research artifacts, keep these views consistent:

- CLI summary;
- Markdown appendix;
- evidence table.

At module close, citation count and evidence type counts should match across those views, or the mismatch must be recorded as a residual risk.

### Checkpoint Hygiene

For every P2 module checkpoint, include a change inventory:

- code changed;
- docs/specs/plans changed;
- artifacts/evals/evidence generated;
- historical dirty files included in the baseline, if any;
- local-only ignored files that remained excluded.

### Next-Step Bias

Every important loop close must name the next bottleneck:

- product bottleneck: user value, scope, positioning, or judgment is unclear;
- engineering bottleneck: implementation, integration, reliability, or maintainability is limiting progress;
- evidence bottleneck: source quality, citation quality, corpus freshness, or evaluation confidence is limiting progress.

When the bottleneck is evidence quality, do not keep tuning formatting or tests as the main work.

## 3. Definition Of Done Template

Each module must define completion using this shape:

```text
Module: [name]

Product behavior:
- What user-visible or system-visible behavior now exists?

Engineering behavior:
- What functions, endpoints, data paths, or workflows changed?

Evidence behavior:
- What source/date/citation/evidence trail is preserved?

Evaluation behavior:
- What test, sample inspection, or golden question check proves this?

Non-goals:
- What is intentionally not done in this module?

Residual risks:
- What remains known but non-blocking?
```

## 4. Quality Gate Levels

### 4.1 Light Loop

Use for:

- Documentation updates
- Single helper functions
- Small test adjustments
- Narrow bug fixes

Required:

- Explain the change briefly.
- Run the smallest relevant check.
- Record only if it affects roadmap, plan, spec, evidence, or execution history.

### 4.2 Module Loop

Use for:

- Completing a roadmap module
- Changing ingestion, retrieval, citation, agent routing, CI, or API behavior

Required:

- Definition of Done
- Focused tests
- Relevant real corpus or API sample where applicable
- Evidence file
- Execution log
- Reviewer gate if meaningful behavior changed

### 4.3 Phase Loop

Use for:

- Finishing P0, P1, P2, or P3

Required:

- Focused tests from all phase modules
- One end-to-end smoke path where feasible
- Golden question evaluation snapshot
- Residual risk review
- Roadmap update if priorities changed

### 4.4 Verification Budget Ladder

Use the cheapest sufficient verification level:

1. `schema`
   - Use for docs/config/eval asset shape.
   - Examples: `jq`, validation CLI, markdown link checks.

2. `focused`
   - Use for changed module behavior.
   - Examples: one or a few `unittest` modules.

3. `canonical`
   - Use after shared runtime path changes or completed module gates.
   - Example: `pnpm rag:check:p0`.

4. `local structural`
   - Use when real retrieval/runtime wiring matters but external LLM transfer is not required.
   - Example: hybrid retrieval with a local fake agent.

5. `live external`
   - Use only for explicit benchmark gates.
   - May call DeepSeek or search providers.
   - Must save evidence and must not be part of default deterministic checks.

### 4.5 GitHub Checkpoint Gate

Use after:

- completing a roadmap module;
- completing a live-smoke verified artifact;
- making a major architecture, spec, or roadmap update;
- completing a P0/P1/P2 phase gate;
- fixing a key bug that affects a shared path.

Default branch:

```text
codex/rag-transformation-checkpoints
```

Default commit message format:

```text
checkpoint(rag): [module-name] - [status]
```

Required before checkpoint:

- `git status --short`
- `git diff --check`
- the minimum required test from the verification ladder;
- secret scan for known API key or token patterns;
- staged-file review to confirm excluded local artifacts are not committed.

Never commit:

- `.env`
- `.venv/`
- `node_modules/`
- Python cache files
- local database or vector runtime artifacts
- real API keys or tokens

For code changes:

- run focused tests and `py_compile`, or the canonical check when shared RAG paths changed.

For shared RAG path changes:

- run `pnpm rag:check:p0`.

For live modules:

- save live smoke artifact and evidence.

If GitHub push fails:

- record `Checkpoint Blocked` in evidence and execution log;
- do not claim the work is backed up.

## 5. Decision Boundary

### 5.1 Codex Can Decide Independently

Codex can independently decide:

- Small code organization details
- Focused test structure
- Local documentation and evidence structure
- Narrow bug fixes
- Small project-level dependencies when all conditions are true:
  - The dependency is necessary for the current module.
  - The dependency is small and scoped to this project.
  - The source is authoritative or widely trusted.
  - It does not require account setup, secrets, global system changes, or paid services.
  - The reason and verification are recorded.

### 5.2 Conrad Must Decide

Codex must stop and ask Conrad before:

- Installing system-level tools such as Homebrew packages.
- Adding large frameworks or changing architecture direction.
- Introducing external services, accounts, tokens, or paid APIs.
- Changing product positioning or roadmap priority.
- Introducing LangChain, LangGraph, or similar framework-level dependencies.
- Deploying services or configuring production secrets.
- Changing the original AI Trend Radar UI.
- Promoting draft golden questions into official product-quality gates.

### 5.3 Original AI Trend Radar UI Boundary

The original AI Trend Radar UI is out of scope until the AI Trend Radar RAG project has completed its core RAG work.

Do not fix or redesign the original UI Agent entry during P0.

The original UI should be revisited only after:

- Fresh corpus sync works.
- Ingestion is citation-ready.
- `/chat` returns grounded citations.
- Golden question evaluation exists.
- Web search/tool boundary is defined.
- GitHub Actions are stable enough for the RAG project.

## 6. Evaluation Set Policy

The evaluation set is a product asset, not just test code.

`docs/rag-transformation/evals/golden-questions.md` should evolve into a repeatable evaluation asset. Each golden question should eventually include:

- Question
- Intent
- Answerability: `internal-only`, `needs-web`, or `insufficient`
- Required evidence
- Citation requirement
- Good answer criteria
- Bad answer patterns
- Current status
- Last evaluated date

Codex can propose evaluation labels, but Conrad should decide when product judgment is required, especially for what counts as a good answer.

Draft evaluation questions must keep `needs_conrad_review: true`.

Codex may use draft questions to find obvious shared-path bugs, but should not keep tuning architecture to satisfy draft questions without first classifying whether the failure is a product issue, a local bug, or a future optimization.

## 7. Residual Risk Policy

Do not hide unresolved problems.

For each non-blocking issue, record:

- Risk
- Why it does not block the current module
- When it should be revisited
- Suggested priority: P0, P1, P2, or P3

Blocking issues must be fixed before continuing.

## 8. Current Loop Position

As of 2026-06-24:

- Completed: P0 baseline through fresh corpus sync, citation-ready ingestion, chat citations, golden question evaluation, and web-search tool boundary.
- Completed: P1 slices through query understanding, hybrid retrieval slice 1, runtime readiness, live answer benchmark, agent control, tool routing, provider routing, Tavily live provider, source-quality controls, external evidence merge into chat, external evidence answer quality benchmark, URL fetch/source-deepening foundation, deep fetch integration policy, live Brave/Exa/GitHub provider adapters, minimal source role handling, graph citation-ready retrieval, live Neo4j hybrid runtime verification, provider quality matrix, claim-level evaluation seed, retrieval precision benchmark seed, and deterministic citation dedup/noise filtering.
- Completed: P1 multi-hop graph relationship seed and deterministic graph question planner with service-layer graph evidence retrieval.
- Completed: P1 seed-level semantic contradiction detection for selected high-risk answer patterns.
- Completed: P1 evaluation set expansion draft from 5 to 12 golden questions.
- Completed: Loop V2 governance update and local-only 12-question structural benchmark.
- Completed: P1 product architecture and quality strategy review.
- Completed: P2 Trend Brief Workflow MVP Spec.
- Completed: P2 Trend Brief Workflow MVP Implementation.
- Completed: P2 Trend Brief Product Review And Live External Mode.
- Completed: Loop V2.1 Governance And Baseline Checkpoint.
- Completed: Loop V2.1 Artifact Quality Extension.
- Next: P2 Trend Brief External Source Quality Upgrade.
- Still needed: DeepSeek live validation when environment permits it, broader semantic contradiction coverage, semantic reranking, richer graph question coverage, and original UI integration after the RAG core matures.

## 9. Current Gate Definition

Current gate: P2 Trend Brief External Source Quality Upgrade.

This gate is complete when:

- the generated trend brief improves from `weak_only` external evidence toward primary or high-quality supporting sources;
- CLI summary, Markdown appendix, and evidence table have consistent citation and evidence-type counts, or any mismatch is recorded as residual risk;
- source-quality status distinguishes `runtime_verified` from `research_quality_verified`;
- the module checkpoint includes a change inventory;
- the next bottleneck is explicitly classified as product, engineering, or evidence.

## 10. How To Update This Spec

After each completed module:

- update the current loop position;
- replace the current gate definition;
- keep historical module details in evidence and execution-log files rather than leaving stale gate text here;
- if a new architectural or component-selection principle is discovered, update the quality governance spec or add a decision record.
