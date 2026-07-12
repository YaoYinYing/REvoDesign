---
name: using-loopkit
description: Use when starting any conversation in a loopkit-enabled project — establishes how to find and use loopkit's skills, requiring skill invocation before ANY response including clarifying questions.
---

# Using Loopkit

<EXTREMELY-IMPORTANT>
If you think there is even a 1% chance a loopkit skill applies to what you are doing, INVOKE it.

IF A SKILL APPLIES, YOU DO NOT HAVE A CHOICE. YOU MUST USE IT.

This overrides "just answer quickly" instincts. Not negotiable.
</EXTREMELY-IMPORTANT>

## The Rule

**Invoke relevant skills BEFORE any response or action** — including clarifying questions, exploring the codebase, or reading files. If it turns out wrong for the situation, drop it.

Then announce "Using [skill] to [purpose]" and follow the skill exactly. If it has a checklist, create a todo per item.

## Where the skills live

Skills are files at `.claude/skills/<name>/SKILL.md`. Each has YAML frontmatter with `name` and `description` (the description is a trigger phrase, not a summary). Load a skill by reading its SKILL.md when its trigger matches your task.

Claude built-in skills (like `frontend-design:frontend-design`) are invoked directly — no SKILL.md in the repo.

## Skill routing (30 repo skills + built-ins)

| Task shape | First skill |
|---|---|
| "Fix this bug" / test failing / crash | `systematic-debugging`, then `read-the-trace` |
| "It broke between two commits" | `bisect-regression` |
| "Flaky test" | `flaky-hunter` |
| "Add a feature" / write anything new | `spec-first`, then `write-failing-test-first` |
| "Refactor" / dead code / deep nesting | `kill-dead-code`, `simplify`, `reduce-nesting` |
| About to claim done / commit / open PR | `adversarial-verify` + `verification-before-completion` + `self-eval-bias` |
| Review a diff / PR description | `adversarial-verify`, `pr-from-diff` |
| **REvoDesign domain skills:** | |
| Qt/PyMOL/threading/UI loading/i18n | `qt-pymol-guardrails` |
| Rosetta/sidechain solver/scoring/design | `rosetta-infrastructure` |
| ConfigBus/widgets/shortcuts/menus/tests | `ui-config-patterns` |
| **Server (`./server/`) skills:** | |
| Web UI / templates / dashboard design | `design-system`, `loading-empty-error-states`, `frontend-design:frontend-design` |
| Security / auth / API hardening | `owasp-review`, `authz-check`, `input-validation`, `secret-scan` |
| Database / SQL / schema / migrations | `sql-review`, `migration-writer`, `schema-diff` |
| **General skills:** | |
| Docs / changelog | `changelog-from-diff` |
| Git ops | `clean-commits`, `pr-from-diff` |
| Running out of context | `context-budget`, `tool-restraint` |

Full list: `ls .claude/skills/`.

## Red Flags — STOP and check for a skill

| Thought | Reality |
|---|---|
| "This is just a simple question" | Questions are tasks. Check first. |
| "Let me explore the codebase first" | Skills tell you HOW to explore. Check first. |
| "I remember this skill" | Skills evolve. Read the current SKILL.md. |
| "The skill is overkill" | Simple things become complex. Use it. |
| "I'll just do this one thing first" | Check BEFORE doing anything. |
| "Tests pass, we're good" | `verification-before-completion` says: run the exact command, read the output, then claim. |
| "I'll do both features while I'm in here" | One feature per session. Never two. |
| "The reviewer will let this slide" | `self-eval-bias` says: assume it will confidently praise. Calibrate first. |

## Priority when multiple skills apply

Process first → domain guardrails → implementation → finishers:

1. **Process**: `spec-first`, `systematic-debugging`, `bisect-regression`
2. **Domain guardrails**: `qt-pymol-guardrails`, `rosetta-infrastructure`, `ui-config-patterns`
3. **Implementation**: `design-system`, `sql-review`, `migration-writer`, etc.
4. **Finishers**: `adversarial-verify`, `verification-before-completion`, `self-eval-bias`, `clean-commits`

- "Let's build X" → `spec-first` → domain skills → implementation → `adversarial-verify`.
- "Fix bug Y" → `systematic-debugging` → `read-the-trace` → fix → `verification-before-completion`.
- "Qt or PyMOL work" → `qt-pymol-guardrails` first.
- "Rosetta or scoring work" → `rosetta-infrastructure` first.
- "Config or UI work" → `ui-config-patterns` first.
- "Server endpoint / template / DB" → relevant server skill first.

## User instructions win

CLAUDE.md, AGENTS.md, and direct user requests override loopkit skills. Only skip a skill workflow when the user has explicitly said to.
