---
status: accepted
---

# Keep answers traceable to request-scoped evidence

Final citations must come only from evidence actually returned by tools and admitted to the current request's Evidence Ledger. We chose this over a fixed pre-retrieval citation pool or post-hoc similarity matching because Agent tools may discover different evidence during reasoning, and future automated ingestion will make inferred citation matching increasingly unreliable.

## Considered Options

- Fixed pre-retrieval citations: simpler, but prevents dynamic Agent tools from becoming authoritative evidence sources.
- Post-hoc similarity filtering: cheaper, but cannot prove that a displayed citation supported the generated claim.
- Request-scoped Evidence Ledger: more engineering work, but keeps tool use, claims, and citations auditable as the system evolves.

## Consequences

Core factual and analytical claims must bind to Evidence Records, while headings, transitions, and explicitly labelled suggestions are exempt. Claims without traceable support must be removed, weakened, or explicitly marked as unsupported rather than paired with a merely similar citation.

The ledger's storage shape, tool eligibility rules, validation method, repair behavior, and UI representation are implementation strategies. They are deliberately kept in versioned delivery plans so they can evolve with retrieval quality, Agent capabilities, daily ingestion, and user feedback without reopening this product principle.
