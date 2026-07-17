# Copyright (c) 2026 The REvoDesign Developers.
# Distributed under the terms of the GNU General Public License v3.0.
# SPDX-License-Identifier: GPL-3.0-only

from __future__ import annotations

from pathlib import Path
import zipfile

import pytest

from REvoDesign.driver.file_dialog import FileDialog, flatten_compressed_files


def _write_zip(path: Path, member_name: str = "payload.txt", content: str = "payload") -> None:
    with zipfile.ZipFile(path, "w") as zip_file:
        zip_file.writestr(member_name, content)


def test_flatten_compressed_files_extracts_to_temporary_directory(tmp_path):
    archive = tmp_path / "input.zip"
    _write_zip(archive)

    extracted_dir = Path(flatten_compressed_files(str(archive), target_dir=str(tmp_path)))

    assert extracted_dir.is_dir()
    assert extracted_dir.parent == tmp_path
    assert extracted_dir.name.startswith("revodesign-input.zip-")
    assert not (tmp_path / "expanded_compressed_files").exists()
    assert (extracted_dir / "payload.txt").read_text() == "payload"


def test_flatten_compressed_files_rejects_oversized_archive(tmp_path):
    archive = tmp_path / "input.zip"
    _write_zip(archive)

    with pytest.raises(ValueError, match="Archive is too large"):
        flatten_compressed_files(str(archive), target_dir=str(tmp_path), max_archive_bytes=1)


def test_file_dialog_cleanup_archive_dirs_removes_temporary_extractions(tmp_path):
    temp_dir = tmp_path / "revodesign-input.zip-test"
    temp_dir.mkdir()
    (temp_dir / "payload.txt").write_text("payload")

    dialog = object.__new__(FileDialog)
    dialog._archive_temp_dirs = {str(temp_dir)}

    dialog.cleanup_archive_dirs()

    assert not temp_dir.exists()
    assert dialog._archive_temp_dirs == set()
