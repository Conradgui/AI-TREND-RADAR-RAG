# Stage 2.7: Unified Local Demo Workspace Spec

**Date:** 2026-06-25

## Purpose

This stage reduces two-project friction by creating a unified local workspace. After Stage 2.4, 2.5, and 2.6 prove the local cockpit and agent value, the next step is to reduce deployment complexity.

## Product Position

The unified workspace should feel like a single, easy-to-use project:
- One cloneable repository
- One configurable `.env` file
- One complete local workflow from data preparation to dashboard

What it should **not** be:
- A full desktop application
- A production-grade scheduler
- An immediate replacement for all GitHub Actions
- A multi-user SaaS
- A long-running background application lifecycle manager

## User Jobs

### 1. Easy Setup
Users should be able to clone the repository and get started quickly with minimal configuration.

### 2. Single Configuration
One `.env` file should configure everything needed for the local workflow.

### 3. Complete Workflow
A clear sequence of commands from data preparation to dashboard should be available.

### 4. Modular Architecture
Internally, the workspace should maintain module boundaries:
- Upstream trend data production
- Corpus sync
- Indexing
- RAG/Agent analysis
- Dashboard experience

## Scope Boundary

**In scope:**
- Unified repository structure
- Unified configuration
- Unified local workflow
- Module boundary preservation

**Out of scope:**
- Full desktop application
- Production-grade scheduler
- GitHub Actions replacement
- Multi-user SaaS
- Long-running background application

## Architecture

### Candidate Approaches

| Approach | Description | Pros | Cons |
|----------|-------------|------|------|
| Local upstream folder | Simple local folder | Easy, simple | Not portable |
| Git submodule | Separate repos | Modular | Complex setup |
| Git subtree | Merged history | Unified history | Complex merge |
| Extracted package | Separate package | Clean separation | Extra dependency |

**Recommended**: Start with a simple local upstream folder or equivalent, then expose unified local commands.

### Module Boundaries

```
Unified Workspace
├── data-pipeline/ (TypeScript)
│   ├── src/
│   └── package.json
├── rag-engine/ (Python)
│   ├── rag/
│   └── requirements.txt
├── dashboard/ (HTML/JS)
│   ├── index.html
│   └── assets/
├── docs/
└── .env
```

## Modules

### Module 1: Unified Repository Structure

**Goal**: Create a unified repository structure that maintains module boundaries.

**Requirements**:
- [ ] Create unified directory structure
- [ ] Move existing code to appropriate directories
- [ ] Update import paths
- [ ] Verify functionality

**Approach**:
1. Create top-level directories
2. Move existing code
3. Update import paths
4. Test functionality

**Verification**:
- [ ] Directory structure created
- [ ] Code moved correctly
- [ ] Import paths updated
- [ ] Functionality preserved

### Module 2: Unified Configuration

**Goal**: Create a single `.env` file that configures everything.

**Requirements**:
- [ ] Create unified `.env.example`
- [ ] Update configuration loading
- [ ] Verify configuration works

**Approach**:
1. Create unified `.env.example`
2. Update `rag/config.py` to load from root
3. Update `src/config.ts` to load from root
4. Test configuration

**Verification**:
- [ ] `.env.example` created
- [ ] Configuration loading works
- [ ] All components configured

### Module 3: Unified Local Workflow

**Goal**: Create a clear sequence of commands from data preparation to dashboard.

**Requirements**:
- [ ] Document setup steps
- [ ] Create unified scripts
- [ ] Test complete workflow

**Approach**:
1. Document setup steps in README
2. Create `setup.sh` or similar
3. Create unified npm scripts
4. Test complete workflow

**Verification**:
- [ ] Setup steps documented
- [ ] Scripts created
- [ ] Workflow tested

## Implementation Plan

### Phase 1: Unified Repository Structure (Module 1)
- Create directory structure
- Move existing code
- Update import paths
- Test functionality

### Phase 2: Unified Configuration (Module 2)
- Create unified `.env.example`
- Update configuration loading
- Test configuration

### Phase 3: Unified Local Workflow (Module 3)
- Document setup steps
- Create unified scripts
- Test complete workflow

## Testing Strategy

### Unit Tests
- [ ] Directory structure
- [ ] Configuration loading
- [ ] Script execution

### Integration Tests
- [ ] End-to-end workflow
- [ ] Module integration
- [ ] Configuration integration

### End-to-End Tests
- [ ] Complete setup from scratch
- [ ] Full workflow execution
- [ ] Dashboard functionality

## Definition of Done

### Product Behavior
- [ ] Unified repository structure
- [ ] Single `.env` configuration
- [ ] Complete local workflow
- [ ] Module boundaries preserved

### Engineering Behavior
- [ ] No broken imports
- [ ] All tests pass
- [ ] Documentation updated
- [ ] Code follows project patterns

### Evidence Behavior
- [ ] Unit tests pass
- [ ] Integration tests pass
- [ ] Execution log recorded

## Residual Risks

1. **Import path breakage**: Moving code may break imports
2. **Configuration conflicts**: Unified config may conflict with existing
3. **Workflow complexity**: Unified workflow may be complex
4. **Module boundary erosion**: Unification may blur module boundaries

## Success Metrics

| Metric | Target | Measurement |
|--------|--------|-------------|
| Setup time | <10 minutes | Time from clone to dashboard |
| Configuration | 1 file | Single `.env` file |
| Workflow steps | <5 | Commands from data to dashboard |
| Module boundaries | Preserved | Clear separation maintained |

---

## Update Log

| Date | Version | Changes |
|------|---------|---------|
| 2026-06-25 | v1.0 | Initial version |
