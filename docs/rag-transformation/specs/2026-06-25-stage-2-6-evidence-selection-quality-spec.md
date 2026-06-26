# Stage 2.6: Evidence Selection Quality Spec

**Date:** 2026-06-25

## Purpose

This stage improves evidence quality after real local Agent usage reveals which retrieval and ranking problems matter. Rather than tuning evidence quality in isolation, this stage addresses it after the product flow and Agent surface expose real usage failures.

## Product Position

The evidence selection should feel intelligent and trustworthy:
- Citations should be relevant to the query
- Sources should be diverse and high-quality
- Time-sensitive questions should be handled correctly
- Duplicate or conflicting evidence should be managed

What it should **not** be:
- A black box that returns irrelevant citations
- A system that over-relies on single sources
- A system that ignores temporal context
- A system that returns duplicate or conflicting evidence

## User Jobs

### 1. Relevant Citations
Citations should be directly relevant to the user's query, not tangentially related.

### 2. Diverse Sources
Citation sets should include evidence from multiple sources when available, not just one provider.

### 3. High-Quality Sources
Official, primary, paper, repository, and high-signal technical sources should be prioritized.

### 4. Temporal Awareness
Time-sensitive questions like "recent" or "past week" should retrieve evidence from the correct period.

### 5. Clean Evidence
Duplicate or conflicting evidence should be managed, not presented as-is.

## Scope Boundary

**In scope:**
- Reranking strategy
- Source quality weighting
- Evidence diversity
- Freshness and temporal logic
- Evaluation refresh

**Out of scope:**
- New retrieval algorithms
- Agent ability improvements (Stage 2.5)
- Unified workspace (Stage 2.7)
- Production deployment

## Architecture

### Layers Affected
- **Retrieval Layer**: Enhanced with reranking and diversity
- **Evidence Layer**: Enhanced with quality weighting and deduplication
- **Evaluation Layer**: Refreshed with real failures

### Data Flow
```
User Query
    ↓
Retrieval (vector + graph)
    ↓
Reranking (deterministic / embedding / LLM)
    ↓
Source Quality Weighting
    ↓
Evidence Diversity Check
    ↓
Freshness Filter
    ↓
Deduplication
    ↓
Clean Citations
```

## Modules

### Module 1: Reranking Strategy

**Goal**: Compare lightweight deterministic scoring, embedding similarity, and optional LLM reranking.

**Requirements**:
- [ ] Implement deterministic scoring
- [ ] Implement embedding similarity
- [ ] Implement optional LLM reranking
- [ ] Measure retrieval precision improvement
- [ ] Control latency

**Approach**:
1. **Deterministic scoring**: Score based on metadata (date, source, relevance)
2. **Embedding similarity**: Use embeddings to measure query-citation similarity
3. **LLM reranking**: Use LLM to rerank citations (optional, expensive)

**Verification**:
- [ ] Precision improvement on golden set
- [ ] Latency within bounds
- [ ] No regression on existing tests

### Module 2: Source Quality Weighting

**Goal**: Prioritize official, primary, paper, repository, and high-signal technical sources.

**Requirements**:
- [ ] Define source quality tiers
- [ ] Implement quality weighting
- [ ] Verify weak-only evidence cannot pass as research-quality

**Source Quality Tiers**:
| Tier | Sources | Weight |
|------|---------|--------|
| 1 - Official | Official docs, announcements | 1.0 |
| 2 - Primary | Papers, repositories | 0.8 |
| 3 - High-signal | Technical blogs, analysis | 0.6 |
| 4 - Secondary | News, social media | 0.4 |
| 5 - Weak | Unverified, low-quality | 0.2 |

**Verification**:
- [ ] Quality weighting applied
- [ ] Weak-only evidence rejected
- [ ] No regression on existing tests

### Module 3: Evidence Diversity

**Goal**: Prevent over-concentration of citations from a single provider or near-duplicate sources.

**Requirements**:
- [ ] Detect single-provider concentration
- [ ] Detect near-duplicate sources
- [ ] Ensure diverse citation sets

**Approach**:
1. Count citations per provider
2. Detect near-duplicates (same title/source)
3. Ensure minimum diversity (e.g., 2+ providers)

**Verification**:
- [ ] Diversity check applied
- [ ] No single-provider dominance
- [ ] No regression on existing tests

### Module 4: Freshness and Temporal Logic

**Goal**: Handle time-sensitive questions explicitly.

**Requirements**:
- [ ] Detect time-sensitive queries
- [ ] Retrieve evidence from correct period
- [ ] Honestly state insufficiency when needed

**Time-Sensitive Patterns**:
- "recent", "最近", "新动向"
- "past week", "过去一周"
- "latest", "最新"

**Verification**:
- [ ] Time-sensitive queries detected
- [ ] Correct period retrieved
- [ ] Insufficiency stated when needed

### Module 5: Evaluation Refresh

**Goal**: Incorporate real failures from Stage 2.4 and Stage 2.5 into evaluation set.

**Requirements**:
- [ ] Identify real failures
- [ ] Add to evaluation set
- [ ] Verify no regressions

**Verification**:
- [ ] Real failures added
- [ ] No regressions
- [ ] Evaluation set improved

## Implementation Plan

### Phase 1: Reranking Strategy (Module 1)
- Implement deterministic scoring
- Test precision improvement
- Control latency

### Phase 2: Source Quality Weighting (Module 2)
- Define quality tiers
- Implement weighting
- Verify weak evidence rejection

### Phase 3: Evidence Diversity (Module 3)
- Implement diversity check
- Test diversity improvement
- Verify no regressions

### Phase 4: Freshness Logic (Module 4)
- Implement time-sensitive detection
- Implement freshness filtering
- Test temporal queries

### Phase 5: Evaluation Refresh (Module 5)
- Identify real failures
- Add to evaluation set
- Run full evaluation

## Testing Strategy

### Unit Tests
- [ ] Reranking scoring
- [ ] Quality weighting
- [ ] Diversity check
- [ ] Freshness filtering
- [ ] Evaluation set

### Integration Tests
- [ ] End-to-end retrieval
- [ ] Citation quality
- [ ] Diversity improvement
- [ ] Temporal handling

### End-to-End Tests
- [ ] Complete research workflow
- [ ] All query types
- [ ] All evidence scenarios

## Definition of Done

### Product Behavior
- [ ] Citations are relevant
- [ ] Sources are diverse
- [ ] Quality is weighted
- [ ] Temporal queries work
- [ ] Evaluation is refreshed

### Engineering Behavior
- [ ] No new dependencies
- [ ] Backward compatible
- [ ] All tests pass
- [ ] Code follows project patterns

### Evidence Behavior
- [ ] Unit tests pass
- [ ] Integration tests pass
- [ ] Execution log recorded

## Residual Risks

1. **Reranking latency**: LLM reranking may be too slow
2. **Quality weighting**: May be too aggressive
3. **Diversity enforcement**: May reduce relevance
4. **Temporal logic**: May miss edge cases
5. **Evaluation overfitting**: May over-optimize for evaluation set

## Success Metrics

| Metric | Target | Measurement |
|--------|--------|-------------|
| Citation relevance | >80% | Golden set precision |
| Source diversity | >2+ providers | Citation set analysis |
| Quality weighting | 100% | Weak evidence rejected |
| Temporal accuracy | >90% | Time-sensitive query accuracy |
| Evaluation coverage | 100% | Real failures added |

---

## Update Log

| Date | Version | Changes |
|------|---------|---------|
| 2026-06-25 | v1.0 | Initial version |
