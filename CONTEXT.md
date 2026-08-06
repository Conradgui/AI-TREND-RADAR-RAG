# AI Trend Radar RAG

This context describes how the product turns retrieved trend material into grounded, auditable answers.

## Language

**Evidence Ledger（证据账本）**:
The request-scoped set of evidence actually returned by tools and eligible to support the final answer. Evidence outside the ledger cannot be presented as a citation for that answer.
_Avoid_: Citation pool, candidate references, retrieved results

**Evidence Record（证据记录）**:
A uniquely identifiable item in the Evidence Ledger that contains enough provenance for a user to inspect its origin and supported content.
_Avoid_: Source item, search hit, chunk

**Displayed Citation（展示引用）**:
A user-facing link or label derived from an Evidence Record that the final answer explicitly uses.
_Avoid_: Suggested source, related reading

**Grounded Claim（有据结论）**:
A claim in the final answer that is supported by at least one identified Evidence Record from the current request's Evidence Ledger.
_Avoid_: Model conclusion, likely fact

**Claim Citation（结论引用）**:
The binding from one core factual or analytical claim to one or more Evidence Record IDs. Headings, transitions, and explicitly labelled suggestions do not require Claim Citations.
_Avoid_: Answer-level sources, sentence-by-sentence footnotes
