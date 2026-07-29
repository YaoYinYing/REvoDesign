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

## DeepSource Data Model

DeepSource exposes two related but non-interchangeable result sets:

| Model | Scope | Use |
|-------|-------|-----|
| Repository issues and occurrences | Active findings in the repository's default branch | Build and measure the complete cleanup queue |
| Analysis run and analyzer checks | Findings introduced between a run's `baseOid` and `commitOid` | Detect regressions from one commit or pull request |

An `Issue` is a rule definition such as `PYL-R1705`. An occurrence is one
location where that rule was raised. Count both:

- **rule count** measures how many distinct issue types remain;
- **occurrence count** measures how many code locations remain.

Do not compare a repository occurrence count with a run issue count. DeepSource
ignores issues introduced before an analysis run's `baseOid`, so a passing run
can coexist with a large default-branch backlog.

## Accessing DeepSource Data

Use the supported GraphQL endpoint with a DeepSource personal access token:

```text
POST https://api.deepsource.com/graphql/
Authorization: Bearer <PERSONAL_ACCESS_TOKEN>
Content-Type: application/json
```

Never commit the token, browser cookies, CSRF values, or unsanitized request
headers. Save sanitized JSON responses under `/tmp` with the queried repository,
branch, commit SHA, timestamp, variables, and pagination cursor.

The dashboard remains useful for interactive inspection, but HTML scraping and
private frontend operations are fallback diagnostics, not the audit contract.
Frontend query names and response shapes can change independently of the
documented API.

### Repository-wide cleanup query

Start with `repository { issues { ... } }` and expand every repository issue's
occurrences. The public schema models the relationship as:

```graphql
query RepositoryBacklog(
  $login: String!
  $name: String!
  $issuesAfter: String
) {
  repository(login: $login, name: $name, vcsProvider: GITHUB) {
    defaultBranch
    issues(first: 100, after: $issuesAfter, analyzerIn: ["python"]) {
      totalCount
      pageInfo {
        hasNextPage
        endCursor
      }
      edges {
        cursor
        node {
          id
          issue {
            shortcode
            title
            category
            severity
          }
          occurrences(first: 100) {
            totalCount
            pageInfo {
              hasNextPage
              endCursor
            }
            edges {
              cursor
              node {
                id
                path
                beginLine
                beginColumn
                endLine
                endColumn
              }
            }
          }
        }
      }
    }
  }
}
```

This example shows the data relationship, not a complete exporter. A production
exporter must paginate both connections:

1. paginate `repository.issues` until `hasNextPage` is false;
2. independently paginate `occurrences` for every repository issue;
3. reject incomplete snapshots rather than silently trusting the first page;
4. sum occurrence totals by category and compare them with the dashboard.

### Run-level regression query

Use `run(commitOid: ...)` and its checks only after establishing the repository
inventory. Record at least:

- `baseOid` and `commitOid`;
- run and check status;
- introduced, resolved, and suppressed occurrence counts;
- every returned issue path, shortcode, category, and severity;
- failing metrics and quality-gate configuration.

The run result answers, “What did this changeset introduce or resolve?” It does
not answer, “What remains everywhere in the repository?”

## Audit Workflow

Before editing code:

1. Record the current default branch and commit SHA.
2. Export the complete repository issue inventory with all occurrence pages.
3. Filter the inventory to the requested categories: Bug Risk, Anti-pattern,
   Security, and Performance.
4. Report rule counts and occurrence counts separately.
5. Compare every occurrence with the recorded default-branch revision.
6. If a line reference has drifted, search the entire tracked source tree for
   the rule's pattern and record the mismatch; do not discard the rest of the
   category.
7. Group reproducible occurrences by shortcode and root cause.
8. Fix and test one reviewable batch.
9. Push the batch and use its analysis run as a regression gate.
10. Repeat until the local manifest has no unresolved validated occurrences.

Repository inventory describes the default branch, so a pull-request branch
cannot prove that the default-branch backlog has cleared. After merge, wait for
the new default-branch analysis, export the repository inventory again, and
reconcile every rule and occurrence with the pre-fix snapshot.

For rules supported by local tooling, add an independent full-repository gate.
For example:

```bash
git ls-files -z -- '*.py' |
  xargs -0 pylint --disable=all --enable=PYL-R1705,PYL-R1724
```

Do not replace the DeepSource inventory with local lint output: analyzer
versions, configuration, suppressions, and rule implementations can differ.

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

| Occurrence ID | Rule | Category | Danger | Complexity | File:line | Status | Validation |
|---------------|------|----------|--------|------------|-----------|--------|------------|
| ... | PY-XXXX | Bug Risk | D1 | C1 | `src/...:42` | fixed | `kw-test ...` |

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
3. The full-repository local checker for the selected rules is clean, when available
4. The pushed batch's DeepSource run introduces no blocking regression
5. `CHANGELOG.md` updated
6. Rationale documented for non-obvious changes
7. Diff remains minimal and reviewable

The complete campaign is done only after a post-merge default-branch inventory
confirms that every targeted occurrence is resolved or explicitly suppressed
with a documented justification.

## Operational Notes for Future AI-Assisted Runs

1. Start from highest danger findings, not oldest findings
2. Keep a local snapshot of issue payloads to prevent paging/context loss
3. Prefer deterministic tests and explicit dependency wiring for UI case chains
4. If network is restricted, document the blocker and still finish code/test/docs work that can run locally
5. Rank by risk and blast radius, not by tool/source order
6. Favor small, reviewable fixes with explicit tests

## See Also

- [DeepSource API overview](https://docs.deepsource.com/docs/developers/api)
- [DeepSource repository API](https://docs.deepsource.com/docs/developers/api/repository)
- [DeepSource analysis run API](https://docs.deepsource.com/docs/developers/api/analysis-run)
- [DeepSource issue model](https://docs.deepsource.com/docs/developers/api/issue)
- [AI-Assisted Codacy Fix Playbook](codex-codacy.md) — companion playbook for Codacy
- [Testing](testing.md) — test framework and CI workflow
- [CI/CD](ci-cd.md) — GitHub Actions configuration
