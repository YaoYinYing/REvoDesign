# AI-Assisted Codacy Fix Playbook

Practical workflow for using Claude Code (or any AI coding assistant) to fix
Codacy findings in risk order — dangerous first, minimal diffs, stable tests.

## Goal

Fix Codacy findings ranked by risk, focusing on dangerous, complex, and
out-of-pattern issues while keeping CI green.

## Scope

1. Source: [Codacy issues](https://app.codacy.com/gh/YaoYinYing/REvoDesign/issues/current)
2. Output: ranked fix queue → batched patches → targeted regression checks → changelog
3. Constraint: **verify every finding against current code** before changing anything

## Accessing Codacy Issues

Browser-like user agent required for both HTML and API:

```bash
UA="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/143.0.0.0 Safari/537.36"

# HTML dashboard
curl -sS -L -A "$UA" \
  "https://app.codacy.com/gh/YaoYinYing/REvoDesign/issues/current" \
  -o /tmp/codacy_issues.html
```

For automation, use the Codacy v3 API with cursor pagination:

```bash
UA="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/143.0.0.0 Safari/537.36"
out=/tmp/codacy_issues_all.ndjson
: > "$out"
cursor=""
while :; do
  if [ -n "$cursor" ]; then
    url="https://app.codacy.com/api/v3/analysis/organizations/gh/YaoYinYing/repositories/REvoDesign/issues/search?limit=100&cursor=$cursor"
  else
    url="https://app.codacy.com/api/v3/analysis/organizations/gh/YaoYinYing/repositories/REvoDesign/issues/search?limit=100"
  fi
  curl -sS -L -A "$UA" -H "content-type: application/json" "$url" --data-binary '{}' -o /tmp/codacy_page.json || exit 1
  jq -c '.data[]' /tmp/codacy_page.json >> "$out"
  next=$(jq -r '.pagination.cursor // empty' /tmp/codacy_page.json)
  [ -z "$next" ] && break
  [ "$next" = "$cursor" ] && break
  cursor="$next"
done
jq -s '{data: ., total: length}' "$out" > /tmp/codacy_issues_all.json
```

## Payload Fields for Ranking

| Field | Purpose |
|-------|---------|
| `issueId` | Unique identifier |
| `filePath` | Affected source file |
| `lineNumber` | Line anchor |
| `message` | Human-readable description |
| `patternInfo.id` | Rule identifier |
| `patternInfo.category` | `Security`, `ErrorProne`, `BestPractice`, `Complexity`, `CodeStyle`, `UnusedCode` |
| `patternInfo.severityLevel` | `High`, `Warning`, `Info` |
| `toolInfo.name` | Tool that raised it (e.g., `Prospector`, `Lizard`, `ShellCheck`) |
| `commitInfo.sha` | Commit where the finding was introduced |

## Classification Model

Classify each issue on three axes:

### 1) Danger

| Level | Meaning |
|-------|---------|
| **D0 Critical** | Security or destructive behavior (command injection, credential leakage, unsafe path traversal) |
| **D1 High** | Runtime failures, invalid API behavior, concurrency hazards |
| **D2 Medium** | Reliability/perf issues, likely wrong edge-case behavior |
| **D3 Low** | Style/maintainability only |

### 2) Complexity

| Level | Meaning |
|-------|---------|
| **C0** | Single-file local fix |
| **C1** | 2–3 file flow changes |
| **C2** | Cross-module/runtime interactions (Docker, auth, async worker) |
| **C3** | Architecture-level shifts |

### 3) Out-of-Pattern

Flag if code conflicts with project conventions:

- Auth flow differs from server-wide behavior
- Path handling bypasses safety helpers
- Shell invocation bypasses existing hardened patterns
- Docker/env wiring uses inconsistent variable names

## Priority Scoring

Deterministic scoring to build the fix queue:

| Factor | Points |
|--------|--------|
| Severity: `High` | +5 |
| Severity: `Warning` | +3 |
| Severity: `Info` | +1 |
| Category: `Security` | +5 |
| Category: `ErrorProne` | +4 |
| Category: `BestPractice` | +2 |
| Category: `Complexity` | +2 |
| Category: `UnusedCode` | +1 |
| Category: `CodeStyle` | +0 |
| Externally exposed (HTTP/API/Docker) | +3 |
| CI-flaky or test-blocking | +2 |
| Out-of-pattern | +2 |

Sort descending, then batch by root cause family.

## Batch Strategy

Keep batches small and cohesive (5–12 issues):

1. Shell/script safety and command execution
2. Server auth/session/logout behavior
3. File/path/delete safety
4. Docker/env consistency
5. Frontend API contract consistency
6. Test harness determinism and CI parity

## Fix Workflow (Repeatable)

1. Fetch and snapshot Codacy issues
2. Deduplicate by root cause and file/line family
3. **Verify each finding against current code** — skip stale/false positives
4. Implement minimal fix
5. Add targeted tests for behavior and regression
6. Run `make clean` before test validation
7. Run `make kw-test PYTEST_KW='<keyword>'` — focused first, then broader
8. Update `CHANGELOG.md`
9. Record residual risk and follow-ups

## Verification Commands

```bash
make clean
conda run -n REvoDesignTestFlight make kw-test PYTEST_KW='single keywords'
conda run -n REvoDesignTestFlight make kw-test PYTEST_KW='"keywordA or keywordB"'
```

For server/Docker/auth changes, include integration keywords from
`tests/server/test_pssm_gremlin.py` where applicable.

## High-Value Fix Patterns

1. Convert unsafe `eval` or fragile pipeline composition to explicit argument-safe execution
2. Guard deletion by strict base-path validation before filesystem removal
3. Align Docker/env variable names across compose, runtime, and scripts
4. Replace brittle browser-auth logout loops with deterministic server/client handoff
5. Avoid root-like defaults; require explicit non-root identity in runner/server paths
6. Preserve distinctions in API return values (`[]` vs `None`) where semantics matter
7. Escape user/version strings before regex-oriented shell tools (e.g., `sed`)

## CI Drift Handling

If local tests pass but GitHub Actions fail:

1. Reproduce with nearest keyword subset
2. Inspect startup/readiness paths first (auth, networking, container health)
3. Improve diagnostics in failing harness code
4. Stabilize readiness checks with explicit liveness + authenticated probes
5. Re-run focused keywords before broader reruns

## Tracking Template

Use this table in PR bodies:

| Codacy ID | Rule | Danger | Complexity | Out-of-Pattern | Files | Fix | Validation |
|-----------|------|--------|------------|----------------|-------|-----|------------|
| ... | `patternInfo.id` | D1 | C1 | yes/no | `path` | one-line | `kw-test ...` |

## Anti-Patterns

1. Blindly fixing by tool severity without runtime verification
2. Large mixed-risk diffs across unrelated subsystems
3. Editing tests to match broken behavior
4. Skipping changelog/docs for behavior-impacting fixes
5. Claiming CI parity without reproducing representative keywords

## Definition of Done

A batch is done only when **all** are true:

1. Every selected finding is fixed or explicitly deferred with reason
2. Targeted tests pass from clean workspace (`make clean` first)
3. No new auth/runtime regressions
4. `CHANGELOG.md` updated
5. Notes are sufficient for a follow-up reviewer to audit quickly

## Quick Snapshot Commands

```bash
jq '.total' /tmp/codacy_issues_all.json
jq -r '.data[].patternInfo.category' /tmp/codacy_issues_all.json | sort | uniq -c | sort -nr
jq -r '.data[].patternInfo.severityLevel' /tmp/codacy_issues_all.json | sort | uniq -c | sort -nr
jq -r '.data[] | [.issueId,.patternInfo.id,.patternInfo.category,.patternInfo.severityLevel,.filePath,.lineNumber] | @tsv' \
  /tmp/codacy_issues_all.json > /tmp/codacy_issues_flat.tsv
```

## See Also

- [AI-Assisted DeepSource Fix Playbook](codex-deepsource.md) — companion playbook for DeepSource
- [Testing](testing.md) — test framework and CI workflow
- [CI/CD](ci-cd.md) — GitHub Actions configuration
