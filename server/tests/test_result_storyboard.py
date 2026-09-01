# Copyright (c) 2026 The REvoDesign Developers.
# Distributed under the terms of the GNU General Public License v3.0.
# SPDX-License-Identifier: GPL-3.0-only

from __future__ import annotations

from revocompute.result_storyboard import resolve_expected_files


def test_expected_file_tree_resolves_logical_files_without_paths() -> None:
    files, checks, problems = resolve_expected_files(
        {
            "models": {"pattern": "models/*.cif", "required": True, "cardinality": "many"},
            "scores": {"path": "scores.csv", "required": False, "cardinality": "one"},
        },
        [
            {"path": "models/a.cif", "size": 1},
            {"path": "models/b.cif", "size": 1},
            {"path": "scores.csv", "size": 0},
        ],
    )
    assert [item["path"] for item in files["models"]] == ["models/a.cif", "models/b.cif"]
    assert files["scores"] == []
    assert [item["status"] for item in checks] == ["passed", "passed"]
    assert problems == []
