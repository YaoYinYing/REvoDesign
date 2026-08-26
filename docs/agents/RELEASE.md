# Release Process

## Version Bumping

### Steps

1. **Update version string**
   ```bash
   # Edit src/REvoDesign/__init__.py
   __version__ = "X.Y.Z"  # Validate format at https://regex101.com/r/6AoOI9/1
   ```

2. **Run make tag**
   ```bash
   make tag
   ```

   This command:
   - Extracts old/new versions from the git diff
   - Inserts a dated `[X.Y.Z]` section in `CHANGELOG.md`
   - Commits both `CHANGELOG.md` and `__init__.py`
   - Creates an annotated tag with the changelog between versions
   - Pushes with `--tags`

### Important

**Do NOT `git add` the version change before running `make tag`.**

The command reads versions from the *unstaged* diff of `__init__.py`.

## Changelog Conventions

- Add entries under the relevant Keep a Changelog section in `[Unreleased]`.
- Use module-scoped terse bullets in 1.8.5-era style: `- Server:`, `- Package manager:`, `- Qt:`, with compact one-line sub-bullets.
- Keep the `## TEMPLATE` block empty; real content belongs only in `[Unreleased]` or a version section.

### Example

```markdown
## [Unreleased]

### Added
- Server:
  - runner: FreeBindCraft GPU family.

### Fixed
- Qt:
  - prevent QThread memory corruption with uvicorn servers.
```

## Code-Doc Alignment

When a change alters behavior that existing docs describe:
- Update that description in the same PR
- Architecture sections, dev guides, CLAUDE.md all count
- A doc that still describes replaced design is a bug
- Reviewer asking "did you update the docs?" means the check was missed
