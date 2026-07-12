@../CLAUDE.md
@../AGENTS.md

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

## Claude-specific

- Slash commands live in `.claude/commands/`. `/spec`, `/verify`, and `/loop` are the primary entry points.
- The `verifier` subagent (`.claude/agents/verifier.md`) is dispatched by `/verify` and can be reused as an eval grader.
- The SessionStart hook (`.claude/hooks/session-start`) injects the `using-loopkit` skill on startup, `/clear`, and compaction — so skill routing is loaded from turn 1.
- Cross-agent rules live in the imported `AGENTS.md` at repo root. Do not duplicate them here.
- The canonical build/test/architecture docs are in `CLAUDE.md` at repo root (imported above).

<!-- Keep under 300 lines. Prune weekly. Every paragraph is a tax on every turn. -->
