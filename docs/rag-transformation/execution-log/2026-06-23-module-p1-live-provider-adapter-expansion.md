# Execution Log: P1 Live Provider Adapter Expansion

Date: 2026-06-23

## Goal

Expand external search from a single live Tavily adapter to a provider-routed system with Brave, Exa, and GitHub live adapters.

## Work Completed

1. Added `BraveSearchProviderAdapter`.
2. Added `ExaSearchProviderAdapter`.
3. Added `GitHubSearchProviderAdapter`.
4. Updated `SearchProviderRegistry` to instantiate configured live adapters.
5. Added provider-specific normalization into external citation schema.
6. Added deterministic unit tests for all new adapters and registry selection.
7. Added consolidated live provider smoke script.
8. Re-ran OKF/ALM chat-level smoke to validate provider fallback plus deep fetch.

## Results

Deterministic verification:

- `python3 -m unittest rag.tests.test_search_provider_adapters rag.tests.test_eval_search_provider_adapters -v`: 13 tests passed.
- `pnpm rag:check:p0`: 122 tests passed.

Live verification:

- Brave: available, returned citation.
- Exa: available, returned citation.
- GitHub: available, returned citation.
- Provider live smoke errors: none.

End-to-end smoke:

- Tavily returned zero citations for OKF/ALM.
- Brave fallback returned two citations.
- Answer policy upgraded to `internal_and_external_grounded`.
- Deep fetch selected two URLs; one succeeded and one failed.

## Quality Gate Decision

Status:

- Brave adapter: `Live Smoke Verified`.
- Exa adapter: `Live Smoke Verified`.
- GitHub adapter: `Live Smoke Verified`.
- Provider fallback: `Live Smoke Verified`.
- Source conflict handling: `Not Claimed`.

## Next Module

P1 Source Conflict Handling.

Reason:

Now that multiple providers can return evidence, the next product risk is not API connectivity. The next risk is answer quality when sources disagree, when official sources and secondary sources provide different levels of confidence, or when only weak sources mention a claim.
