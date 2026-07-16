# DeepSource Active Issue Reduction Plan

Snapshot date: 2026-07-16

Target: reduce the DeepSource headline active occurrence count from about
1.3k to 300 or fewer, without masking real security findings.

## Current Evidence

DeepSource's issue page for the default branch reported these active occurrence
widgets in the latest snapshot:

| Widget | Count |
|--------|-------|
| All active occurrences | 1259 |
| Recommended | 855 |
| Secrets | 674 |
| Coverage | 480 |
| Antipattern | 508 |
| Style | 168 |
| Performance | 61 |
| Bug risk | 42 |
| Docs | 0 |
| Typecheck | 0 |

These widgets overlap and must not be added together.

The latest default-branch analysis in the snapshot was:

| Field | Value |
|-------|-------|
| Branch | `main` |
| Commit | `57c36bcc5e5b3d6261b5f9f8cdaeb1690f00a41e` |
| Analysis run | `9ea7977c-250b-4dbd-abd2-a5b02ae9e62e` |
| Status | `FAIL` |
| Finished | `2026-07-15T16:34:11` |

The active PR branch for the first remediation batch was:

| Field | Value |
|-------|-------|
| Branch | `codex/deepsource-audit-fixes` |
| Commit | `8d7d1f56dfd02dc2b7a2e6b7ceaf81736183b3b2` |
| Analysis run | `769adfbb-aaf5-48c5-a111-0ff6c6436c6d` |
| Status | `PASS` |
| Python check result | `0` issues raised, `18` resolved |
| Finished | `2026-07-16T03:40:15` |

The default-branch Python check exported through the API contained 519 issue
nodes:

| Category | Count |
|----------|-------|
| Security | 453 |
| Antipattern | 59 |
| Style | 3 |
| Bug risk | 2 |
| Performance | 2 |

High-volume Python issue families on `main` were:

| Rule | Count | Main cause |
|------|-------|------------|
| `BAN-B101` | 444 | `assert` statements in `server/tests/**` treated as production security findings |
| `BAN-B103` | 4 | File-permission test helpers in `server/tests/**` treated as production security findings |
| `PY-W2000` | 33-36 | Unused imports, mostly test and server cleanup |
| `PY-W0069` | 7 | Commented-out code blocks |
| `PTC-W0043` | 6 | Unnecessary local `del` statements |
| `PY-R1000` | 5 | High cyclomatic complexity |
| `PTC-W0048` | 2 | Mergeable `if` statements |
| `PYL-R0401` | 1 | Cyclic import |

Evidence files from this snapshot:

| File | Purpose |
|------|---------|
| `/tmp/deepsource_plan_issues.html` | Server-rendered issue page snapshot |
| `/tmp/deepsource_all_issues_fullscope.json` | Default-branch Python issue export |
| `/tmp/deepsource_main_concrete_all_plan.json` | Grouped default-branch issue families |
| `/tmp/deepsource_run_detail_fullscope.json` | Default-branch run detail |
| `/tmp/deepsource_pr_run_detail_plan.json` | PR branch run detail |

## Reduction Strategy

To reach 300 from 1259, the project must remove or legitimately resolve at
least 959 active occurrences. The fastest safe path is not to rewrite test
asserts one by one; it is to fix scope first, then handle secrets, then use
coverage and low-volume code quality work only as needed.

### Stage 0: Merge the Python Scope Fix

PR #193 adds `server/tests/**` to DeepSource's test/exclude configuration and
Bandit's test exclusion, then fixes the small production findings surfaced in
`server/pssm_gremlin_server`.

Expected effect:

| Metric | Before | After PR branch |
|--------|--------|-----------------|
| Python issues raised in run | 497 | 0 |
| Python check status | `FAIL` | `PASS` |
| Test-noise security findings | 448+ | 0 on PR branch |

Verification gate:

1. Merge PR #193.
2. Wait for a default-branch DeepSource reanalysis.
3. Confirm the default-branch Python check no longer raises the
   `server/tests/**` assert and file-permission findings.
4. Record the new `all` active occurrence count before starting Stage 1.

Do not spend time replacing pytest `assert` usage in `server/tests/**`; those
are test semantics, not production security defects.

### Stage 1: Resolve the Secrets Bucket

The issue page reports 674 active secret occurrences. This is the largest
security bucket and should be treated as the highest-risk remaining work after
the Python scope fix.

Required workflow:

1. Export exact secret findings from DeepSource's secret detector UI/API.
2. Classify each occurrence as real secret, generated fixture, documented
   placeholder, or detector false positive.
3. For real secrets, rotate or revoke the credential before deleting it from
   the repository.
4. For fixture or placeholder strings, replace them with unmistakable dummy
   values or move them into ignored test fixtures where appropriate.
5. Suppress only verified false positives, with a written rationale.

Expected effect:

| Item | Count |
|------|-------|
| Current secrets widget | 674 |
| Stage target | 0 active real or unsuppressed secret findings |

Verification gate:

1. DeepSource secrets widget is 0, or every remaining item is an explicit,
   documented false-positive suppression.
2. Any rotated credentials are confirmed invalid in the upstream service.
3. The new headline active count is 300 or fewer, or Stage 2 starts with the
   updated count.

Do not silence secret findings without reviewing the exact path and value
class. A false positive can be suppressed; a real secret must be rotated first.

### Stage 2: Reduce Coverage Noise If Needed

The snapshot reports 480 active coverage occurrences. This bucket is high
volume but lower security risk than secrets. Start it only if Stage 0 and
Stage 1 do not bring the headline count to 300 or fewer.

Required workflow:

1. Export coverage occurrences and group them by package/module.
2. Split production code from generated, vendored, optional, and UI-only
   paths.
3. Exclude paths that are not meaningful coverage targets.
4. Add focused smoke or unit tests only for production code with realistic
   behavior risk.

Verification gate:

1. Coverage findings are reduced enough to keep the headline count at or below
   300.
2. Any coverage exclusions are scoped to generated, fixture, optional, or
   otherwise intentionally unmeasured paths.
3. New tests run under the repo's conda workflow.

### Stage 3: Clean Up Remaining Production Findings

After scope, secrets, and any required coverage work, handle the low-volume
production findings in small pull requests:

| Family | Count | Approach |
|--------|-------|----------|
| `PY-R1000` | 5 | Refactor only when the function boundary is clear and tests can pin behavior |
| `PYL-R0401` | 1 | Break the import cycle with a local import or dependency inversion |
| `PY-W2000` | Remaining | Remove unused imports only in production code |
| `PY-W0069` | Remaining | Delete dead commented code when it is not useful documentation |
| `PTC-W0043` | Remaining | Remove unnecessary local `del` statements |
| `PTC-W0048` | Remaining | Merge simple adjacent conditionals |

Verification gate:

1. Each batch has targeted tests or a documented reason tests are not needed.
2. `git diff --check` passes.
3. DeepSource no longer reports the targeted issue family on the affected
   branch.

## Count Model

The count model should be refreshed after every DeepSource reanalysis:

| Step | Confirmed or expected movement | Expected active count |
|------|--------------------------------|-----------------------|
| Snapshot | Current issue page | 1259 |
| Stage 0 | Python branch check already shows `0` raised and `18` resolved; default-branch page movement waits for merge/reanalysis | lower, exact value pending |
| Stage 1 | Remove or legitimately suppress 674 secret occurrences | likely below 300 if Stage 0 page movement is reflected |
| Stage 2 | Reduce coverage only if the headline remains above target | 300 or fewer |
| Stage 3 | Clean residual production findings | Keep below 300 and reduce future regression risk |

Because the widgets overlap, this model is intentionally conservative. The only
hard pass condition is the live DeepSource headline count after reanalysis.

## API Refresh Checklist

Use the DeepSource playbook for authenticated access. Save raw outputs for each
refresh and record the run ID, commit SHA, and timestamp.

Minimum refresh artifacts:

1. Issue page HTML with the active occurrence widgets.
2. Default-branch run detail for the latest analysis.
3. PR or follow-up branch run detail.
4. Per-check issue export for Python, secrets, and coverage.
5. Grouped issue-family summary with counts by rule and path.

## Stop Conditions

The reduction project is done when all of these are true:

1. DeepSource default-branch reanalysis reports 300 or fewer active
   occurrences.
2. The secrets bucket has no unresolved real credentials.
3. The Python check no longer audits `server/tests/**` as production code.
4. Any remaining active issues are documented as intentionally deferred with an
   owner, rule family, and reason.
