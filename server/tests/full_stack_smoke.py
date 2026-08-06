# Copyright (c) 2026 The REvoDesign Developers.
# Distributed under the terms of the GNU General Public License v3.0.
# SPDX-License-Identifier: GPL-3.0-only

from __future__ import annotations

import argparse
import io
import os
import time
import zipfile
from pathlib import Path

import requests


def _wait_for_server(session: requests.Session, base_url: str, timeout: float = 90.0) -> None:
    deadline = time.monotonic() + timeout
    last_error = "server did not respond"
    while time.monotonic() < deadline:
        try:
            response = session.get(f"{base_url}/compute/login", timeout=5)
            if response.status_code == 200:
                return
            last_error = f"login page returned HTTP {response.status_code}"
        except requests.RequestException as exc:
            last_error = str(exc)
        time.sleep(2)
    raise AssertionError(f"Server readiness timed out: {last_error}")


def _assert_page(
    session: requests.Session,
    base_url: str,
    path: str,
    expected_text: str,
    headers: dict[str, str] | None = None,
) -> None:
    response = session.get(f"{base_url}{path}", headers=headers, timeout=10)
    assert response.status_code == 200, f"GET {path} returned HTTP {response.status_code}: {response.text[:300]}"
    assert expected_text in response.text, f"GET {path} did not contain {expected_text!r}"


def _wait_for_task(
    session: requests.Session,
    base_url: str,
    task_id: str,
    headers: dict[str, str],
    timeout: float = 240.0,
) -> None:
    deadline = time.monotonic() + timeout
    last_payload: object = None
    while time.monotonic() < deadline:
        response = session.get(
            f"{base_url}/compute/api/running/{task_id}",
            headers=headers,
            timeout=10,
        )
        if response.status_code not in {200, 202}:
            raise AssertionError(f"GET running/{task_id} returned HTTP {response.status_code}: {response.text[:300]}")
        last_payload = response.json()
        if last_payload.get("status") == "finished":
            return
        if last_payload.get("status") == "failed":
            raise AssertionError(f"GREMLIN task failed: {last_payload}")
        time.sleep(5)
    raise AssertionError(f"GREMLIN task timed out; last status: {last_payload}")


def run_full_stack_checks(base_url: str, fasta_path: Path, admin_password: str) -> None:
    with requests.Session() as session:
        _wait_for_server(session, base_url)
        _assert_page(session, base_url, "/compute/login", "Sign in")

        login = session.post(
            f"{base_url}/compute/api/auth/login",
            json={"username": "admin", "password": admin_password},
            timeout=10,
        )
        assert login.status_code == 200, f"Admin login failed: {login.status_code} {login.text[:300]}"
        token = login.json()["token"]
        headers = {"Authorization": f"Bearer {token}"}

        me = session.get(f"{base_url}/compute/api/auth/me", headers=headers, timeout=10)
        assert me.status_code == 200
        assert me.json()["username"] == "admin"
        assert me.json()["role"] == "admin"

        users = session.get(f"{base_url}/compute/api/auth/admin/users", headers=headers, timeout=10)
        assert users.status_code == 200

        for path, marker in (
            ("/compute/dashboard", "PSSM GREMLIN Task Dashboard"),
            ("/compute/create_task", "Create PSSM GREMLIN Task"),
            ("/compute/profile", "Profile"),
            ("/compute/user_control", "User Control"),
        ):
            _assert_page(session, base_url, path, marker, headers)

        with fasta_path.open("rb") as handle:
            submitted = session.post(
                f"{base_url}/compute/api/post",
                headers=headers,
                files={"file": (fasta_path.name, handle, "text/plain")},
                allow_redirects=False,
                timeout=30,
            )
        assert submitted.status_code == 302, f"Task submission failed: {submitted.status_code} {submitted.text[:300]}"
        task_id = submitted.headers["Location"].rstrip("/").rsplit("/", 1)[-1]
        _wait_for_task(session, base_url, task_id, headers)

        results = session.get(
            f"{base_url}/compute/api/results/{task_id}",
            headers=headers,
            allow_redirects=False,
            timeout=10,
        )
        assert results.status_code == 302
        download_url = results.headers["Location"]
        if download_url.startswith("/"):
            download_url = f"{base_url}{download_url}"
        archive_response = session.get(download_url, headers=headers, timeout=30)
        assert archive_response.status_code == 200
        with zipfile.ZipFile(io.BytesIO(archive_response.content)) as archive:
            names = set(archive.namelist())
        assert any(name.endswith("log/task_finished") for name in names)
        assert any(name.endswith("gremlin_res/2KL8.i90c75_aln.GREMLIN.mrf.pkl") for name in names)
        assert any(name.endswith("pssm_msa/2KL8_ascii_mtx_file") for name in names)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--base-url", required=True)
    parser.add_argument("--fasta", required=True, type=Path)
    args = parser.parse_args()
    admin_password = os.environ.get("FULL_STACK_ADMIN_PASSWORD", "")
    if not admin_password:
        raise SystemExit("FULL_STACK_ADMIN_PASSWORD is required")
    run_full_stack_checks(args.base_url.rstrip("/"), args.fasta, admin_password)


if __name__ == "__main__":
    main()
