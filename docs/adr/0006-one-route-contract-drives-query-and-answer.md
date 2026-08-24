# One route contract drives query preparation and answer generation

The system will classify a request once into a versioned Route Contract after extracting non-destructive Intent Signals. Query rewriting, retrieval-channel selection, GraphRAG use, evidence ranking, Prompt Package compilation, structured Answer Envelope validation, and final rendering must consume that same contract; the browser submits and displays the original query but does not own a separate routing or rewrite implementation.

## Consequences

- The input-side rewrite policy and output-side prompt/output contracts cannot silently choose different task families.
- Five task routes share infrastructure and domain identities rather than becoming five copied pipelines.
- Exact ATR navigation remains deterministic and bypasses answer generation; complex or ambiguous requests may use one bounded routing-model call.
- Route A uses a versioned deterministic answer builder contract instead of a prompt contract, and an accepted navigation match enters the Evidence Ledger before the NavigationAnswer is built.
- JSON is an internal validated contract, while Markdown and UI are deterministic projections for users.
- Retrieved candidates become citable Evidence Records only after deduplication, reranking, tier assignment, and evidence admission.
- Trend Discovery owns “what recently happened or deserves attention”; Temporal Relation Exploration owns “how it evolved or relates across time or entities.” The word “trend” alone does not select the latter.
