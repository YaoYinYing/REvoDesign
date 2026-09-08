# PR Workflow Guide

## Full PR Babysitting Checklist

After opening a PR, own it through the squash-merge marker:

### 1. Branch Setup
- Work on a branch off `main`; never push to `main` directly
- Use conventional commit messages
- Each commit must be production-quality: show correct evolution, not wrong intermediate attempts

### 2. Babysit CI Until Green
- Monitor all CI checks
- Read every bot review comment from codex and coderabbit
- Decide per comment: fix or ignore
- Reply with evidence (file:line) when ignoring a valid-looking finding
- **DeepSource and Codacy are ignored** — their check statuses and comments are noise (stylistic lint profiles configured opposite to project conventions)
  - Don't fix, don't debate, don't treat them as blocking
  - No branch protection gates on them
  - Their findings get handled periodically in dedicated batch-fix PRs

### 3. Main Program PRs (PyMOL Plugin)
- CI and review comments only
- Run relevant gates: `make kw-test PYTEST_KW='<keyword>'`
- Cross-Qt checks exist in `REvoDesignTestFlight` (PyQt5) and `REvoDesignTestFlightQt6`

### 4. Merge
When CI is green and every comment is fixed or consciously ignored:
- Push a final empty marker commit only when handing the PR back for manual merge: `chore: Done fixing — <what was live/CI verified>`
- The `Done fixing` prefix is an intentional exception to the conventional-commit rule
- Otherwise squash-merge with a conventional commit title

## PR Lessons Learned

- Don't repeatedly trigger automated reviews
- Request one review pass, batch valid findings, verify locally between pushes

## Commit and PR Conventions

- PR titles use `type(scope): description` or `type: description`; valid types are `feat`, `fix`, `docs`, `style`, `refactor`, `perf`, `test`, `build`, `ci`, `chore`, and `revert`.
- Before pushing, run `make black`, then `git add -A`; pre-commit hooks must pass.
- Documentation lives under `docs/` or its relevant module directory and needs no build step.
- When a PR only touches documentation files (for example `docs/`, `CLAUDE.md`, `README.md`, `mkdocs.yml`, or `.github/workflows/docs.yml`), append `[skip ci]` to the final commit message.
