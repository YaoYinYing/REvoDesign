# Codex Codacy Fix Playbook

This document captures the practical Codacy workflow used in this repository to fix high-risk findings quickly, with minimal complexity and stable behavior.

## Goal

Fix Codacy findings in risk order, focusing first on dangerous, complex, and out-of-pattern issues, while keeping CI/test behavior stable.

## Scope

1. Source: Codacy `issues/current` for this repository.
2. Output: ranked fix queue, batched patches, targeted regression checks, changelog updates.
3. Constraint: verify every finding against current code before changing anything.

## Required Inputs

1. Codacy issues URL.
2. Browser-like user agent.
3. Local test runtime details (`conda` env, `make kw-test`, CI limits).

## Codacy Access Pattern

Use a regular browser user agent for both HTML and API calls.

```bash
UA="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/143.0.0.0 Safari/537.36"

curl -sS -L -A "$UA" \
  "https://app.codacy.com/gh/YaoYinYing/REvoDesign/issues/current" \
  -o /tmp/codacy_issues.html
```

For automation, use Codacy v3 issue search with cursor pagination:

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

## Payload Fields Used For Ranking

Typical fields used from Codacy payload:

1. `issueId`
2. `filePath`
3. `lineNumber`
4. `message`
5. `patternInfo.id`
6. `patternInfo.category`
7. `patternInfo.severityLevel`
8. `toolInfo.name`
9. `commitInfo.sha`

## Baseline Snapshot (Example)

From the saved payload `/tmp/codacy_issues_all.json` during this run:

1. Total issues: `201`
2. Category distribution:
   1. `CodeStyle: 84`
   2. `Complexity: 75`
   3. `BestPractice: 25`
   4. `Security: 13`
   5. `UnusedCode: 2`
   6. `ErrorProne: 2`
3. Severity distribution:
   1. `High: 11`
   2. `Warning: 106`
   3. `Info: 84`
4. Top tools:
   1. `Prospector: 76`
   2. `Lizard: 75`
   3. `ShellCheck: 24`

## Classification Model

Classify each issue on three axes.

### 1) Danger

1. `D0 Critical`: security or destructive behavior (`Security`, command injection, unsafe delete/path traversal, credential leakage).
2. `D1 High`: runtime failures, invalid API behavior, concurrency hazards, auth/control-plane breakage.
3. `D2 Medium`: reliability/perf issues, likely wrong behavior in edge cases.
4. `D3 Low`: style/maintainability only.

### 2) Complexity

1. `C0`: single-file local fix.
2. `C1`: 2-3 file flow changes.
3. `C2`: cross-module/runtime interactions (docker, auth, async worker, CI harness).
4. `C3`: architecture-level shifts.

### 3) Out-of-Pattern

Mark if code conflicts with current project conventions, for example:

1. auth flow differs from server-wide behavior.
2. path handling bypasses safety helpers.
3. shell invocation bypasses existing hardened patterns.
4. Docker/env wiring uses inconsistent variable names.

## Priority Scoring (Practical)

Use a deterministic score to build top-100 queue.

1. Severity points:
   1. `High=5`
   2. `Warning=3`
   3. `Info=1`
2. Category multiplier:
   1. `Security +5`
   2. `ErrorProne +4`
   3. `BestPractice +2`
   4. `Complexity +2`
   5. `UnusedCode +1`
   6. `CodeStyle +0`
3. Additions:
   1. `+3` if externally exposed (HTTP/API/docker entrypoint).
   2. `+2` if CI-flaky or test-blocking.
   3. `+2` if out-of-pattern.

Sort descending and take top 100. Then batch by root cause family.

## Batch Execution Strategy

Keep batches small and cohesive (5 to 12 issues):

1. Shell/script safety and command execution.
2. Server auth/session/logout behavior.
3. File/path/delete safety.
4. Docker/env consistency.
5. Frontend API contract consistency.
6. Test harness determinism and CI parity.

## Fix Workflow (Repeatable)

1. Fetch and snapshot Codacy issues.
2. Deduplicate by root cause and file/line family.
3. Verify each finding against current code.
4. Skip stale/false-positive findings with explicit note.
5. Implement minimal fix.
6. Add targeted tests for behavior and regression.
7. Run `make clean` before test validation.
8. Run focused `kw-test`, then broader tests as needed.
9. Update changelog in repo style.
10. Record residual risk/follow-up.

## Verification Rules

Minimum validation for each batch:

```bash
make clean
conda run -n REvoDesignLatestDev make kw-test PYTEST_KW='single keywords'
conda run -n REvoDesignLatestDev make kw-test PYTEST_KW='"keywordA or keywordB"'
```

For server/docker/auth changes, include integration-style keywords from `tests/server/test_pssm_gremlin.py` where feasible.

## High-Value Fix Patterns Observed In This Repo

1. Convert unsafe shell `eval` or fragile pipeline composition to explicit argument-safe execution.
2. Guard deletion by strict base-path validation before filesystem removal.
3. Align Docker/env variable names across compose, runtime, and scripts.
4. Replace brittle browser-auth logout loops with deterministic server/client handoff.
5. Avoid root-like defaults; require explicit non-root identity in runner/server paths.
6. Preserve distinctions in API return values (`[]` vs `None`) where semantic differences matter.
7. Escape user/version strings before regex-oriented shell tools (for example `sed`).

## CI Drift Handling

If local tests pass but GHA fails:

1. Reproduce with nearest keyword subset.
2. Inspect startup/readiness paths first (auth, networking, container health).
3. Improve diagnostics in failing harness code.
4. Stabilize readiness checks using explicit liveness + authenticated probes.
5. Re-run focused keywords before broader reruns.

## Tracking Template

Use this table in PR/body notes:

| Codacy Issue ID | Rule/Pattern | Danger | Complexity | Out-of-Pattern | Files | Fix | Validation |
|---|---|---|---|---|---|---|---|
| example | `patternInfo.id` | D1 | C1 | yes/no | `path` | one-line summary | `kw-test ...` |

## Anti-Patterns To Avoid

1. Blindly fixing by tool severity without runtime verification.
2. Large mixed-risk diffs across unrelated subsystems.
3. Editing tests to match broken behavior.
4. Skipping changelog/docs for behavior-impacting fixes.
5. Claiming CI parity without reproducing representative keywords.

## Definition Of Done (Codacy Batch)

A batch is done only when all are true:

1. Every selected finding is fixed or explicitly deferred with reason.
2. Targeted tests pass from clean workspace.
3. No new auth/runtime regressions introduced.
4. Changelog updated.
5. Notes are sufficient for follow-up reviewer (`Claude Code`) to audit quickly.

## Quick Snapshot Commands

```bash
jq '.total' /tmp/codacy_issues_all.json
jq -r '.data[].patternInfo.category' /tmp/codacy_issues_all.json | sort | uniq -c | sort -nr
jq -r '.data[].patternInfo.severityLevel' /tmp/codacy_issues_all.json | sort | uniq -c | sort -nr
jq -r '.data[] | [.issueId,.patternInfo.id,.patternInfo.category,.patternInfo.severityLevel,.filePath,.lineNumber] | @tsv' \
  /tmp/codacy_issues_all.json > /tmp/codacy_issues_flat.tsv
```

## Operational Notes For Future Codex Runs

1. Keep raw Codacy snapshots in `/tmp` for auditability and retry safety.
2. Rank by risk and blast radius, not by tool/source order.
3. Favor small, reviewable fixes with explicit tests.
4. Preserve existing project patterns unless a migration is intentional and documented.
