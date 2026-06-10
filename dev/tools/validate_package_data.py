# Copyright (c) 2026 The REvoDesign Developers.
# Distributed under the terms of the GNU General Public License v3.0.
# SPDX-License-Identifier: GPL-3.0-only

"""Validate package data required by the runtime UI loader."""

from __future__ import annotations

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
REQUIRED_PATHS = (
    REPO_ROOT / "src/REvoDesign/UI/REvoDesign.ui",
    REPO_ROOT / "src/REvoDesign/UI/language/eng-chs.qm",
    REPO_ROOT / "src/REvoDesign/UI/language/eng-cht.qm",
)


def main() -> int:
    missing = [path.relative_to(REPO_ROOT) for path in REQUIRED_PATHS if not path.exists()]
    if missing:
        for path in missing:
            print(f"Missing required package data path: {path}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
