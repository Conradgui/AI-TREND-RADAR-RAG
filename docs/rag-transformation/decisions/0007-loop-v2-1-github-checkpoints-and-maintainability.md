# Decision 0007: Loop V2.1 GitHub Checkpoints And Maintainability Gates

Date: 2026-06-24

Status: Accepted

## Context

The project has accumulated many uncommitted changes across RAG runtime, evaluation, documentation, and evidence artifacts.

Loop V2 improved efficiency by preferring script-first evidence collection and by preventing draft tests from automatically forcing architecture work. It still had three gaps:

- important module completions were not automatically backed up to GitHub;
- repeated test or benchmark adjustments could pull work into local optimization loops;
- architecture, interface, data-boundary, and long-term maintainability checks were not explicit enough before coding.

## Decision

Adopt Loop V2.1 as the operating loop for AI Trend Radar RAG.

Loop V2.1 adds:

1. GitHub Checkpoint Gate
2. Architecture Boundary Gate
3. Anti-Rabbit-Hole Rule
4. Maintainability Review Gate

This rule applies only to the AI Trend Radar RAG project. It does not apply to the original AI Trend Radar UI project until that project is intentionally brought into scope.

## GitHub Checkpoint Gate

Checkpoint branch:

```text
codex/rag-transformation-checkpoints
```

Commit message format:

```text
checkpoint(rag): [module-name] - [status]
```

Checkpoint is required after:

- completing a roadmap module;
- completing a live-smoke verified artifact;
- making a major architecture, spec, or roadmap update;
- completing a P0/P1/P2 phase gate;
- fixing a key bug that affects a shared path.

Before checkpoint:

- run the minimum required verification for the change risk;
- run secret scan;
- review staged files;
- update evidence and execution log;
- confirm local-only artifacts and secrets are excluded.

Never commit:

- `.env`
- `.venv/`
- `node_modules/`
- Python cache files
- local database or vector runtime artifacts
- real API keys or tokens

If push fails, record `Checkpoint Blocked` and do not claim the work has been backed up.

## Architecture Boundary Gate

Before important code changes, answer:

1. Which layer owns the change?
2. What are the inputs and outputs?
3. Does this create a new data or evidence boundary?
4. Is this reused or newly created module logic?
5. Does it make future UI, Stage 2.5, or local app integration harder?
6. Is an official or authoritative component preferable to custom infrastructure?

If the answer reveals an architecture shift, stop for Conrad's decision.

## Anti-Rabbit-Hole Rule

Classify failures before fixing:

- `shared-path bug`: fix now with focused coverage;
- `artifact quality bug`: fix display, filtering, or formatting logic;
- `provider/data quality issue`: record evidence and do not tune indefinitely;
- `product judgment`: stop for Conrad;
- `future optimization`: record as residual risk.

The same issue can be fixed for at most two consecutive rounds.

If the third round is still unsatisfactory, convert it to residual risk or a new module.

## Maintainability Review Gate

Before closing important modules, check:

- duplicated logic;
- hidden global state;
- provider-specific logic leaking into core RAG;
- inconsistent citation or evidence schema;
- orphan code, dead flags, or unused parameters;
- temporary strategy that needs a decision or residual-risk record.

## Consequences

Positive:

- Important progress is backed up outside the local machine.
- Future reviews can inspect branch history, evidence, and execution logs together.
- The loop has explicit controls against local benchmark overfitting.
- Code changes are judged against long-term module boundaries, not only passing tests.

Trade-offs:

- Important nodes now include commit and push overhead.
- Some work will stop earlier for product or architecture decisions.
- Baseline checkpoint is intentionally broad because the worktree already contains many accumulated changes.
