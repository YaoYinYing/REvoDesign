#!/usr/bin/env python3
"""Check CHANGELOG.md for duplicate section headers within a version block.

Usage:
    python dev/tools/check_changelog_duplicates.py [CHANGELOG.md]

Exit code: non-zero if duplicates found.
"""

from __future__ import annotations

import re
import sys
from collections import Counter
from pathlib import Path

VERSION_RE = re.compile(r"^##\s+\[")
SECTION_RE = re.compile(r"^###\s+(.+)")


def check_changelog(path: Path) -> list[str]:
    """Return a list of duplicate-section errors. Empty list = clean."""
    errors: list[str] = []
    lines = path.read_text().splitlines()

    current_version: str | None = None
    sections: list[tuple[int, str]] = []  # (line_number, section_name) for current version

    def flush() -> None:
        """Check the accumulated sections for the current version block."""
        nonlocal sections
        if not sections:
            return
        counts = Counter(name for _, name in sections)
        for name, count in counts.items():
            if count > 1:
                dupes = [ln for ln, sn in sections if sn == name]
                errors.append(
                    f"{path}:{dupes[0]}: section '### {name}' appears {count} times "
                    f"under '{current_version}' (lines {', '.join(map(str, dupes))})"
                )
        sections = []

    for i, line in enumerate(lines, start=1):
        # Version header starts a new block
        m = VERSION_RE.match(line)
        if m:
            flush()
            current_version = line.strip()
            continue

        # Section header within a version block
        m = SECTION_RE.match(line)
        if m and current_version is not None:
            sections.append((i, m.group(1).strip()))

    flush()  # check the last version block
    return errors


def main() -> int:
    path = Path(sys.argv[1]) if len(sys.argv) > 1 else Path("CHANGELOG.md")
    if not path.exists():
        print(f"File not found: {path}", file=sys.stderr)
        return 1

    errors = check_changelog(path)
    if errors:
        print(f"{len(errors)} duplicate section(s) found:\n", file=sys.stderr)
        for e in errors:
            print(f"  {e}", file=sys.stderr)
        return 1

    print("CHANGELOG.md: no duplicate sections.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
