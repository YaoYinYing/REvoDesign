# PR Workflow Guide

## Full PR Babysitting Checklist

After opening a PR, own it through the squash-merge marker:

### 1. Branch Setup
- Work on a fix branch off `main`
- Use conventional commit messages
- Never push to `main` directly

### 2. Babysit CI Until Green
- Monitor all CI checks
- Read every bot review comment from codex and coderabbit
- Decide per comment: fix or ignore
- Reply with evidence (file:line) when ignoring a valid-looking finding
- **DeepSource and Codacy are ignored** — their check statuses and comments are noise (stylistic lint profiles configured opposite to project conventions)
  - Don't fix, don't debate, don't treat them as blocking
  - No branch protection gates on them
  - Their findings get handled periodically in dedicated batch-fix PRs

### 3. Server PRs (REvoCompute)

Follow [`server/DEPLOYMENT_CONTROL_GUIDE.md`](../server/DEPLOYMENT_CONTROL_GUIDE.md).

**Key points:**
- Use absolute production env path
- Exactly one controller mutation at a time
- If runner images changed: run prepare first while healthy stack remains up
- Sync `server/config/task_types.yaml` to production CONFIG_DIR before activation
- After restart, verify `${CONFIG_DIR}/.deploy-stamp`
- Live-verify on canonical edge `https://revocompute.yaoyy.moe` in incognito

**Living test flow:**
1. Login `POST /compute/api/auth/login` → Bearer token
2. Submit `POST /compute/api/post` (multipart file + task_type + params)
3. Monitor SLURM job (`squeue`)
4. Read results:
   - Status: `GET /compute/api/running/<md5>`
   - Manifest: `GET /compute/api/results/<md5>`
   - Logs: `GET /compute/api/results/<md5>/artifacts/<path>`
5. Verify served static files contain the change AND page behaves as designed

### 4. Main Program PRs (PyMOL Plugin)
- CI and review comments only — no server deploy
- Run relevant gates: `make kw-test PYTEST_KW='<keyword>'`
- Cross-Qt checks exist in `REvoDesignTestFlight` (PyQt5) and `REvoDesignTestFlightQt6`

### 5. Final Marker Commit
When CI is green and every comment is fixed or consciously ignored:
- Push final empty marker commit: `chore: Done fixing — <what was live/CI verified>`
- The `Done fixing` prefix is intentional exception to conventional-commit rule
- User squash-merges from there

## PR Lessons Learned

- Don't repeatedly trigger automated reviews
- Request one review pass, batch valid findings, verify locally between pushes
- Runner builds use final Docker tag directly — never create `:next` or `:previous` tags
- Replacing `:latest` retires old digest through dangling-image pruning
- For SIFs: record exact source Docker digest and SIF hash in `images/digest/image-sif.json`
- Refuse activation on mismatch

## Doc-Only PRs

When a PR only touches documentation files (e.g. `docs/`, `CLAUDE.md`, `README.md`, `mkdocs.yml`, or `.github/workflows/docs.yml`), append `[skip ci]` to the final commit message.
