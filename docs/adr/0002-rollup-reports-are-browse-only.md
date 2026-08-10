# Keep weekly and monthly rollups out of retrieval

Weekly and monthly reports are derived selections and trend summaries built from daily reports, so users should be able to browse them but the RAG pipeline must not vectorize or graph-index them. Daily `ai-topic-radar` reports remain the report-level retrieval corpus; this avoids overweighting the same facts through repeated daily, weekly, and monthly summaries while GraphRAG derives cross-day trends from linked daily evidence.

## Consequences

- Corpus sync may download rollup reports for browsing, but ingestion must filter them out by report type.
- Answers may cite daily evidence and derive trends through graph relationships; rollups are not independent supporting evidence.
- If rollup retrieval is reconsidered later, it requires an explicit weighting and duplicate-evidence evaluation rather than simply adding the files to the index.
