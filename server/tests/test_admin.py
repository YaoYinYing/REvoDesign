# Copyright (c) 2026 The REvoDesign Developers.
# Distributed under the terms of the GNU General Public License v3.0.
# SPDX-License-Identifier: GPL-3.0-only

from __future__ import annotations

import json

import pytest
from conftest import (
    _admin_client_auth,
    _extract_md5,
    _insert_pending_task,
    _load_pssm_module,
    _test_client_auth,
    _upsert_task_for_user,
)

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
            is_admin=True,
            registration_status="approved",
            user_status="active",
        )
        db.verify_email(user["id"])
    from pssm_gremlin_server.auth import generate_token

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

    resp = client.get("/PSSM_GREMLIN/api/auth/admin/users", headers=admin_header)
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
    resp = client.get("/PSSM_GREMLIN/api/auth/admin/users", headers=user_header)
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
        f"/PSSM_GREMLIN/api/auth/admin/users/{user['id']}",
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
        f"/PSSM_GREMLIN/api/auth/admin/users/{user['id']}",
        headers={**admin_header, "Content-Type": "application/json"},
        data=json.dumps({"user_status": "banned"}),
    )
    assert resp.status_code == 200
    updated = db.get_user(user["id"])
    assert updated["user_status"] == "banned"


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

    from pssm_gremlin_server.auth import generate_token

    old_bearer = {"Authorization": f"Bearer {generate_token(user['id'])}"}
    api_key = db.generate_api_key(user["id"])

    resp = client.put(
        f"/PSSM_GREMLIN/api/auth/admin/users/{user['id']}",
        headers={**admin_header, "Content-Type": "application/json"},
        data=json.dumps({"user_status": "banned"}),
    )
    assert resp.status_code == 200

    resp = client.post(
        "/PSSM_GREMLIN/api/auth/login",
        headers={"Content-Type": "application/json"},
        data=json.dumps({"username": "bancheck", "password": "pass1234"}),
    )
    assert resp.status_code == 403
    assert resp.json["error"] == "Account has been suspended"

    resp = client.get("/PSSM_GREMLIN/api/auth/me", headers=old_bearer)
    assert resp.status_code == 401
    assert resp.json["error"] == "Authentication required"

    resp = client.get("/PSSM_GREMLIN/api/auth/me", headers={"X-API-Key": api_key})
    assert resp.status_code == 401
    assert resp.json["error"] == "Authentication required"


def test_login_rate_limit_returns_retry_after_seconds(monkeypatch, tmp_path):
    """Login throttling returns a countdown value for the login page."""
    module = _load_pssm_module(monkeypatch, tmp_path, extra_env={"RUNNER_UID": "1234", "RUNNER_GID": "5678"})
    client = module.app.test_client()
    payload = {"username": "missing-user", "password": "wrong"}

    for _ in range(5):
        resp = client.post(
            "/PSSM_GREMLIN/api/auth/login",
            headers={"Content-Type": "application/json"},
            data=json.dumps(payload),
            environ_base={"REMOTE_ADDR": "198.51.100.77"},
        )
        assert resp.status_code == 401

    resp = client.post(
        "/PSSM_GREMLIN/api/auth/login",
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
        f"/PSSM_GREMLIN/api/auth/admin/users/{admin['id']}",
        headers={**admin_header, "Content-Type": "application/json"},
        data=json.dumps({"user_status": "banned"}),
    )
    assert resp.status_code == 400
    assert db.get_user(admin["id"])["user_status"] == "active"

    resp = client.delete(f"/PSSM_GREMLIN/api/auth/admin/users/{admin['id']}", headers=admin_header)
    assert resp.status_code == 400
    assert db.get_user(admin["id"])["deleted"] is False


def test_admin_update_rejects_invalid_status(monkeypatch, tmp_path):
    """PUT with invalid status values returns 400."""
    module = _load_pssm_module(monkeypatch, tmp_path, extra_env={"RUNNER_UID": "1234", "RUNNER_GID": "5678"})
    client = module.app.test_client()
    admin_header = _admin_client_auth(module)
    db = module.app.config["user_db"]
    user = db.create_user(username="target2", email="target2@test.local", password="pass1234")

    resp = client.put(
        f"/PSSM_GREMLIN/api/auth/admin/users/{user['id']}",
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

    resp = client.delete(f"/PSSM_GREMLIN/api/auth/admin/users/{user['id']}", headers=admin_header)
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
        "/PSSM_GREMLIN/api/auth/admin/users",
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


def test_register_with_affiliation_and_terms(monkeypatch, tmp_path):
    """Registration accepts affiliation and requires terms_agreed."""
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
    from pssm_gremlin_server.auth import _serializer

    client = module.app.test_client()
    db = module.app.config["user_db"]

    captcha_token: str = _serializer.dumps({"answer": 7, "purpose": "captcha"})

    # Registration with all fields
    resp = client.post(
        "/PSSM_GREMLIN/api/auth/register",
        headers={"Content-Type": "application/json"},
        data=json.dumps(
            {
                "username": "reguser",
                "email": "reg@test.local",
                "password": "regpass123",
                "affiliation": "Stanford",
                "terms_agreed": True,
                "captcha_token": captcha_token,
                "captcha_answer": "7",
            }
        ),
    )
    assert resp.status_code == 201
    user = db.get_user_by_username("reguser")
    assert user is not None
    assert user["affiliation"] == "Stanford"
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
    from pssm_gremlin_server.auth import _serializer

    client = module.app.test_client()

    captcha_token: str = _serializer.dumps({"answer": 7, "purpose": "captcha"})

    resp = client.post(
        "/PSSM_GREMLIN/api/auth/register",
        headers={"Content-Type": "application/json"},
        data=json.dumps(
            {
                "username": "noterms",
                "email": "noterms@test.local",
                "password": "regpass123",
                "captcha_token": captcha_token,
                "captcha_answer": "7",
            }
        ),
    )
    assert resp.status_code == 400
    data = json.loads(resp.text)
    assert "Terms of Service" in data.get("error", "")


def test_user_control_page_requires_admin(monkeypatch, tmp_path):
    """GET /PSSM_GREMLIN/user_control returns 403 for non-admin."""
    module = _load_pssm_module(monkeypatch, tmp_path, extra_env={"RUNNER_UID": "1234", "RUNNER_GID": "5678"})
    client = module.app.test_client()

    admin_header = _admin_client_auth(module)
    user_header = _test_client_auth(module)

    resp = client.get("/PSSM_GREMLIN/user_control", headers=admin_header)
    assert resp.status_code == 200
    assert b"User Control" in resp.data or b"user_control" in resp.data or b"User Management" in resp.data

    resp = client.get("/PSSM_GREMLIN/user_control", headers=user_header)
    assert resp.status_code == 403


def test_user_verify_endpoint(monkeypatch, tmp_path):
    """GET /PSSM_GREMLIN/user_verify validates token and sets verified status."""
    module = _load_pssm_module(monkeypatch, tmp_path, extra_env={"RUNNER_UID": "1234", "RUNNER_GID": "5678"})
    db = module.app.config["user_db"]

    user = db.create_user(username="verifyme", email="verify@test.local", password="pass1234")
    from pssm_gremlin_server.auth import _serializer

    token = _serializer.dumps({"uid": user["id"], "purpose": "verify-email"})
    client = module.app.test_client()

    resp = client.get(f"/PSSM_GREMLIN/user_verify?c={token}")
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
        "/PSSM_GREMLIN/api/auth/admin/users/batch",
        headers={**admin_header, "Content-Type": "application/json"},
        data=json.dumps({"action": "disable", "user_ids": ids}),
    )
    assert resp.status_code == 200
    assert db.get_user(u1["id"])["user_status"] == "banned"
    assert db.get_user(u2["id"])["user_status"] == "banned"

    # Batch enable
    resp = client.post(
        "/PSSM_GREMLIN/api/auth/admin/users/batch",
        headers={**admin_header, "Content-Type": "application/json"},
        data=json.dumps({"action": "enable", "user_ids": ids}),
    )
    assert resp.status_code == 200
    assert db.get_user(u1["id"])["user_status"] == "active"
    assert db.get_user(u1["id"])["registration_status"] == "approved"

    # Batch delete (soft)
    resp = client.post(
        "/PSSM_GREMLIN/api/auth/admin/users/batch",
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
        "/PSSM_GREMLIN/api/auth/admin/users/batch",
        headers={**admin_header, "Content-Type": "application/json"},
        data=json.dumps({"action": "disable", "user_ids": [admin["id"], user["id"]]}),
    )
    assert resp.status_code == 200
    assert resp.json["count"] == 1
    assert db.get_user(admin["id"])["user_status"] == "active"
    assert db.get_user(user["id"])["user_status"] == "banned"

    resp = client.post(
        "/PSSM_GREMLIN/api/auth/admin/users/batch",
        headers={**admin_header, "Content-Type": "application/json"},
        data=json.dumps({"action": "delete", "user_ids": [admin["id"], user["id"]]}),
    )
    assert resp.status_code == 200
    assert resp.json["count"] == 1
    assert db.get_user(admin["id"])["deleted"] is False
    assert db.get_user(user["id"])["deleted"] is True


def test_bootstrap_admin_has_correct_statuses(monkeypatch, tmp_path):
    """First-run bootstrap admin gets approved+active statuses."""
    module = _load_pssm_module(monkeypatch, tmp_path, extra_env={"RUNNER_UID": "1234", "RUNNER_GID": "5678"})
    db = module.app.config["user_db"]
    # The module's bootstrap code should have created 'admin' already
    admin = db.get_user_by_username("admin")
    assert admin is not None
    assert admin["registration_status"] == "approved"
    assert admin["user_status"] == "active"
    assert admin["is_admin"] is True


# ==================================================================
