# Relevance tiers precede within-tier ranking

For every request, the system will first assign Evidence Candidates to Primary, Supplementary, Background, Unverified, or Excluded tiers according to the current Query Frame. Only after that eligibility decision will it rank candidates inside each tier by Dynamic Importance, Query-relative Freshness, and Evidence Quality; it will not persist or depend on a global `important_news` label because the same observation can be primary for one task and merely supplementary or background for another.

## Consequences

- Stable corpus facts remain reusable, while importance and display role are calculated per request.
- A fresh but irrelevant item cannot outrank a directly relevant item by accumulating recency or popularity points.
- Primary, supplementary, and background evidence retain separate identities in evaluation and UI output instead of being flattened into one list.
- Existing fixed important-news gates and scores become migration targets, not compatibility contracts for new work.
