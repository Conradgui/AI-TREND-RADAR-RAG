# Decision 0002: Web Search Tool Boundary

## Status

Accepted for P0 boundary definition.

## Context

AI Trend Radar RAG should not become a generic chatbot with web search. The product value comes from a grounded AI Trend Radar corpus first, then carefully labeled external freshness and gap filling.

Some golden questions exceed the internal corpus:

- RAG academic evolution and papers.
- Google OKF and ALM Wiki comparison.
- Latest official product confirmation.

These should not be answered by fabrication. They should either return evidence-insufficient or, in a future phase, use clearly labeled external search.

## Decision

Do not implement web search in P0.

Define the future tool boundary now:

### `search_corpus`

Searches the internal AI Trend Radar RAG corpus.

Evidence type:

- `internal`

Allowed sources:

- synced AI Trend Radar reports
- topic-pool candidates
- future internal knowledge artifacts

Required citation fields:

- `date`
- `source`
- `title`
- `citation_id`
- `excerpt`

### `web_search`

Discovers external sources when internal evidence is insufficient or when a golden question is explicitly marked `needs-web`.

Evidence type:

- `external`

Allowed use:

- after internal search
- when question requires official, academic, or latest public evidence
- when answer must state that external evidence is being used

Not allowed:

- replacing internal corpus search by default
- mixing external claims with internal claims without labels
- using web snippets as proof when primary sources are available

### `fetch_url`

Fetches a specific external URL selected by `web_search` or supplied by the user.

Evidence type:

- `external`

Allowed use:

- source verification
- official docs or primary-source reading
- article or paper extraction when needed for a cited answer

Not allowed:

- unbounded browsing
- fetching unknown pages without a user or tool-selected reason

### `compare_internal_and_external`

Compares internal corpus evidence with external evidence.

Purpose:

- show what AI Trend Radar already captured
- show what external search adds
- detect outdated or missing internal coverage
- avoid presenting external facts as internal Radar evidence

Output must separate:

- internal findings
- external findings
- conflicts or gaps
- confidence and remaining uncertainty

## Citation Rules

Internal citations must be labeled as internal corpus evidence.

External citations must be labeled as external evidence and should include:

- source name
- page or document title
- URL
- retrieval or publication date when available
- excerpt

When evidence is insufficient:

- say evidence is insufficient
- do not infer missing relationships
- recommend the next retrieval action

## Product Implication

This keeps AI Trend Radar RAG positioned as a grounded research cockpit rather than a generic search chatbot.

## Engineering Implication

Future web search should be implemented as a separate tool path with its own citations, logs, failure modes, and evaluation labels.

## Evaluation Implication

Golden questions marked `needs-web` should not be judged as P0 internal failures if they correctly report internal evidence insufficiency.

Future benchmark modes should separate:

- P0 internal-only benchmark
- internal-first with external search benchmark
- full research workflow benchmark
