# Copyright (c) 2026 The REvoDesign Developers.
# Distributed under the terms of the GNU General Public License v3.0.
# SPDX-License-Identifier: GPL-3.0-only

from __future__ import annotations

import inspect
import json
import os
import zipfile
from pathlib import Path

import pytest
from conftest import _load_pssm_module, _test_client_auth

# Admin user control helpers
# ==================================================================


def _admin_client_auth(module, username: str = "sysadmin") -> dict[str, str]:
    """Create an admin user and return Bearer token headers."""
    db = module.app.config["user_db"]
    user = db.get_user_by_username(username)
    if not user:
        user = db.create_user(
            username=username,
            email=f"{username}@test.local",
            password="admin_password",
            role="admin",
            registration_status="approved",
            user_status="active",
        )
        db.verify_email(user["id"])
    from revocompute.auth import generate_token

    return {"Authorization": f"Bearer {generate_token(user['id'])}"}


# ==================================================================
# Admin user management tests
# ==================================================================


def test_admin_can_list_users(monkeypatch, tmp_path):
    """Admin GET /api/auth/admin/users returns all users with safe fields."""
    module = _load_pssm_module(monkeypatch, tmp_path, extra_env={"RUNNER_UID": "1234", "RUNNER_GID": "5678"})
    client = module.app.test_client()
    admin_header = _admin_client_auth(module)
    db = module.app.config["user_db"]

    # Create a regular user too
    db.create_user(username="regular", email="regular@test.local", password="pass1234")

    resp = client.get("/compute/api/auth/admin/users", headers=admin_header)
    assert resp.status_code == 200
    data = json.loads(resp.text)
    assert "users" in data
    assert len(data["users"]) >= 2

    # Safe fields present, sensitive fields absent
    for u in data["users"]:
        assert "password_hash" not in u
        assert "api_key_hash" not in u
        assert "id" in u
        assert "email" in u
        assert "registration_status" in u
        assert "user_status" in u


def test_non_admin_cannot_list_users(monkeypatch, tmp_path):
    """Regular user gets 403 on GET /api/auth/admin/users."""
    module = _load_pssm_module(monkeypatch, tmp_path, extra_env={"RUNNER_UID": "1234", "RUNNER_GID": "5678"})
    client = module.app.test_client()
    user_header = _test_client_auth(module)
    resp = client.get("/compute/api/auth/admin/users", headers=user_header)
    assert resp.status_code == 403


def test_admin_can_update_user_status(monkeypatch, tmp_path):
    """Admin can approve/reject/ban a user via PUT."""
    module = _load_pssm_module(monkeypatch, tmp_path, extra_env={"RUNNER_UID": "1234", "RUNNER_GID": "5678"})
    client = module.app.test_client()
    admin_header = _admin_client_auth(module)
    db = module.app.config["user_db"]

    user = db.create_user(username="target", email="target@test.local", password="pass1234")

    # Approve registration
    resp = client.put(
        f"/compute/api/auth/admin/users/{user['id']}",
        headers={**admin_header, "Content-Type": "application/json"},
        data=json.dumps({"registration_status": "approved", "user_status": "active"}),
    )
    assert resp.status_code == 200
    updated = db.get_user(user["id"])
    assert updated["registration_status"] == "approved"
    assert updated["user_status"] == "active"
    assert updated["approved_by"] is not None

    # Ban user
    resp = client.put(
        f"/compute/api/auth/admin/users/{user['id']}",
        headers={**admin_header, "Content-Type": "application/json"},
        data=json.dumps({"user_status": "banned"}),
    )
    assert resp.status_code == 200
    updated = db.get_user(user["id"])
    assert updated["user_status"] == "banned"


@pytest.mark.parametrize(
    ("registration_status", "sender_name", "warning"),
    (
        ("approved", "send_approval_email", "Approval email failed for"),
        ("rejected", "send_rejection_email", "Rejection email failed for"),
    ),
)
def test_admin_notification_failure_logs_user_id_not_email(
    monkeypatch,
    tmp_path,
    caplog,
    registration_status,
    sender_name,
    warning,
):
    module = _load_pssm_module(monkeypatch, tmp_path, extra_env={"RUNNER_UID": "1234", "RUNNER_GID": "5678"})
    db = module.app.config["user_db"]
    user = db.create_user(username=f"{registration_status}_target", email="private@test.local", password="pass1234")
    route_globals = inspect.unwrap(module.app.view_functions["admin_manage_user"]).__globals__
    monkeypatch.setitem(route_globals, sender_name, lambda _user: False)

    route_globals["_notify_admin_user_update"](db, user["id"], user, registration_status)

    assert caplog.messages[-1] == f"{warning} {user['id']!r}"
    assert user["email"] not in caplog.text


def test_banned_user_cannot_authenticate_with_existing_credentials(monkeypatch, tmp_path):
    """Banning a user invalidates login, old Bearer tokens, and API keys."""
    module = _load_pssm_module(monkeypatch, tmp_path, extra_env={"RUNNER_UID": "1234", "RUNNER_GID": "5678"})
    client = module.app.test_client()
    admin_header = _admin_client_auth(module)
    db = module.app.config["user_db"]
    user = db.create_user(
        username="bancheck",
        email="bancheck@test.local",
        password="pass1234",
        registration_status="approved",
        user_status="active",
    )
    db.verify_email(user["id"])

    from revocompute.auth import generate_token

    old_bearer = {"Authorization": f"Bearer {generate_token(user['id'])}"}
    api_key = db.generate_api_key(user["id"])

    resp = client.put(
        f"/compute/api/auth/admin/users/{user['id']}",
        headers={**admin_header, "Content-Type": "application/json"},
        data=json.dumps({"user_status": "banned"}),
    )
    assert resp.status_code == 200

    resp = client.post(
        "/compute/api/auth/login",
        headers={"Content-Type": "application/json"},
        data=json.dumps({"username": "bancheck", "password": "pass1234"}),
    )
    assert resp.status_code == 403
    assert resp.json["error"] == "Account has been suspended"

    resp = client.get("/compute/api/auth/me", headers=old_bearer)
    assert resp.status_code == 401
    assert resp.json["error"] == "Authentication required"

    resp = client.get("/compute/api/auth/me", headers={"X-API-Key": api_key})
    assert resp.status_code == 401
    assert resp.json["error"] == "Authentication required"


def test_login_rate_limit_returns_retry_after_seconds(monkeypatch, tmp_path):
    """Login throttling returns a countdown value for the login page."""
    module = _load_pssm_module(monkeypatch, tmp_path, extra_env={"RUNNER_UID": "1234", "RUNNER_GID": "5678"})
    client = module.app.test_client()
    payload = {"username": "missing-user", "password": "wrong"}

    for _ in range(5):
        resp = client.post(
            "/compute/api/auth/login",
            headers={"Content-Type": "application/json"},
            data=json.dumps(payload),
            environ_base={"REMOTE_ADDR": "198.51.100.77"},
        )
        assert resp.status_code == 401

    resp = client.post(
        "/compute/api/auth/login",
        headers={"Content-Type": "application/json"},
        data=json.dumps(payload),
        environ_base={"REMOTE_ADDR": "198.51.100.77"},
    )
    assert resp.status_code == 429
    assert resp.json["error"] == "Too many requests"
    assert isinstance(resp.json["retry_after_seconds"], int)
    assert resp.json["retry_after_seconds"] > 0


def test_admin_cannot_lock_out_self(monkeypatch, tmp_path):
    """Admin cannot ban or delete their own account."""
    module = _load_pssm_module(monkeypatch, tmp_path, extra_env={"RUNNER_UID": "1234", "RUNNER_GID": "5678"})
    client = module.app.test_client()
    admin_header = _admin_client_auth(module)
    db = module.app.config["user_db"]
    admin = db.get_user_by_username("sysadmin")
    assert admin is not None

    resp = client.put(
        f"/compute/api/auth/admin/users/{admin['id']}",
        headers={**admin_header, "Content-Type": "application/json"},
        data=json.dumps({"user_status": "banned"}),
    )
    assert resp.status_code == 400
    assert db.get_user(admin["id"])["user_status"] == "active"

    resp = client.delete(f"/compute/api/auth/admin/users/{admin['id']}", headers=admin_header)
    assert resp.status_code == 400
    assert db.get_user(admin["id"])["deleted"] is False


def test_admin_can_enable_own_gpu_access_with_unchanged_role(monkeypatch, tmp_path):
    """An unchanged self-role must not block an otherwise valid GPU update."""
    module = _load_pssm_module(monkeypatch, tmp_path, extra_env={"RUNNER_UID": "1234", "RUNNER_GID": "5678"})
    client = module.app.test_client()
    admin_header = _admin_client_auth(module)
    db = module.app.config["user_db"]
    admin = db.get_user_by_username("sysadmin")
    assert admin is not None
    assert admin["role"] == "admin"
    assert admin["allow_gpu_use"] is False

    response = client.put(
        f"/compute/api/auth/admin/users/{admin['id']}",
        headers={**admin_header, "Content-Type": "application/json"},
        data=json.dumps({"role": "admin", "allow_gpu_use": True}),
    )

    assert response.status_code == 200
    updated = db.get_user(admin["id"])
    assert updated["role"] == "admin"
    assert updated["allow_gpu_use"] is True

    listing = client.get("/compute/api/auth/admin/users", headers=admin_header)
    assert listing.status_code == 200
    serialized = next(user for user in listing.json["users"] if user["id"] == admin["id"])
    assert serialized["allow_gpu_use"] is True

    script = (Path(__file__).resolve().parents[1] / "revocompute" / "static" / "js" / "user-control.js").read_text(
        encoding="utf-8"
    )
    assert "if (self) delete payload.role;" in script


def test_admin_update_rejects_invalid_status(monkeypatch, tmp_path):
    """PUT with invalid status values returns 400."""
    module = _load_pssm_module(monkeypatch, tmp_path, extra_env={"RUNNER_UID": "1234", "RUNNER_GID": "5678"})
    client = module.app.test_client()
    admin_header = _admin_client_auth(module)
    db = module.app.config["user_db"]
    user = db.create_user(username="target2", email="target2@test.local", password="pass1234")

    resp = client.put(
        f"/compute/api/auth/admin/users/{user['id']}",
        headers={**admin_header, "Content-Type": "application/json"},
        data=json.dumps({"registration_status": "nonexistent"}),
    )
    assert resp.status_code == 400


def test_admin_can_delete_user(monkeypatch, tmp_path):
    """Admin DELETE soft-deletes a user (hides from list, record kept for audit)."""
    module = _load_pssm_module(monkeypatch, tmp_path, extra_env={"RUNNER_UID": "1234", "RUNNER_GID": "5678"})
    client = module.app.test_client()
    admin_header = _admin_client_auth(module)
    db = module.app.config["user_db"]
    user = db.create_user(username="deleteme", email="deleteme@test.local", password="pass1234")

    resp = client.delete(f"/compute/api/auth/admin/users/{user['id']}", headers=admin_header)
    assert resp.status_code == 200
    # Record still exists (soft-delete) but marked deleted
    deleted_user = db.get_user(user["id"])
    assert deleted_user is not None
    assert deleted_user["deleted"] is True
    # Hidden from list_users (excludes deleted by default)
    visible = db.list_users()
    visible_ids = {u["id"] for u in visible}
    assert user["id"] not in visible_ids


def test_admin_create_user_with_affiliation(monkeypatch, tmp_path):
    """Admin POST creates user with affiliation and correct default statuses."""
    module = _load_pssm_module(monkeypatch, tmp_path, extra_env={"RUNNER_UID": "1234", "RUNNER_GID": "5678"})
    client = module.app.test_client()
    admin_header = _admin_client_auth(module)
    db = module.app.config["user_db"]

    resp = client.post(
        "/compute/api/auth/admin/users",
        headers={**admin_header, "Content-Type": "application/json"},
        data=json.dumps(
            {"username": "affuser", "email": "aff@test.local", "password": "pass1234", "affiliation": "MIT"}
        ),
    )
    assert resp.status_code == 201
    user = db.get_user_by_username("affuser")
    assert user is not None
    assert user["affiliation"] == "MIT"
    assert user["registration_status"] == "approved"
    assert user["user_status"] == "active"
    assert user["email_verified"] is True


def test_admin_create_user_ignores_legacy_is_admin_input(monkeypatch, tmp_path):
    """Only role can grant admin access; the removed boolean input is inert."""
    module = _load_pssm_module(monkeypatch, tmp_path, extra_env={"RUNNER_UID": "1234", "RUNNER_GID": "5678"})
    client = module.app.test_client()
    admin_header = _admin_client_auth(module)
    db = module.app.config["user_db"]

    resp = client.post(
        "/compute/api/auth/admin/users",
        headers={**admin_header, "Content-Type": "application/json"},
        data=json.dumps(
            {
                "username": "legacyflag",
                "email": "legacy-flag@test.local",
                "password": "pass1234",
                "is_admin": True,
                "role": "user",
            }
        ),
    )
    assert resp.status_code == 201
    user = db.get_user_by_username("legacyflag")
    assert user is not None
    assert user["role"] == "user"
    assert "is_admin" not in user


def test_register_with_required_research_profile_and_terms(monkeypatch, tmp_path):
    """Registration stores the required research-profile fields."""
    module = _load_pssm_module(
        monkeypatch,
        tmp_path,
        extra_env={
            "RUNNER_UID": "1234",
            "RUNNER_GID": "5678",
            "ENABLE_REGISTER": "true",
            "SMTP_HOST": "localhost",
        },
    )
    from revocompute.auth import _serializer

    client = module.app.test_client()
    db = module.app.config["user_db"]

    captcha_token: str = _serializer.dumps({"answer": 7, "purpose": "captcha"})

    # Registration with all fields
    resp = client.post(
        "/compute/api/auth/register",
        headers={"Content-Type": "application/json"},
        data=json.dumps(
            {
                "username": "reguser",
                "email": "reg@test.local",
                "password": "regpass123",
                "full_name": "Ada Researcher",
                "affiliation": "Stanford",
                "position": "phd_student",
                "pi_name": "Prof. Grace Hopper",
                "terms_agreed": True,
                "captcha_token": captcha_token,
                "captcha_answer": "7",
            }
        ),
    )
    assert resp.status_code == 201
    user = db.get_user_by_username("reguser")
    assert user is not None
    assert user["full_name"] == "Ada Researcher"
    assert user["affiliation"] == "Stanford"
    assert user["position"] == "phd_student"
    assert user["pi_name"] == "Prof. Grace Hopper"
    assert user["terms_agreed"] is True
    assert user["registration_status"] == "email_sent"
    assert user["user_status"] == "pending"
    assert user["email_verified"] is False


def test_register_rejects_without_terms(monkeypatch, tmp_path):
    """Registration without terms_agreed returns 400."""
    module = _load_pssm_module(
        monkeypatch,
        tmp_path,
        extra_env={
            "RUNNER_UID": "1234",
            "RUNNER_GID": "5678",
            "ENABLE_REGISTER": "true",
            "SMTP_HOST": "localhost",
        },
    )
    from revocompute.auth import _serializer

    client = module.app.test_client()

    captcha_token: str = _serializer.dumps({"answer": 7, "purpose": "captcha"})

    resp = client.post(
        "/compute/api/auth/register",
        headers={"Content-Type": "application/json"},
        data=json.dumps(
            {
                "username": "noterms",
                "email": "noterms@test.local",
                "password": "regpass123",
                "full_name": "No Terms",
                "affiliation": "Example University",
                "position": "undergraduate_student",
                "pi_name": "Example Supervisor",
                "captcha_token": captcha_token,
                "captcha_answer": "7",
            }
        ),
    )
    assert resp.status_code == 400
    data = json.loads(resp.text)
    assert "Terms of Service" in data.get("error", "")


def test_register_rejects_missing_research_profile(monkeypatch, tmp_path):
    """Self-registration requires name, affiliation, position, and PI name."""
    module = _load_pssm_module(
        monkeypatch,
        tmp_path,
        extra_env={
            "RUNNER_UID": "1234",
            "RUNNER_GID": "5678",
            "ENABLE_REGISTER": "true",
            "SMTP_HOST": "localhost",
        },
    )
    from revocompute.auth import _serializer

    client = module.app.test_client()
    captcha_token: str = _serializer.dumps({"answer": 7, "purpose": "captcha"})
    resp = client.post(
        "/compute/api/auth/register",
        json={
            "username": "missingprofile",
            "email": "missing@test.local",
            "password": "regpass123",
            "terms_agreed": True,
            "captcha_token": captcha_token,
            "captcha_answer": "7",
        },
    )

    assert resp.status_code == 400
    assert module.app.config["user_db"].get_user_by_username("missingprofile") is None


def test_user_control_page_requires_admin(monkeypatch, tmp_path):
    """GET /compute/user_control returns 403 for non-admin."""
    module = _load_pssm_module(monkeypatch, tmp_path, extra_env={"RUNNER_UID": "1234", "RUNNER_GID": "5678"})
    client = module.app.test_client()

    admin_header = _admin_client_auth(module)
    user_header = _test_client_auth(module)

    resp = client.get("/compute/user_control", headers=admin_header)
    assert resp.status_code == 200
    assert b"User Control" in resp.data or b"user_control" in resp.data or b"User Management" in resp.data

    resp = client.get("/compute/user_control", headers=user_header)
    assert resp.status_code == 403


def test_log_viewer_page_requires_admin(monkeypatch, tmp_path):
    module = _load_pssm_module(
        monkeypatch,
        tmp_path,
        extra_env={"RUNNER_UID": "1234", "RUNNER_GID": "5678"},
    )
    client = module.app.test_client()

    response = client.get(
        "/compute/logs",
        headers=_admin_client_auth(module),
    )
    assert response.status_code == 200
    assert b"Gunicorn access" in response.data
    assert b"Maintenance" in response.data
    assert b"/static/js/log-viewer.js" in response.data

    response = client.get(
        "/compute/dashboard",
        headers=_admin_client_auth(module),
    )
    assert response.status_code == 200
    assert b'href="/compute/logs"' in response.data

    response = client.get(
        "/compute/logs",
        headers=_test_client_auth(module),
    )
    assert response.status_code == 403


@pytest.mark.parametrize(
    ("log_name", "filename"),
    [
        ("gunicorn-access", "gunicorn-access.log"),
        ("gunicorn-error", "gunicorn-error.log"),
        ("celery-worker", "celery-worker.log"),
        ("maintenance", "maintenance.log"),
    ],
)
def test_admin_can_stream_fixed_server_logs(monkeypatch, tmp_path, log_name, filename):
    module = _load_pssm_module(
        monkeypatch,
        tmp_path,
        extra_env={"RUNNER_UID": "1234", "RUNNER_GID": "5678"},
    )
    content = f"{filename}: first\n{filename}: second\n".encode()
    log_dir = os.environ["LOG_DIR"]
    with open(os.path.join(log_dir, filename), "wb") as handle:
        handle.write(content)

    response = module.app.test_client().get(
        f"/compute/api/auth/admin/logs/{log_name}",
        headers=_admin_client_auth(module),
        buffered=False,
    )

    assert response.status_code == 200
    assert response.is_streamed
    assert b"".join(response.response) == content
    assert response.headers["Cache-Control"] == "no-store"


def test_server_log_stream_rejects_non_admin_and_unknown_names(monkeypatch, tmp_path):
    module = _load_pssm_module(
        monkeypatch,
        tmp_path,
        extra_env={"RUNNER_UID": "1234", "RUNNER_GID": "5678"},
    )
    client = module.app.test_client()

    response = client.get(
        "/compute/api/auth/admin/logs/maintenance",
        headers=_test_client_auth(module),
    )
    assert response.status_code == 403

    response = client.get(
        "/compute/api/auth/admin/logs/not-a-log",
        headers=_admin_client_auth(module),
    )
    assert response.status_code == 404


def test_admin_can_list_and_download_rotated_logs(monkeypatch, tmp_path):
    module = _load_pssm_module(
        monkeypatch,
        tmp_path,
        extra_env={"RUNNER_UID": "1234", "RUNNER_GID": "5678"},
    )
    log_dir = os.environ["LOG_DIR"]
    archive_name = "maintenance.log.20260729T000000000000Z.zip"
    archive_path = os.path.join(log_dir, archive_name)
    with zipfile.ZipFile(archive_path, "w") as archive:
        archive.writestr("maintenance.log", "rotated entry\n")
    with open(os.path.join(log_dir, "unrelated.zip"), "wb") as handle:
        handle.write(b"not managed")

    client = module.app.test_client()
    admin_header = _admin_client_auth(module)
    response = client.get(
        "/compute/api/auth/admin/logs/archives",
        headers=admin_header,
    )

    assert response.status_code == 200
    groups = {group["id"]: group for group in response.get_json()["logs"]}
    assert [item["filename"] for item in groups["maintenance"]["archives"]] == [archive_name]
    assert all(item["filename"] != "unrelated.zip" for group in groups.values() for item in group["archives"])

    response = client.get(
        f"/compute/api/auth/admin/logs/archives/{archive_name}",
        headers=admin_header,
    )
    assert response.status_code == 200
    assert response.data.startswith(b"PK")
    assert "attachment" in response.headers["Content-Disposition"]
    assert response.headers["Cache-Control"] == "no-store"


def test_rotated_log_endpoints_reject_non_admin_and_unmanaged_files(monkeypatch, tmp_path):
    module = _load_pssm_module(
        monkeypatch,
        tmp_path,
        extra_env={"RUNNER_UID": "1234", "RUNNER_GID": "5678"},
    )
    client = module.app.test_client()

    response = client.get(
        "/compute/api/auth/admin/logs/archives",
        headers=_test_client_auth(module),
    )
    assert response.status_code == 403

    response = client.get(
        "/compute/api/auth/admin/logs/archives/unrelated.zip",
        headers=_admin_client_auth(module),
    )
    assert response.status_code == 404


def test_user_verify_endpoint(monkeypatch, tmp_path):
    """GET /compute/user_verify validates token and sets verified status."""
    module = _load_pssm_module(monkeypatch, tmp_path, extra_env={"RUNNER_UID": "1234", "RUNNER_GID": "5678"})
    db = module.app.config["user_db"]

    user = db.create_user(username="verifyme", email="verify@test.local", password="pass1234")
    from revocompute.auth import _serializer

    token = _serializer.dumps({"uid": user["id"], "purpose": "verify-email"})
    client = module.app.test_client()

    resp = client.get(f"/compute/user_verify?c={token}")
    assert resp.status_code == 200
    assert b"verified" in resp.data.lower() or b"success" in resp.data.lower()

    updated = db.get_user(user["id"])
    assert updated["email_verified"] is True
    assert updated["registration_status"] == "verified"


def test_admin_batch_operations(monkeypatch, tmp_path):
    """Admin can batch enable, disable, and delete users."""
    module = _load_pssm_module(monkeypatch, tmp_path, extra_env={"RUNNER_UID": "1234", "RUNNER_GID": "5678"})
    client = module.app.test_client()
    admin_header = _admin_client_auth(module)
    db = module.app.config["user_db"]

    u1 = db.create_user(username="batch1", email="batch1@test.local", password="pass1234")
    u2 = db.create_user(username="batch2", email="batch2@test.local", password="pass1234")
    ids = [u1["id"], u2["id"]]

    # Batch disable
    resp = client.post(
        "/compute/api/auth/admin/users/batch",
        headers={**admin_header, "Content-Type": "application/json"},
        data=json.dumps({"action": "disable", "user_ids": ids}),
    )
    assert resp.status_code == 200
    assert db.get_user(u1["id"])["user_status"] == "banned"
    assert db.get_user(u2["id"])["user_status"] == "banned"

    # Batch enable
    resp = client.post(
        "/compute/api/auth/admin/users/batch",
        headers={**admin_header, "Content-Type": "application/json"},
        data=json.dumps({"action": "enable", "user_ids": ids}),
    )
    assert resp.status_code == 200
    assert db.get_user(u1["id"])["user_status"] == "active"
    assert db.get_user(u1["id"])["registration_status"] == "approved"

    # Batch delete (soft)
    resp = client.post(
        "/compute/api/auth/admin/users/batch",
        headers={**admin_header, "Content-Type": "application/json"},
        data=json.dumps({"action": "delete", "user_ids": ids}),
    )
    assert resp.status_code == 200
    assert db.get_user(u1["id"])["deleted"] is True
    assert db.get_user(u2["id"])["deleted"] is True


def test_admin_batch_operations_skip_self_lockout(monkeypatch, tmp_path):
    """Batch disable/delete skips the acting admin account."""
    module = _load_pssm_module(monkeypatch, tmp_path, extra_env={"RUNNER_UID": "1234", "RUNNER_GID": "5678"})
    client = module.app.test_client()
    admin_header = _admin_client_auth(module)
    db = module.app.config["user_db"]
    admin = db.get_user_by_username("sysadmin")
    assert admin is not None
    user = db.create_user(username="batch_target", email="batch_target@test.local", password="pass1234")

    resp = client.post(
        "/compute/api/auth/admin/users/batch",
        headers={**admin_header, "Content-Type": "application/json"},
        data=json.dumps({"action": "disable", "user_ids": [admin["id"], user["id"]]}),
    )
    assert resp.status_code == 200
    assert resp.json["count"] == 1
    assert db.get_user(admin["id"])["user_status"] == "active"
    assert db.get_user(user["id"])["user_status"] == "banned"

    resp = client.post(
        "/compute/api/auth/admin/users/batch",
        headers={**admin_header, "Content-Type": "application/json"},
        data=json.dumps({"action": "delete", "user_ids": [admin["id"], user["id"]]}),
    )
    assert resp.status_code == 200
    assert resp.json["count"] == 1
    assert db.get_user(admin["id"])["deleted"] is False
    assert db.get_user(user["id"])["deleted"] is True


def test_bootstrap_admin_has_correct_statuses(monkeypatch, tmp_path):
    """Every first-run bootstrap admin gets approved+active statuses."""
    module = _load_pssm_module(
        monkeypatch,
        tmp_path,
        extra_env={
            "RUNNER_UID": "1234",
            "RUNNER_GID": "5678",
            "ADMIN_USERS": "admin,group_admin",
            "ADMIN_BOOTSTRAP_CREDENTIALS": ("admin\ttest-admin-password\n" "group_admin\ttest-group-admin-password"),
        },
    )
    db = module.app.config["user_db"]
    for username in ("admin", "group_admin"):
        admin = db.get_user_by_username(username)
        assert admin is not None
        assert admin["registration_status"] == "approved"
        assert admin["user_status"] == "active"
        assert admin["role"] == "admin"


# ==================================================================
def test_configuration_page_script_initializes_theme_and_admin_data(monkeypatch, tmp_path):
    module = _load_pssm_module(monkeypatch, tmp_path, extra_env={"RUNNER_UID": "1234", "RUNNER_GID": "5678"})
    client = module.app.test_client()
    admin_header = _admin_client_auth(module)

    page = client.get("/compute/configuration", headers=admin_header)
    assert page.status_code == 200
    response = client.get("/compute/api/auth/admin/config", headers=admin_header)
    assert response.status_code == 200
    assert response.json["task_types"]
    assert "resources" in response.json

    script = (Path(__file__).resolve().parents[1] / "revocompute" / "static" / "js" / "configuration.js").read_text(
        encoding="utf-8"
    )
    assert "var T = window.REvoDesignTheme;" in script
    assert "T.initToggle" in script
    assert "init();" in script


def test_admin_resource_api_returns_effective_policy_and_validates_updates(monkeypatch, tmp_path):
    module = _load_pssm_module(monkeypatch, tmp_path, extra_env={"RUNNER_UID": "1234", "RUNNER_GID": "5678"})
    client = module.app.test_client()
    admin_header = _admin_client_auth(module)

    updated = client.put(
        "/compute/api/auth/admin/config",
        headers=admin_header,
        json={"task_types": [{"tool": "gremlin", "cpus": 8, "memory": "16G", "max_runtime_seconds": 3600}]},
    )
    assert updated.status_code == 200
    payload = client.get("/compute/api/auth/admin/config", headers=admin_header).get_json()
    gremlin = next(item for item in payload["task_types"] if item["tool"] == "gremlin")
    assert gremlin["effective_resources"]["cpus"] == 8
    assert gremlin["effective_resources"]["memory"] == "16G"
    assert gremlin["effective_resources"]["slurm_time"] == "01:00:00"
    assert gremlin["resource_error"] is None

    invalid = client.put(
        "/compute/api/auth/admin/config",
        headers=admin_header,
        json={"task_types": [{"tool": "gremlin", "cpus": 0}]},
    )
    assert invalid.status_code == 400
    assert "positive integer" in invalid.get_json()["error"]
    mixed_invalid = client.put(
        "/compute/api/auth/admin/config",
        headers=admin_header,
        json={"task_types": [{"tool": "gremlin", "cpus": 4, "memory": "unbounded"}]},
    )
    assert mixed_invalid.status_code == 400
    unchanged = client.get("/compute/api/auth/admin/config", headers=admin_header).get_json()
    gremlin = next(item for item in unchanged["task_types"] if item["tool"] == "gremlin")
    assert gremlin["cpus"] == 8
    assert gremlin["memory"] == "16G"

    unknown = client.put(
        "/compute/api/auth/admin/config",
        headers=admin_header,
        json={"resources": {"unused_setting": "1"}},
    )
    assert unknown.status_code == 400

    allowed = client.put(
        "/compute/api/auth/admin/config",
        headers=admin_header,
        json={"slurm": {"allowed_queues": ["normal", "gpu"]}},
    )
    assert allowed.status_code == 200
    forbidden_partition = client.put(
        "/compute/api/auth/admin/config",
        headers=admin_header,
        json={"task_types": [{"tool": "gremlin", "slurm_partition": "debug"}]},
    )
    assert forbidden_partition.status_code == 400
    assert "allowed_queues" in forbidden_partition.get_json()["error"]
