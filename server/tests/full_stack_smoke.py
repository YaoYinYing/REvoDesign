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


def _wait_for_archive(
    session: requests.Session,
    base_url: str,
    task_id: str,
    headers: dict[str, str],
    timeout: float = 120.0,
) -> str:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        response = session.get(f"{base_url}/compute/api/results/{task_id}", headers=headers, timeout=10)
        assert response.status_code == 200, response.text[:300]
        archive = response.json()["archive"]
        if archive["ready"]:
            return archive["download_url"]
        time.sleep(2)
    raise AssertionError(f"Optional archive for {task_id} was not ready after {timeout:g} seconds")


def run_full_stack_checks(base_url: str, fasta_path: Path, admin_username: str, admin_password: str) -> None:
    with requests.Session() as session:
        _wait_for_server(session, base_url)
        _assert_page(session, base_url, "/compute/login", "Sign in")

        login = session.post(
            f"{base_url}/compute/api/auth/login",
            json={"username": admin_username, "password": admin_password},
            timeout=10,
        )
        assert login.status_code == 200, f"Admin login failed: {login.status_code} {login.text[:300]}"
        token = login.json()["token"]
        headers = {"Authorization": f"Bearer {token}"}

        me = session.get(f"{base_url}/compute/api/auth/me", headers=headers, timeout=10)
        assert me.status_code == 200
        assert me.json()["username"] == admin_username
        assert me.json()["role"] == "admin"

        users = session.get(f"{base_url}/compute/api/auth/admin/users", headers=headers, timeout=10)
        assert users.status_code == 200

        for path, marker in (
            ("/compute/dashboard", "REvoCompute Task Dashboard"),
            ("/compute/create_task", "Create Compute Task"),
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
        assert results.status_code == 200, results.text[:300]
        manifest = results.json()
        artifacts = manifest["artifacts"]
        paths = {artifact["path"] for artifact in artifacts}
        assert any(path.endswith("log/task_finished") for path in paths)
        assert any(path.endswith("gremlin_res/2KL8.i90c75_aln.GREMLIN.mrf.pkl") for path in paths)
        assert any(path.endswith("pssm_msa/2KL8_ascii_mtx_file") for path in paths)

        artifact = next(item for item in artifacts if item["path"].endswith("pssm_msa/2KL8_ascii_mtx_file"))
        artifact_url = artifact["url"]
        if artifact_url.startswith("/"):
            artifact_url = f"{base_url}{artifact_url}"
        head_response = session.head(artifact_url, headers=headers, timeout=30)
        assert head_response.status_code == 200
        assert int(head_response.headers.get("Content-Length", "0")) > 0
        range_headers = dict(headers)
        range_headers["Range"] = "bytes=0-0"
        range_response = session.get(artifact_url, headers=range_headers, timeout=30)
        assert range_response.status_code == 206
        assert range_response.content and len(range_response.content) == 1
        assert range_response.headers.get("Content-Range", "").startswith("bytes 0-0/")

        archive_request = session.post(
            f"{base_url}/compute/api/results/{task_id}/archive",
            headers=headers,
            timeout=10,
        )
        assert archive_request.status_code in {200, 202}, archive_request.text[:300]
        download_url = _wait_for_archive(session, base_url, task_id, headers)
        if download_url.startswith("/"):
            download_url = f"{base_url}{download_url}"
        archive_response = session.get(download_url, headers=headers, timeout=30)
        assert archive_response.status_code == 200
        with zipfile.ZipFile(io.BytesIO(archive_response.content)) as archive:
            names = set(archive.namelist())
        assert paths <= names
        assert "manifest.json" in names


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--base-url", required=True)
    parser.add_argument("--fasta", required=True, type=Path)
    args = parser.parse_args()
    admin_username = os.environ.get("FULL_STACK_ADMIN_USERNAME", "admin")
    admin_password = os.environ.get("FULL_STACK_ADMIN_PASSWORD", "")
    if not admin_password:
        raise SystemExit("FULL_STACK_ADMIN_PASSWORD is required")
    run_full_stack_checks(args.base_url.rstrip("/"), args.fasta, admin_username, admin_password)


if __name__ == "__main__":
    main()
