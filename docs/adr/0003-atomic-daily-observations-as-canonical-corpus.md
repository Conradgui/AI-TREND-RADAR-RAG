# Use atomic daily observations as the canonical retrieval corpus

Daily reports remain human-readable views, but retrieval, citation, navigation, and GraphRAG will consume structured Daily Signal Observations instead of re-chunking rendered Markdown. Each admitted observation receives one immutable public Daily Item ID (`ATR-YYYYMMDD-XXXXXX`), while an internal content identity links repeated or materially changed observations across dates; this removes duplicate report/item indexing without sacrificing longitudinal trend analysis.

## Consequences

- Markdown daily, weekly, and monthly reports are browse-only projections and are not primary vector documents.
- A rerun preserves existing Daily Item IDs; a later Material Signal Change may create a new dated observation linked to the same underlying content.
- Historical items are backfilled only after a one-day shadow migration passes identity, retrieval, citation, and deep-link gates.
- Legacy IDs remain read-only aliases, while every new public output uses the Daily Item ID.
