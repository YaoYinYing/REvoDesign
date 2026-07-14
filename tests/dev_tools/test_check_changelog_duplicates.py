# Copyright (c) 2026 The REvoDesign Developers.
# Distributed under the terms of the GNU General Public License v3.0.
# SPDX-License-Identifier: GPL-3.0-only

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "dev" / "tools"))

from check_changelog_duplicates import check_changelog  # noqa: E402


def test_clean_changelog_no_duplicates(tmp_path: Path):
    """No duplicate section headers within a version block."""
    md = tmp_path / "clean.md"
    md.write_text(
        "## [Unreleased]\n"
        "### Added\n- thing\n\n"
        "### Changed\n- change\n\n"
        "### Fixed\n- fix\n\n"
        "## [1.0.0]\n"
        "### Added\n- old\n"
    )
    assert check_changelog(md) == []


def test_duplicate_section_reported(tmp_path: Path):
    """Duplicate section header within the same version block is caught."""
    md = tmp_path / "dup.md"
    md.write_text(
        "## [Unreleased]\n"
        "### Added\n- one\n\n"
        "### Changed\n- first\n\n"
        "### Changed\n- second (duplicate key!)\n\n"
        "## [1.0.0]\n"
        "### Added\n- old\n"
    )
    errors = check_changelog(md)
    assert len(errors) == 1
    assert "### Changed" in errors[0]
    assert "2 times" in errors[0]


def test_duplicate_across_versions_is_fine(tmp_path: Path):
    """Same section name in different version blocks is not a duplicate."""
    md = tmp_path / "cross.md"
    md.write_text("## [Unreleased]\n" "### Added\n- new\n\n" "## [1.0.0]\n" "### Added\n- old\n")
    assert check_changelog(md) == []
