# P2 Trend Brief Live External Mode Plan

## Module

P2 Trend Brief Live External Mode

## Product Decision

The generated local-only RAG brief is structurally useful, but its main weakness is missing external primary evidence.

Therefore the next improvement should be a live external evidence mode, not LLM-assisted prose polishing.

## Definition Of Done

Product behavior:
- Default generation remains `local-only`.
- A user can explicitly run `--mode live-external`.
- Live mode adds external citations and source review to the Markdown brief.
- The brief still distinguishes internal, graph, and external evidence.

Engineering behavior:
- Reuse existing provider routing and `SearchProviderRegistry`.
- Do not add new dependencies.
- Do not call external providers unless `--mode live-external` is set.
- Keep provider calls bounded by existing route budget policy.

Evidence behavior:
- Focused tests prove local-only creates no external requests.
- Focused tests prove live-external creates provider-routed requests.
- P0 check includes the new path.
- Live smoke should be run only when local service / network execution is permitted.

Non-goals:
- No LLM-assisted summary in this module.
- No UI.
- No deep fetch by default.
- No claim of complete external coverage.

Residual risks:
- External providers may return generic or weak citations.
- Live smoke is required before claiming runtime behavior.
