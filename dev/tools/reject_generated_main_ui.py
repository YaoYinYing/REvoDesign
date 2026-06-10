# Copyright (c) 2026 The REvoDesign Developers.
# Distributed under the terms of the GNU General Public License v3.0.
# SPDX-License-Identifier: GPL-3.0-only

"""Reject generated runtime use of Ui_REvoDesign.py."""

from __future__ import annotations

import argparse
import ast
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
UI_PY_PATH = REPO_ROOT / "src/REvoDesign/UI/Ui_REvoDesign.py"


def _iter_python_files() -> list[Path]:
    files: list[Path] = []
    for root_name in ("src",):
        root = REPO_ROOT / root_name
        if not root.exists():
            continue
        for path in root.rglob("*.py"):
            if any(part in {".venv", "__pycache__", ".pytest_cache", ".mypy_cache"} for part in path.parts):
                continue
            files.append(path)
    return sorted(files)


def _find_ui_imports() -> list[str]:
    offenders: list[str] = []
    for path in _iter_python_files():
        relative_path = path.relative_to(REPO_ROOT)
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    if "Ui_REvoDesign" in alias.name:
                        offenders.append(f"{relative_path}:{node.lineno}: runtime import of Ui_REvoDesign.py")
            elif isinstance(node, ast.ImportFrom) and node.module and "Ui_REvoDesign" in node.module:
                offenders.append(f"{relative_path}:{node.lineno}: runtime import of Ui_REvoDesign.py")
    return offenders


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--allow-file-but-reject-imports",
        action="store_true",
        help="Temporarily allow the generated file to exist while still rejecting code references to it.",
    )
    args = parser.parse_args(argv)

    errors = _find_ui_imports()
    if UI_PY_PATH.exists() and not args.allow_file_but_reject_imports:
        errors.insert(0, f"{UI_PY_PATH.relative_to(REPO_ROOT)}: generated main UI file must be removed")

    if errors:
        for error in errors:
            print(error, file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
