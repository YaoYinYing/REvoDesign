# Copyright (c) 2026 The REvoDesign Developers.
# Distributed under the terms of the GNU General Public License v3.0.
# SPDX-License-Identifier: GPL-3.0-only

import hmac
import json
import os
import tempfile
import urllib.error
from unittest.mock import patch

import pytest

import REvoDesign.tools.package_manager as package_manager
from REvoDesign.tools.package_manager import (
    _compute_hmac,
    bootstrap_extras_json,
    bootstrap_manager_ui_file,
    fetch_bootstrap_manifest,
    fetch_gist_file,
    fetch_gist_json,
    fetch_verified_bootstrap_file,
    load_bootstrap_extras_json,
    package_manager_bootstrap_dir,
    verify_manifest,
)


def test_pm_fetch_gist_file_valid_url():
    mock_url = "https://example.com/file.ui"
    mock_data = "mock UI content"
    with tempfile.NamedTemporaryFile(delete=False) as tmp_file:
        save_to_file = tmp_file.name

    with patch("urllib.request.urlopen") as mock_urlopen:
        mock_urlopen.return_value.__enter__.return_value.read.return_value = mock_data.encode()
        fetch_gist_file(mock_url, save_to_file)

    with open(save_to_file) as file:
        assert file.read() == mock_data
    os.remove(save_to_file)


def test_pm_fetch_gist_file_invalid_url():
    with pytest.raises(ValueError, match="URL must start with 'https'"):
        fetch_gist_file("http://example.com/file.ui", "temp_file.ui")


def test_pm_fetch_gist_file_url_error():
    with tempfile.NamedTemporaryFile() as tmp_file:
        with patch("urllib.request.urlopen", side_effect=urllib.error.URLError("Mock error")):
            with pytest.raises(urllib.error.URLError, match="Failed to download file:"):
                fetch_gist_file("https://example.com/file.ui", tmp_file.name)


def test_pm_fetch_gist_file_uses_timeout(monkeypatch, tmp_path):
    calls = []

    def mock_read(url, **kwargs):
        calls.append((url, kwargs))
        return b"mock UI content"

    output = tmp_path / "manager.ui"
    monkeypatch.setattr(package_manager, "_read_https_url", mock_read)
    fetch_gist_file("https://example.com/file.ui", str(output), timeout=3)

    assert output.read_text() == "mock UI content"
    assert calls == [("https://example.com/file.ui", {"timeout": 3})]


def test_pm_fetch_gist_file_rejects_non_temporary_destination(monkeypatch, tmp_path):
    def unexpected_read(*_args, **_kwargs):
        raise AssertionError("invalid destinations must be rejected before downloading")

    temporary_root = tmp_path / "temporary-root"
    temporary_root.mkdir()
    monkeypatch.setattr(package_manager, "_read_https_url", unexpected_read)
    monkeypatch.setattr(package_manager.tempfile, "gettempdir", lambda: str(temporary_root))

    with pytest.raises(ValueError, match="must be located in the temporary directory"):
        fetch_gist_file(
            "https://example.com/file.ui",
            str(temporary_root.parent / "outside" / "manager.ui"),
        )


def test_pm_fetch_gist_file_rejects_symlink_destination(monkeypatch, tmp_path):
    outside_file = tmp_path.parent / "outside-manager.ui"
    outside_file.write_text("do not overwrite")
    destination = tmp_path / "manager.ui"
    destination.symlink_to(outside_file)
    monkeypatch.setattr(package_manager, "_read_https_url", lambda *_args, **_kwargs: b"replacement")

    with pytest.raises(OSError):
        fetch_gist_file("https://example.com/file.ui", str(destination))

    assert outside_file.read_text() == "do not overwrite"


def test_pm_fetch_gist_json_valid():
    mock_json = {"key1": "value1", "key2": "value2"}
    with patch("urllib.request.urlopen") as mock_urlopen:
        mock_urlopen.return_value.__enter__.return_value.read.return_value = json.dumps(mock_json).encode()
        assert fetch_gist_json("https://example.com/data.json") == mock_json


def test_pm_fetch_gist_json_invalid_structure():
    with patch("urllib.request.urlopen") as mock_urlopen:
        mock_urlopen.return_value.__enter__.return_value.read.return_value = json.dumps(["value"]).encode()
        assert fetch_gist_json("https://example.com/data.json") == {}


def test_pm_fetch_gist_json_error():
    with patch("urllib.request.urlopen", side_effect=Exception("Mock error")):
        assert fetch_gist_json("https://example.com/data.json") == {}


def test_pm_load_bootstrap_extras_json(tmp_path):
    registry = tmp_path / "REvoDesignExtrasTableRich.json"
    registry.write_text(json.dumps({"entities": []}))
    assert load_bootstrap_extras_json(registry) == {"entities": []}


def test_pm_bootstrap_paths_use_env(monkeypatch, tmp_path):
    monkeypatch.setenv(package_manager.PACKAGE_MANAGER_BOOTSTRAP_ENV, str(tmp_path))
    assert package_manager_bootstrap_dir() == tmp_path
    assert bootstrap_manager_ui_file() == tmp_path / "UI" / "REvoDesign_installer.ui"
    assert bootstrap_extras_json() == tmp_path / "REvoDesignExtrasTableRich.json"


def test_pm_verify_manifest_all_match(monkeypatch, tmp_path):
    key = os.urandom(32)
    monkeypatch.setattr(package_manager, "_MANAGER_HMAC_KEY", key)
    files = {}
    manifest = {}
    for name in ("a.py", "b.ui"):
        path = tmp_path / name
        path.write_bytes(os.urandom(64))
        files[name] = str(path)
        manifest[name] = hmac.new(key, path.read_bytes(), "sha256").hexdigest()
    assert verify_manifest(files, manifest)


def test_pm_verify_manifest_mismatch(monkeypatch, tmp_path):
    key = os.urandom(32)
    monkeypatch.setattr(package_manager, "_MANAGER_HMAC_KEY", key)
    path = tmp_path / "a.py"
    path.write_bytes(b"original")
    manifest = {"a.py": hmac.new(key, b"tampered", "sha256").hexdigest()}
    assert not verify_manifest({"a.py": str(path)}, manifest)


def test_pm_verify_manifest_missing_entry(monkeypatch, tmp_path):
    monkeypatch.setattr(package_manager, "_MANAGER_HMAC_KEY", os.urandom(32))
    path = tmp_path / "a.py"
    path.write_bytes(b"data")
    assert not verify_manifest({"a.py": str(path)}, {})


def test_pm_fetch_bootstrap_manifest_rejects_invalid_schema(monkeypatch):
    monkeypatch.setattr(package_manager, "fetch_required_gist_json", lambda _url: {"asset.py": 123})
    with pytest.raises(ValueError, match="Bootstrap manifest must map asset names to HMAC strings"):
        fetch_bootstrap_manifest()


def test_pm_fetch_verified_bootstrap_file_retries_on_hmac_mismatch(monkeypatch, tmp_path):
    key = os.urandom(32)
    monkeypatch.setattr(package_manager, "_MANAGER_HMAC_KEY", key)
    monkeypatch.setattr(package_manager.time, "sleep", lambda _seconds: None)
    output = tmp_path / "asset.ui"
    expected_payload = b"expected asset"
    manifest = {"asset.ui": hmac.new(key, expected_payload, "sha256").hexdigest()}
    fetch_payloads = iter((b"tampered asset", expected_payload))
    fetch_calls = []

    def mock_fetch(ui_file_url, save_to_file, **kwargs):
        fetch_calls.append(ui_file_url)
        with open(save_to_file, "wb") as file_handle:
            file_handle.write(next(fetch_payloads))

    monkeypatch.setattr(package_manager, "fetch_gist_file", mock_fetch)
    fetch_verified_bootstrap_file(
        url="https://example.com/asset.ui",
        asset_name="asset.ui",
        save_to_file=str(output),
        manifest=manifest,
        description="test asset",
    )

    assert fetch_calls == ["https://example.com/asset.ui", "https://example.com/asset.ui"]
    assert output.read_bytes() == expected_payload


def test_pm_compute_hmac_deterministic(monkeypatch, tmp_path):
    monkeypatch.setattr(package_manager, "_MANAGER_HMAC_KEY", os.urandom(32))
    path = tmp_path / "a.py"
    path.write_bytes(b"hello")
    assert _compute_hmac(str(path)) == _compute_hmac(str(path))


def test_pm_compute_hmac_rejects_non_temporary_path(monkeypatch, tmp_path):
    temporary_root = tmp_path / "temporary-root"
    temporary_root.mkdir()
    monkeypatch.setattr(package_manager.tempfile, "gettempdir", lambda: str(temporary_root))
    path = temporary_root.parent / "outside" / "manager.py"

    with pytest.raises(ValueError, match="must be located in the temporary directory"):
        _compute_hmac(str(path))
