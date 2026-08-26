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

- Module-scoped terse bullets in 1.8.5-era style
- Top-levels: `- Server:`, `- Package manager:`, `- Qt:`
- One-line sub-bullets under each
- Descriptions must be short, precise, and compact — never long prose paragraphs
- The `## TEMPLATE` block must stay empty
- Real content belongs only in version sections or `[Unreleased]`

### Example

```markdown
## [Unreleased]

### Server
- Add FreeBindCraft runner
- Redesign submission workspace UI

### Qt
- Fix QThread memory corruption with uvicorn servers
```

## Code-Doc Alignment

When a change alters behavior that existing docs describe:
- Update that description in the same PR
- Architecture sections, dev guides, CLAUDE.md all count
- A doc that still describes replaced design is a bug
- Reviewer asking "did you update the docs?" means the check was missed
