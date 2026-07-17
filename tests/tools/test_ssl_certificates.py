# Copyright (c) 2026 The REvoDesign Developers.
# Distributed under the terms of the GNU General Public License v3.0.
# SPDX-License-Identifier: GPL-3.0-only

from __future__ import annotations

import datetime
import stat

import pytest
from OpenSSL import crypto

import REvoDesign
from REvoDesign.tools.ssl_certificates import (
    CERT_VALIDITY_ENV,
    CERTIFICATE_MODE,
    PRIVATE_DIR_MODE,
    PRIVATE_KEY_MODE,
    SSLCertificateManager,
)


def _mode(path):
    return stat.S_IMODE(path.stat().st_mode)


def _load_cert(path):
    return crypto.load_certificate(crypto.FILETYPE_PEM, path.read_bytes())


def test_new_certificate_uses_random_serial_and_private_permissions(monkeypatch, tmp_path):
    monkeypatch.setattr(REvoDesign, "set_cache_dir", lambda: str(tmp_path))

    manager = SSLCertificateManager(role="server")
    manager.create_new_certificate()
    first_serial = _load_cert(tmp_path / "crts" / "server.crt").get_serial_number()

    manager.create_new_certificate()
    second_serial = _load_cert(tmp_path / "crts" / "server.crt").get_serial_number()

    assert first_serial != 1000
    assert second_serial != 1000
    assert first_serial != second_serial
    assert _mode(tmp_path / "crts") == PRIVATE_DIR_MODE
    assert _mode(tmp_path / "crts" / "server.key") == PRIVATE_KEY_MODE
    assert _mode(tmp_path / "crts" / "server.crt") == CERTIFICATE_MODE


def test_certificate_validity_can_be_configured(monkeypatch, tmp_path):
    monkeypatch.setattr(REvoDesign, "set_cache_dir", lambda: str(tmp_path))
    monkeypatch.setenv(CERT_VALIDITY_ENV, "3")

    manager = SSLCertificateManager(role="server")
    manager.create_new_certificate()

    cert = _load_cert(tmp_path / "crts" / "server.crt")
    expires_at = datetime.datetime.strptime(
        cert.get_notAfter().decode("utf-8"),
        "%Y%m%d%H%M%SZ",
    ).replace(tzinfo=datetime.UTC)
    now = datetime.datetime.now(datetime.UTC)

    assert datetime.timedelta(days=2, hours=23) < expires_at - now <= datetime.timedelta(days=3, minutes=1)


@pytest.mark.parametrize("value", ["0", "-1", "invalid"])
def test_certificate_validity_rejects_invalid_values(monkeypatch, tmp_path, value):
    monkeypatch.setattr(REvoDesign, "set_cache_dir", lambda: str(tmp_path))
    monkeypatch.setenv(CERT_VALIDITY_ENV, value)

    manager = SSLCertificateManager(role="server")

    with pytest.raises(ValueError, match=CERT_VALIDITY_ENV):
        manager.create_new_certificate()
