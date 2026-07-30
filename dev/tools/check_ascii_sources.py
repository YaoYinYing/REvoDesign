# Copyright (c) 2026 The REvoDesign Developers.
# Distributed under the terms of the GNU General Public License v3.0.
# SPDX-License-Identifier: GPL-3.0-only

"""Keep standalone Python sources safe across locale-aware download tools."""

from __future__ import annotations

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]

# These files are distributed as standalone Python source rather than solely
# through Python packaging, so locale-aware tools may transcode their bytes.
ASCII_ONLY_PATHS = (Path("src/REvoDesign/tools/package_manager.py"),)


def scan_file(path: Path) -> list[str]:
    """Return one diagnostic for each non-ASCII character in *path*."""

    try:
        display_path = path.relative_to(REPO_ROOT)
    except ValueError:
        display_path = path

    errors: list[str] = []
    source_bytes = path.read_bytes()
    try:
        text = source_bytes.decode("utf-8")
    except UnicodeDecodeError as error:
        line_number = source_bytes.count(b"\n", 0, error.start) + 1
        line_start = source_bytes.rfind(b"\n", 0, error.start) + 1
        column_number = error.start - line_start + 1
        escaped = "".join(f"\\x{byte:02x}" for byte in source_bytes[error.start : error.end])
        return [
            f"{display_path}:{line_number}:{column_number}: "
            f"invalid UTF-8 byte sequence {escaped}; "
            "standalone distributed Python sources must remain ASCII-only"
        ]

    for line_number, line in enumerate(text.splitlines(), start=1):
        for column_number, character in enumerate(line, start=1):
            if character.isascii():
                continue
            escaped = character.encode("unicode_escape").decode("ascii")
            errors.append(
                f"{display_path}:{line_number}:{column_number}: "
                f"non-ASCII character U+{ord(character):04X} ({escaped}); "
                "standalone distributed Python sources must remain ASCII-only"
            )
    return errors


def main() -> int:
    """Check every source governed by the ASCII-only distribution contract."""

    errors: list[str] = []
    for relative_path in ASCII_ONLY_PATHS:
        errors.extend(scan_file(REPO_ROOT / relative_path))

    if errors:
        for error in errors:
            print(error, file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
