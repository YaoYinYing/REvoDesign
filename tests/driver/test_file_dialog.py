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


def test_flatten_compressed_files_rejects_large_extracted_payload(tmp_path):
    archive = tmp_path / "compressed.zip"
    payload = "A" * 4096
    with zipfile.ZipFile(archive, "w", compression=zipfile.ZIP_DEFLATED) as zip_file:
        zip_file.writestr("payload.txt", payload)

    assert archive.stat().st_size < len(payload)
    with pytest.raises(ValueError, match="Archive expands too large"):
        flatten_compressed_files(
            str(archive),
            target_dir=str(tmp_path),
            max_archive_bytes=archive.stat().st_size + 1,
        )


def test_file_dialog_cleanup_archive_dirs_removes_temporary_extractions(tmp_path):
    temp_dir = tmp_path / "revodesign-input.zip-test"
    temp_dir.mkdir()
    (temp_dir / "payload.txt").write_text("payload")

    dialog = object.__new__(FileDialog)
    dialog._archive_temp_dirs = {str(temp_dir)}

    dialog.cleanup_archive_dirs()

    assert not temp_dir.exists()
    assert dialog._archive_temp_dirs == set()


def test_browse_filename_reopens_archive_temp_directory(monkeypatch, tmp_path):
    archive = tmp_path / "input.zip"
    _write_zip(archive)
    extracted_dir = tmp_path / "revodesign-input.zip-test"
    picked_file = extracted_dir / "payload.txt"
    dialogs = []

    def mock_get_open_file_name(_window, _title, directory="", **_kwargs):
        dialogs.append(directory)
        return str(archive) if len(dialogs) == 1 else str(picked_file)

    monkeypatch.setattr("REvoDesign.driver.file_dialog.decide", lambda **_kwargs: True)
    monkeypatch.setattr("REvoDesign.driver.file_dialog.flatten_compressed_files", lambda _path: str(extracted_dir))
    monkeypatch.setattr("REvoDesign.driver.file_dialog.getOpenFileNameWithExt", mock_get_open_file_name)

    dialog = object.__new__(FileDialog)
    dialog.window = None
    dialog._archive_temp_dirs = set()

    assert dialog.browse_filename() == str(picked_file)
    assert dialogs == ["", str(extracted_dir)]
    assert dialog._archive_temp_dirs == {str(extracted_dir)}
