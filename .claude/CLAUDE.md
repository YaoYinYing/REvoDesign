@../CLAUDE.md

# Project: REvoDesign
Stack: Python 3.10+, PyMOL plugin (PyQt5/PyQt6), conda, OmegaConf/Hydra, FastAPI/uvicorn.
Layout: `src/REvoDesign/` (package), `tests/` (test suite), `dev/tools/` (dev scripts), `server/` (backend).

## Commands
- `conda run -n REvoDesignTestFlight make fast-test` — parallel test suite
- `conda run -n REvoDesignTestFlight make kw-test PYTEST_KW='<keyword>'` — focused test
- `make black` — pre-commit run --all-files (format, lint, validate)

## Conventions
- Match the existing code in the file you're editing. Read it before you write.
- One change, one purpose. No "while I was in there".
- Run `make black` before committing; pre-commit hooks must pass.
- Conventional commits (`feat:`, `fix:`, `docs:`, etc.). PR titles enforce it.
- Docs in `docs/` and entry in `CHANGELOG.md` after feature/bugfix work.

## Loop contract (Plan → Act → Verify)

Every session, in order:

1. **Plan.** Read `PROMPT.md` (goal), `IMPLEMENTATION_PLAN.md` (state), and `git log --oneline -20` (history).
2. **Act.** Implement exactly one feature. Not two.
3. **Verify.** Run `/verify` (adversarial pass against the diff) BEFORE claiming done or committing.

**Single-feature rule**: one feature per session. The next session takes the next feature.

**Clean-state**: all code committed with conventional commits, `make black` has run, no uncommitted changes. A feature is only "done" after `/verify`, not after unit tests alone.

## Skills

Skills are files at `.claude/skills/<name>/SKILL.md` — invoked on demand by trigger phrases. The SessionStart hook injects the routing table on startup. Full routing: `using-loopkit/SKILL.md`.

## Slash commands

- `/spec` — write `PROMPT.md` before implementing. Refuses to overwrite without `--force`.
- `/verify` — adversarial pass against the current diff (uses `verifier` subagent). Non-zero blocks completion.
- `/loop` — describe or run the Plan → Act → Verify cycle.

## Never

- Weaken or delete a test to make red go green.
- Mark work done without running `/verify`.
- Add a dependency without justifying it in the commit body.
- Unpin dependency versions unless the feature is "upgrade dependencies".
- Push to `main` from an agent session.

The canonical build/test/architecture docs are in `CLAUDE.md` at repo root (imported above). User instructions override this file.

<!-- Keep under 300 lines. Prune weekly. Every paragraph is a tax on every turn. -->
