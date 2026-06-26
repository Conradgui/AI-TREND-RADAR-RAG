# Stage 2.5: Agent Ability Closure Spec

**Date:** 2026-06-25

## Purpose

This stage makes the Agent practically useful inside the local cockpit. After Stage 2.4 proves the local product flow works, the next bottleneck becomes Agent usefulness — how well it handles real research tasks.

## Product Position

The Agent should feel like a knowledgeable research assistant that:
- Understands context from the current report
- Chooses appropriate retrieval strategies
- Explains its reasoning and tool usage
- Handles failures gracefully
- Stays within cost/latency bounds

What it should **not** be:
- A generic chatbot without context
- A black box that hides its reasoning
- An expensive tool that makes unnecessary calls
- A system that crashes on errors

## User Jobs

### 1. Context-Aware Research
When viewing a report, the Agent should understand the current context (report, date, topic) and leverage it when answering follow-up questions.

### 2. Transparent Reasoning
Users should see how the Agent arrived at its answer — whether it used internal retrieval, graph evidence, web search, or deep fetch.

### 3. Task-Specific Modes
Different research tasks need different approaches:
- **Explain**: Break down complex topics
- **Compare**: Analyze multiple items
- **Timeline**: Track evolution over time
- **Brief follow-up**: Deep dive into brief topics
- **Source check**: Verify claims and sources

### 4. Graceful Failure
When evidence is insufficient, providers fail, or corpus is stale, the Agent should clearly communicate limitations and provide bounded answers.

### 5. Cost Efficiency
Simple queries should be cheap; complex ones should stay bounded with visible tool budgets.

## Scope Boundary

**In scope:**
- Context-aware Agent entry
- Tool trace presentation
- Agent task modes
- Failure and uncertainty behavior
- Cost and latency guardrails

**Out of scope:**
- New retrieval algorithms (Stage 2.6)
- Evidence selection quality (Stage 2.6)
- Unified workspace (Stage 2.7)
- Production deployment

## Architecture

### Layers Affected
- **Agent Layer**: Enhanced with context, modes, and guardrails
- **Retrieval Layer**: Used by Agent for evidence gathering
- **Evidence Layer**: Provides citation and source information
- **Runtime Layer**: Controls cost and latency

### Data Flow
```
User Query + Context
    ↓
Agent Entry (context-aware)
    ↓
Task Mode Selection
    ↓
Tool Execution (with traces)
    ↓
Evidence Gathering
    ↓
Answer Generation (with uncertainty)
    ↓
Response with Traces
```

## Modules

### Module 1: Context-Aware Agent Entry

**Goal**: Agent receives current report, date, and topic context from the dashboard.

**Requirements**:
- [ ] Pass report context to Agent
- [ ] Pass date context to Agent
- [ ] Pass topic context to Agent
- [ ] Use context when answering follow-ups

**API Changes**:
```python
class ChatRequest(BaseModel):
    message: str = Field(..., max_length=2000)
    history: list[dict] = Field(default_factory=list)
    context: dict = Field(default_factory=dict)  # NEW: report, date, topic
```

**Verification**:
- [ ] Agent receives context
- [ ] Agent uses context in answers
- [ ] Context is optional (backward compatible)

### Module 2: Tool Trace Presentation

**Goal**: Display compact tool decisions so users can see how answers were generated.

**Requirements**:
- [ ] Track tool usage (internal retrieval, graph, web search, deep fetch)
- [ ] Generate compact trace summary
- [ ] Display trace in response
- [ ] Don't expose raw logs

**Response Format**:
```json
{
  "answer": "...",
  "citations": [...],
  "query_understanding": {...},
  "tool_trace": {
    "tools_used": ["search_corpus", "graph_query"],
    "evidence_sources": ["internal", "graph"],
    "total_calls": 2,
    "summary": "基于内部语料和图谱证据回答"
  }
}
```

**Verification**:
- [ ] Trace is generated
- [ ] Trace is compact
- [ ] Trace is displayed in UI

### Module 3: Agent Task Modes

**Goal**: Support different modes for different research tasks.

**Requirements**:
- [ ] Detect task mode from query
- [ ] Adjust retrieval/tool strategy per mode
- [ ] Support modes: explain, compare, timeline, brief_followup, source_check

**Mode Detection**:
```python
def detect_task_mode(query: str, context: dict) -> str:
    # explain: "解释...", "什么是..."
    # compare: "对比...", "A和B的区别"
    # timeline: "演进...", "发展历程"
    # brief_followup: "关于...的brief"
    # source_check: "验证...", "来源是..."
    # default: "general"
```

**Verification**:
- [ ] Mode is detected
- [ ] Strategy adjusts per mode
- [ ] All modes work

### Module 4: Failure and Uncertainty Behavior

**Goal**: Clearly surface insufficient evidence, provider failures, or stale corpus.

**Requirements**:
- [ ] Detect insufficient evidence
- [ ] Detect provider failures
- [ ] Detect stale corpus
- [ ] Return bounded answers
- [ ] Clear communication of limitations

**Failure Scenarios**:
| Scenario | Detection | Response |
|----------|-----------|----------|
| Insufficient evidence | No citations | "证据不足，无法确定性回答" |
| Provider failure | API error | "服务暂时不可用，请稍后重试" |
| Stale corpus | Old dates | "语料可能过时，建议查看最新报告" |

**Verification**:
- [ ] Failures are detected
- [ ] Responses are bounded
- [ ] Communication is clear

### Module 5: Cost and Latency Guardrails

**Goal**: Simple queries cheap, complex ones bounded.

**Requirements**:
- [ ] Track tool call counts
- [ ] Track provider usage
- [ ] Set budget limits
- [ ] Show budget in traces

**Budget Configuration**:
```python
AGENT_BUDGET = {
    "max_tool_calls": 5,
    "max_web_searches": 2,
    "max_deep_fetches": 1,
    "timeout_seconds": 30,
}
```

**Verification**:
- [ ] Budgets are enforced
- [ ] Budgets are visible
- [ ] Simple queries are cheap

## Implementation Plan

### Phase 1: Context-Aware Entry (Module 1)
- Modify ChatRequest to include context
- Pass context to Agent
- Verify context usage

### Phase 2: Tool Traces (Module 2)
- Add trace tracking to chat_service
- Generate compact trace summary
- Display trace in UI

### Phase 3: Task Modes (Module 3)
- Implement mode detection
- Adjust strategies per mode
- Test all modes

### Phase 4: Failure Handling (Module 4)
- Implement failure detection
- Implement bounded responses
- Test failure scenarios

### Phase 5: Cost Guardrails (Module 5)
- Implement budget tracking
- Implement budget enforcement
- Test budget limits

## Testing Strategy

### Unit Tests
- [ ] Context passing
- [ ] Trace generation
- [ ] Mode detection
- [ ] Failure detection
- [ ] Budget enforcement

### Integration Tests
- [ ] Context-aware responses
- [ ] Trace display
- [ ] Mode-specific behavior
- [ ] Failure handling
- [ ] Budget limits

### End-to-End Tests
- [ ] Complete research workflow
- [ ] All task modes
- [ ] All failure scenarios

## Definition of Done

### Product Behavior
- [ ] Agent receives and uses context
- [ ] Tool traces are visible
- [ ] All task modes work
- [ ] Failures are handled gracefully
- [ ] Costs are bounded

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

1. **Context complexity**: Too much context may confuse Agent
2. **Trace verbosity**: Traces may be too detailed or too sparse
3. **Mode detection**: May misclassify queries
4. **Budget enforcement**: May be too strict or too loose
5. **Failure handling**: May miss some failure scenarios

## Success Metrics

| Metric | Target | Measurement |
|--------|--------|-------------|
| Context usage rate | >80% | Agent uses context when available |
| Trace visibility | 100% | All responses include traces |
| Mode accuracy | >90% | Correct mode detection |
| Failure handling | 100% | All failures handled gracefully |
| Cost efficiency | >50% | Simple queries use fewer resources |

---

## Update Log

| Date | Version | Changes |
|------|---------|---------|
| 2026-06-25 | v1.0 | Initial version |
