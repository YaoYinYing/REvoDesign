# AI-Assisted DeepSource Fix Playbook

Practical workflow for using Claude Code (or any AI coding assistant) to fix
DeepSource findings — risk-first, minimal diffs, stable tests.

## Goal

Fix a large DeepSource backlog by prioritizing the most dangerous and complex
findings first, while keeping behavior stable and tests green.

## Principles

1. **Risk first**, not count first
2. **Root-cause patches**, not one-off local silencing
3. **Small safe diffs** over broad refactors
4. Every risky fix must have verification
5. Keep changelog and docs updated in the same PR

## Accessing DeepSource Issues

Use a regular browser user agent:

```bash
curl -sS -L -A "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/143.0.0.0 Safari/537.36" \
  "https://app.deepsource.com/gh/YaoYinYing/REvoDesign/issues" \
  -o /tmp/deepsource_issues.html
```

If static HTML is insufficient, use the same UA for authenticated GraphQL/API
calls (with CSRF/cookies) and save raw payloads for traceability.

## Classification Model

Classify each finding on two axes: danger and complexity.

### Danger Levels

| Level | Meaning |
|-------|---------|
| **D0 Critical** | Security, data corruption, remote execution, credential/path leakage, unsafe deserialization |
| **D1 High** | Runtime crashes, concurrency hazards, deadlocks, silent wrong results |
| **D2 Medium** | Reliability/perf regressions with user-visible impact |
| **D3 Low** | Readability/style/maintainability only |

### Complexity Levels

| Level | Meaning |
|-------|---------|
| **C0 Low** | Local one-file change, obvious behavior, easy regression test |
| **C1 Medium** | Multi-file but stable boundaries |
| **C2 High** | Cross-module flow, threading/process/network interactions |
| **C3 Very High** | Architectural shifts, migration-level changes |

## Prioritization Rule

Work in this order:

1. **D0/C0–C2** — critical danger, tractable complexity
2. **D1/C0–C2** — high danger, tractable complexity
3. **D0/D1 C3** — only when isolated safely
4. **D2 batches** — medium danger
5. **D3 cleanup** — low danger

Within the same bucket, prioritize by blast radius:

1. Core runtime modules (`src/REvoDesign/...` hot paths)
2. Shared tools/utilities
3. Optional paths and edge flows

## Batch Strategy

Small batches (5–10 issues) grouped by root cause family:

1. Serialization and file safety
2. Subprocess/network/IO robustness
3. Qt/thread interaction safety
4. Path and temp-file handling
5. Test determinism and ordering

This avoids mixing unrelated risk and simplifies rollback.

## Fix Workflow (Repeatable)

1. Fetch and snapshot issue list
2. Normalize and deduplicate findings by root cause
3. Assign danger and complexity
4. Select next batch by priority
5. Patch with minimal code movement
6. Add or adjust targeted tests
7. Run `make clean` before test validation
8. Run `make kw-test` — focused first, then broader if needed
9. Update `CHANGELOG.md`
10. Record unresolved items and blockers

## Fix Patterns by Category

### 1. Unsafe Data Loading

**Do:**
- Replace unsafe loaders with constrained loaders
- Validate input type and expected schema early
- Fail closed with explicit, actionable errors

**Don't:**
- Broad `except Exception` without context
- Silent fallback that hides corruption

### 2. Subprocess and External Tools

**Do:**
- Use explicit argument lists (no implicit shell parsing unless required)
- Set timeout and capture stderr/stdout
- Return structured errors for UI/logging
- Validate executable existence before launch

**Don't:**
- Fire-and-forget calls in critical paths
- Weak error propagation

### 3. Paths, Files, and Temporary Artifacts

**Do:**
- Normalize and validate paths before use
- Create parent dirs deterministically
- Use atomic write patterns where practical
- Guard cleanup operations carefully

**Don't:**
- Trust user-provided file names blindly
- Destructive deletes without explicit path checks

### 4. Thread/UI Safety (Qt + Worker Threads)

**Do:**
- Keep UI updates on main thread
- Use centralized worker orchestration (`WorkerThread`, `ThreadExecutionManager`)
- Register and clean up worker state deterministically

**Don't:**
- Cross-thread UI updates
- Orphan worker/process state

### 5. Test Determinism and Ordering

**Do:**
- Express logical prerequisites with explicit `pytest-dependency` markers
- Keep order assumptions declarative
- Ensure required plugins are in `prepare-test` dependencies

**Don't:**
- Reorder tests to hide dependency problems
- Edit test expectations without validating runtime behavior

## Verification Commands

```bash
make clean
conda run -n REvoDesignTestFlight make kw-test PYTEST_KW='single keywords'
conda run -n REvoDesignTestFlight make kw-test PYTEST_KW='"keywordA or keywordB"'
```

For dependency-chain checks, include anchor tests and downstream tests in the
keyword expression.

## Documentation Checklist per Batch

1. What rule/finding was fixed
2. Why it was dangerous
3. What changed and why this is minimal
4. Which tests validate the change
5. Any known limitations or follow-up tasks

## Tracking Template

Use this table in PR bodies:

| DeepSource ID | Rule | Danger | Complexity | Files | Fix summary | Validation |
|---------------|------|--------|------------|-------|-------------|------------|
| ... | PY-XXXX | D1 | C1 | `src/...` | safer error path | `kw-test ...` |

## Anti-Patterns

1. Batch-fixing unrelated modules in one commit
2. Silencing warnings without code-level mitigation
3. Skipping `make clean` before validating flaky areas
4. Reordering tests to hide dependency problems
5. Editing test expectations without validating runtime behavior

## Definition of Done

A batch is done only if **all** are true:

1. Selected findings are fixed or explicitly deferred with reason
2. No new regressions in targeted tests
3. `CHANGELOG.md` updated
4. Rationale documented for non-obvious changes
5. Diff remains minimal and reviewable

## Operational Notes for Future AI-Assisted Runs

1. Start from highest danger findings, not oldest findings
2. Keep a local snapshot of issue payloads to prevent paging/context loss
3. Prefer deterministic tests and explicit dependency wiring for UI case chains
4. If network is restricted, document the blocker and still finish code/test/docs work that can run locally
5. Rank by risk and blast radius, not by tool/source order
6. Favor small, reviewable fixes with explicit tests

## See Also

- [AI-Assisted Codacy Fix Playbook](codex-codacy.md) — companion playbook for Codacy
- [Testing](testing.md) — test framework and CI workflow
- [CI/CD](ci-cd.md) — GitHub Actions configuration
