# Decision 0008: Loop V2.2 Strategic Review And Stage Cadence

Date: 2026-06-25

Status: Accepted

## Context

Loop V2.1 improved evidence quality, checkpoint hygiene, and maintainability checks. During P2 Trend Brief work, the loop also exposed two execution problems:

- too much attention drifted into evidence/citation refinement while product function, architecture, and user workflow iteration received less attention;
- documentation updates and checkpoint metadata became too frequent, slowing engineering throughput.

Conrad clarified that direction decisions should not be accepted just because he suggested them. Major direction, roadmap, architecture, Agent capability, testing depth, dependency, and deployment decisions must be reviewed critically from product, architecture, and engineering perspectives.

## Decision

Adopt Loop V2.2 for AI Trend Radar RAG.

Loop V2.2 keeps the quality controls from V2.1 but adds:

1. Strategic Direction Review Gate
2. Mainline Balance Rule
3. Stage-Level Documentation Cadence
4. Longer Checkpoint Interval
5. External API Budget Clarification

## Strategic Direction Review Gate

Before accepting a major direction change, Codex must treat the idea as a hypothesis and review it through three lenses:

- senior AI product manager;
- senior AI product architect;
- senior full-stack engineer.

The review must answer:

- what real problem this solves now;
- whether it is the highest-leverage current bottleneck;
- whether a simpler or more reversible path exists;
- engineering, time, maintenance, and API cost;
- concrete product capability gained;
- what should remain deferred.

Codex should push back when a proposal is premature, over-scoped, or mostly makes the project look more sophisticated without improving the current product path.

## Mainline Balance Rule

Evidence, tests, and benchmarks are quality controls. They should not silently become the main product work.

At each stage boundary, identify one primary bottleneck:

- product function;
- architecture;
- engineering;
- evidence;
- evaluation.

If two consecutive modules are evidence/evaluation-heavy, the next stage must re-check whether product function or architecture should become the priority.

## Documentation And Checkpoint Cadence

Documentation and checkpointing should support execution, not interrupt it.

Default cadence:

- update roadmap/spec/evidence/execution-log at stage close;
- checkpoint after completed stages, major shared-path changes, or major product/architecture decisions;
- do not create metadata-only commits solely to record push status;
- use concise conversation updates during implementation;
- save raw evidence artifacts only when useful for benchmark, comparison, or product review.

Exceptions:

- secrets or deployment risk;
- destructive migration risk;
- live external artifact needed as audit evidence;
- user explicitly asks for immediate recording.

## External API Budget Clarification

When external search or DeepSeek budget is available, the scarce resource is often Codex token/context and development loop time, not external API calls.

For testing and exploration, prefer batched provider calls and larger result pools when they reduce repeated small searches or repeated model reasoning.

For production or Agent response paths, keep provider routing and result limits bounded for latency, noise, and maintainability.

## Consequences

Positive:

- Product and architecture work will not be crowded out by evidence polishing.
- Direction changes receive explicit tradeoff review.
- Fewer doc/checkpoint interruptions should improve execution speed.
- Evidence quality work remains available but is put back into the quality-control layer.

Trade-offs:

- Some intermediate details will be recorded later rather than immediately.
- Checkpoints are less granular.
- Conrad may see fewer small documentation updates during implementation.
