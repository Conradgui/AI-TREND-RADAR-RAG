# Decision 0006: Loop V2 And Benchmark Boundary

Date: 2026-06-24

## Decision

Adopt Execution Loop V2.

The loop must balance product judgment, engineering quality, and token/runtime cost.

## Accepted User Decisions

1. Keep Q6-Q12 as draft golden questions.
   - They are useful as a coverage map.
   - They are not final product truth labels until Conrad reviews them.

2. DeepSeek live benchmark is allowed.
   - Conrad accepts that live LLM benchmark may send retrieved local evidence snippets and questions to DeepSeek.
   - This benchmark remains an explicit live gate, not a default deterministic check.

3. Next-stage work should return to product architecture and quality strategy.
   - Do not overfit development around a draft test set.

4. Keep the local-only structural benchmark.
   - It is the safer default for verifying retrieval, citation, policy, and routing without external LLM data transfer.

5. Development dependencies may be installed automatically when needed.
   - Prefer project-local dependencies.
   - Prefer official or widely trusted sources.
   - Avoid unnecessary global/system installation.
   - Record the reason and verification result when a dependency is added.
   - Neo4j is currently satisfied through the project's Docker Compose runtime; no extra Neo4j installation is needed unless that path fails.

## Loop V2 Rules

### Product Before Test

Draft tests should map coverage and reveal risks.

Draft tests must not automatically become architecture requirements.

If a draft test exposes a defect, Codex should classify it before coding:

- `clear shared-path bug`: fix with focused tests;
- `product judgment`: stop and ask Conrad;
- `nice-to-have refinement`: record as residual risk;
- `architecture shift`: stop and ask Conrad.

### Token And Runtime Budget

Use scripts before model reading whenever possible.

Preferred evidence tools:

- `rg` for locating text and files;
- `jq` for JSON summaries;
- `awk` or small Python scripts for counts and tabular summaries;
- focused unit tests for local behavior;
- canonical checks only at module gates;
- live API benchmarks only as explicit gates.

Use model reasoning for:

- product judgment;
- architecture tradeoffs;
- ambiguous failure classification;
- roadmap and priority decisions;
- summarizing evidence into user-facing guidance.

### Verification Budget

Use this verification ladder:

1. `schema`: docs/config/eval asset shape only.
2. `focused`: changed module tests only.
3. `canonical`: shared runtime path or completed module gate.
4. `local structural`: real local retrieval/runtime without external LLM.
5. `live external`: DeepSeek/search-provider calls; explicit evidence snapshot only.

Do not run canonical checks after every small draft edit.

Do not run live external checks as part of normal local development.

### Review Gate

Each module must end with:

- what changed;
- what was verified;
- what was not claimed;
- what Conrad must still decide;
- next recommended module.

## Consequences

This reduces token spend and avoids test-set overfitting.

It also makes benchmark evidence clearer:

- local deterministic checks prove structure;
- local structural checks prove retrieval/runtime wiring;
- live DeepSeek checks sample answer quality with accepted external-data-transfer risk.

## Current Runtime Note

The Codex execution environment rejected the 12-question DeepSeek live benchmark despite Conrad's explicit approval.

Therefore:

- local structural benchmark is the completed evidence path for this environment;
- DeepSeek live benchmark remains approved by Conrad but blocked by execution policy here;
- do not attempt to bypass the policy through indirect execution.
