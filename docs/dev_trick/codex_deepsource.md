# Codex DeepSource Fix Playbook

This document records the practical approach used to process DeepSource issues in this repository with minimal complexity and high safety.

## Goal

Fix a large DeepSource backlog by prioritizing the most dangerous and complex findings first, while keeping behavior stable and tests green.

## Principles

1. Risk first, not count first.
2. Root-cause patches, not one-off local silencing.
3. Small safe diffs over broad refactors.
4. Every risky fix must have verification.
5. Keep changelog and docs updated in the same PR.

## Inputs Required

1. DeepSource issues URL.
2. Browser-like user agent for issue fetching.
3. Local runtime/test environment details (`conda` env, test commands, CI constraints).

## Access Pattern For DeepSource

Use a regular browser user agent when fetching issue pages or APIs.

```bash
curl -sS -L -A "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/143.0.0.0 Safari/537.36" \
  "https://app.deepsource.com/gh/YaoYinYing/REvoDesign/issues" \
  -o /tmp/deepsource_issues.html
```

If static HTML is insufficient, use the same UA for authenticated GraphQL/API calls (with csrf/cookies) and save raw payloads for traceability.

## Issue Classification Model

Classify each finding on two dimensions: danger and complexity.

### Danger Levels

1. `D0 Critical`: Security, data corruption, remote execution, credential/path leakage, unsafe deserialization.
2. `D1 High`: Runtime crashes, concurrency hazards, deadlocks, silent wrong results.
3. `D2 Medium`: Reliability/perf regressions with user-visible impact.
4. `D3 Low`: Readability/style/maintainability only.

### Complexity Levels

1. `C0 Low`: Local one-file change, obvious behavior, easy regression test.
2. `C1 Medium`: Multi-file behavior but stable boundaries.
3. `C2 High`: Cross-module flow, threading/process/network interactions.
4. `C3 Very High`: Architectural shifts, migration-level changes.

## Prioritization Rule

Work in this order:

1. `D0/C0-C2`
2. `D1/C0-C2`
3. `D0/D1` items with `C3` only when isolated safely
4. `D2` batches
5. `D3` cleanup

Within the same bucket, prioritize by blast radius:

1. Core runtime modules (`src/REvoDesign/...` hot paths)
2. Shared tools/utilities
3. Optional paths and edge flows

## Batch Strategy

Use small batches (5 to 10 issues) grouped by root cause family:

1. Serialization and file safety
2. Subprocess/network/IO robustness
3. Qt/thread interaction safety
4. Path and temp-file handling
5. Test determinism and ordering

This avoids mixing unrelated risk and simplifies rollback.

## Fix Workflow (Repeatable)

1. Fetch and snapshot issue list.
2. Normalize and deduplicate findings by root cause.
3. Assign `danger` and `complexity`.
4. Select next batch by priority.
5. Patch with minimal code movement.
6. Add or adjust targeted tests.
7. Run `make clean` before test validation.
8. Run focused `kw-test` first, then broader suite if needed.
9. Update changelog.
10. Record unresolved items and blockers.

## Typical Fix Patterns Used In This Repo

### 1) Unsafe Data Loading

Preferred approach:

1. Replace unsafe loaders with constrained loaders.
2. Validate input type and expected schema early.
3. Fail closed with explicit, actionable errors.

Avoid:

1. Broad `except Exception` without context.
2. Silent fallback that hides corruption.

### 2) Subprocess and External Tools

Preferred approach:

1. Use explicit argument lists (no implicit shell parsing unless required).
2. Set timeout and capture stderr/stdout.
3. Return structured errors for UI/logging.
4. Validate executable existence before launch.

Avoid:

1. Fire-and-forget calls in critical paths.
2. Weak error propagation.

### 3) Paths, Files, and Temporary Artifacts

Preferred approach:

1. Normalize and validate paths before use.
2. Create parent dirs deterministically.
3. Use atomic write patterns where practical.
4. Guard cleanup operations carefully.

Avoid:

1. Trusting user-provided file names blindly.
2. Destructive deletes without explicit path checks.

### 4) Thread/UI Safety (Qt + Worker Threads)

Preferred approach:

1. Keep UI updates on main thread.
2. Use centralized worker orchestration.
3. Register and clean up worker state deterministically.

Avoid:

1. Cross-thread UI updates.
2. Orphan worker/process state.

### 5) Test Determinism and Ordering

Preferred approach:

1. Express logical prerequisites with explicit dependencies.
2. Keep order assumptions declarative.
3. Ensure required plugins are part of test dependencies.

Recent example:

1. Refactored tabs dependency chain to `pytest-dependency`.
2. Added `pytest-dependency` to test extras and `make prepare-test`.
3. Enabled `--order-dependencies`.

## Verification Protocol

Always verify in two layers:

1. Fast targeted checks
2. Broader regression checks

### Commands

```bash
make clean
conda run -n REvoDesignLatestDev make kw-test PYTEST_KW='single keywords'
conda run -n REvoDesignLatestDev make kw-test PYTEST_KW='"keywordA or keywordB"'
```

For dependency-chain checks, include anchor tests and downstream tests in the keyword expression.

## Documentation Checklist For Each Batch

1. What rule/finding was fixed.
2. Why it was dangerous.
3. What changed and why this is minimal.
4. Which tests validate the change.
5. Any known limitations or follow-up tasks.

## Suggested Tracking Table

Use this table format in PR descriptions or internal notes:

| DeepSource ID | Rule | Danger | Complexity | Files | Fix summary | Validation |
|---|---|---|---|---|---|---|
| example-id | PY-XXXX | D1 | C1 | `src/...` | safer error path | `kw-test ...` |

## Anti-Patterns To Avoid

1. Batch-fixing unrelated modules in one commit.
2. Silencing warnings without code-level mitigation.
3. Skipping `make clean` before validating flaky areas.
4. Reordering tests to hide dependency problems.
5. Editing test expectations without validating runtime behavior.

## Definition Of Done (DeepSource Batch)

A batch is done only if all are true:

1. Selected findings are fixed or explicitly deferred with reason.
2. No new regressions in targeted tests.
3. Changelog updated.
4. Rationale documented for non-obvious changes.
5. Diff remains minimal and reviewable.

## Notes For Future Codex Runs

1. Start from highest danger findings, not oldest findings.
2. Keep a local snapshot of issue payloads to prevent paging/context loss.
3. Prefer deterministic tests and explicit dependency wiring for UI case chains.
4. If network is restricted, document the blocker and still finish code/test/docs work that can run locally.
