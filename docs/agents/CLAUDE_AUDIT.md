# CLAUDE.md Audit

**Date:** 2026-08-26
**Reference:** [Your AGENTS.md is a Neural Net](https://blog.kunchenguid.com/p/your-agentsmd-is-a-neural-net) by Kun Chen

## Goal

Keep `CLAUDE.md` small enough to load on every session while retaining the
project-wide constraints that prevent expensive mistakes. Rare procedures live
under `docs/agents/` and are loaded only when their task is relevant.

## Result

- `CLAUDE.md` is below its 3000-token / 400-line budget.
- Repeated commit, changelog, documentation, and version-bump instructions were
  removed from `CLAUDE.md`.
- [`PR_WORKFLOW.md`](PR_WORKFLOW.md) is the source for branch, PR, CI, review,
  deployment, and doc-only PR procedures.
- [`RELEASE.md`](RELEASE.md) is the source for version bumps, changelog style,
  and code-documentation alignment.
- `CLAUDE.md` links this audit and both procedural guides explicitly.

## Retention Rule

Keep an instruction in `CLAUDE.md` when it is broadly applicable,
safety-critical, or needed to understand the architecture. Move a rare,
step-by-step procedure to `docs/agents/` and leave one direct link at its trigger
point. Delete obsolete or duplicated instructions rather than preserving them
for history.

Use `memory/` for session-specific context and user preferences. Repository
history records prior instruction states; the live files should describe only
the current workflow.

## Maintenance

After substantial sessions:

1. Add only project-invariant learnings that prevent repeated mistakes.
2. Remove duplicate or obsolete instructions before adding more prose.
3. Keep `CLAUDE.md` under 3000 tokens and 400 lines.
4. Recheck every linked procedure and local path during the quarterly audit.
