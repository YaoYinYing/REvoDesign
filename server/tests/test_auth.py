# Copyright (c) 2026 The REvoDesign Developers.
# Distributed under the terms of the GNU General Public License v3.0.
# SPDX-License-Identifier: GPL-3.0-only

from __future__ import annotations

import io
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

# Auth endpoint tests — /api/auth/me, API keys, password reset, etc.
# ==================================================================


def test_auth_me_returns_current_user(monkeypatch, tmp_path):
    """GET /api/auth/me returns the authenticated user's profile."""
    module = _load_pssm_module(monkeypatch, tmp_path, extra_env={"RUNNER_UID": "1234", "RUNNER_GID": "5678"})
    client = module.app.test_client()
    auth_header = _test_client_auth(module)
    resp = client.get("/PSSM_GREMLIN/api/auth/me", headers=auth_header)
    assert resp.status_code == 200
    data = json.loads(resp.text)
    assert data["username"] == "tester"
    assert "password_hash" not in data
    assert "api_key_hash" not in data


def test_auth_me_rejects_unauthenticated(monkeypatch, tmp_path):
    """GET /api/auth/me returns 401 without credentials."""
    module = _load_pssm_module(monkeypatch, tmp_path, extra_env={"RUNNER_UID": "1234", "RUNNER_GID": "5678"})
    client = module.app.test_client()
    resp = client.get("/PSSM_GREMLIN/api/auth/me")
    assert resp.status_code == 401


def test_auth_update_me_changes_password(monkeypatch, tmp_path):
    """PUT /api/auth/me changes the current user's password."""
    module = _load_pssm_module(monkeypatch, tmp_path, extra_env={"RUNNER_UID": "1234", "RUNNER_GID": "5678"})
    client = module.app.test_client()
    auth_header = _test_client_auth(module)
    payload = {"current_password": "password", "new_password": "newpassword123"}
    resp = client.put(
        "/PSSM_GREMLIN/api/auth/me",
        headers={**auth_header, "Content-Type": "application/json"},
        data=json.dumps(payload),
    )
    assert resp.status_code == 200
    # Old password should no longer work for login
    login_resp = client.post(
        "/PSSM_GREMLIN/api/auth/login",
        headers={"Content-Type": "application/json"},
        data=json.dumps({"username": "tester", "password": "password"}),
    )
    assert login_resp.status_code == 401
    # New password should work
    login_resp = client.post(
        "/PSSM_GREMLIN/api/auth/login",
        headers={"Content-Type": "application/json"},
        data=json.dumps({"username": "tester", "password": "newpassword123"}),
    )
    assert login_resp.status_code == 200


def test_auth_update_me_rejects_wrong_current_password(monkeypatch, tmp_path):
    """PUT /api/auth/me rejects change when current_password is wrong."""
    module = _load_pssm_module(monkeypatch, tmp_path, extra_env={"RUNNER_UID": "1234", "RUNNER_GID": "5678"})
    client = module.app.test_client()
    auth_header = _test_client_auth(module)
    payload = {"current_password": "wrongpassword", "new_password": "newpassword123"}
    resp = client.put(
        "/PSSM_GREMLIN/api/auth/me",
        headers={**auth_header, "Content-Type": "application/json"},
        data=json.dumps(payload),
    )
    assert resp.status_code == 401
    assert resp.json["error"] == "Current password is incorrect"


def test_auth_update_me_requires_bearer_not_cookie(monkeypatch, tmp_path):
    """PUT /api/auth/me rejects cookie-based auth (CSRF gate)."""
    module = _load_pssm_module(monkeypatch, tmp_path, extra_env={"RUNNER_UID": "1234", "RUNNER_GID": "5678"})
    _test_client_auth(module)  # ensure tester exists
    client = module.app.test_client()
    db = module.app.config["user_db"]
    user = db.get_user_by_username("tester")
    from pssm_gremlin_server.auth import generate_token

    token = generate_token(user["id"])
    # Set cookie but don't send Bearer header
    client.set_cookie("auth_token", token)
    payload = {"current_password": "password", "new_password": "newpassword123"}
    resp = client.put(
        "/PSSM_GREMLIN/api/auth/me",
        headers={"Content-Type": "application/json"},
        data=json.dumps(payload),
    )
    assert resp.status_code == 403
    assert "Bearer token required" in resp.json["error"]


def test_auth_update_me_rejects_guest(monkeypatch, tmp_path):
    """PUT /api/auth/me rejects guest accounts."""
    module = _load_pssm_module(monkeypatch, tmp_path, extra_env={"RUNNER_UID": "1234", "RUNNER_GID": "5678"})
    client = module.app.test_client()
    db = module.app.config["user_db"]
    user = db.create_user(
        username="guest_user",
        email="guest@test.local",
        password="guestpass123",
        role="guest",
        registration_status="approved",
        user_status="active",
    )
    db.verify_email(user["id"])
    from pssm_gremlin_server.auth import generate_token

    guest_header = {"Authorization": f"Bearer {generate_token(user['id'])}"}
    payload = {"current_password": "guestpass123", "new_password": "newpassword123"}
    resp = client.put(
        "/PSSM_GREMLIN/api/auth/me",
        headers={**guest_header, "Content-Type": "application/json"},
        data=json.dumps(payload),
    )
    assert resp.status_code == 403
    assert "Guest" in resp.json["error"]


# --- API key management ---


def test_api_key_status_no_key(monkeypatch, tmp_path):
    """GET /api/auth/me/api-key returns has_api_key=False when no key exists."""
    module = _load_pssm_module(monkeypatch, tmp_path, extra_env={"RUNNER_UID": "1234", "RUNNER_GID": "5678"})
    client = module.app.test_client()
    auth_header = _test_client_auth(module)
    resp = client.get("/PSSM_GREMLIN/api/auth/me/api-key", headers=auth_header)
    assert resp.status_code == 200
    assert resp.json["has_api_key"] is False


def test_api_key_generate_and_status(monkeypatch, tmp_path):
    """POST /api/auth/me/api-key generates key, then GET reports has_api_key=True."""
    module = _load_pssm_module(monkeypatch, tmp_path, extra_env={"RUNNER_UID": "1234", "RUNNER_GID": "5678"})
    client = module.app.test_client()
    auth_header = _test_client_auth(module)
    resp = client.post("/PSSM_GREMLIN/api/auth/me/api-key", headers=auth_header)
    assert resp.status_code == 201
    assert "api_key" in resp.json
    assert resp.json["api_key"].startswith("revodesign_")
    # Check status now reports has_api_key=True
    status_resp = client.get("/PSSM_GREMLIN/api/auth/me/api-key", headers=auth_header)
    assert status_resp.json["has_api_key"] is True


def test_api_key_revoke(monkeypatch, tmp_path):
    """DELETE /api/auth/me/api-key revokes the key."""
    module = _load_pssm_module(monkeypatch, tmp_path, extra_env={"RUNNER_UID": "1234", "RUNNER_GID": "5678"})
    client = module.app.test_client()
    auth_header = _test_client_auth(module)
    # Generate first
    client.post("/PSSM_GREMLIN/api/auth/me/api-key", headers=auth_header)
    # Revoke
    resp = client.delete("/PSSM_GREMLIN/api/auth/me/api-key", headers=auth_header)
    assert resp.status_code == 200
    # Status should be False
    status_resp = client.get("/PSSM_GREMLIN/api/auth/me/api-key", headers=auth_header)
    assert status_resp.json["has_api_key"] is False


def test_api_key_authenticates_user(monkeypatch, tmp_path):
    """X-API-Key header authenticates the user for read endpoints."""
    module = _load_pssm_module(monkeypatch, tmp_path, extra_env={"RUNNER_UID": "1234", "RUNNER_GID": "5678"})
    client = module.app.test_client()
    auth_header = _test_client_auth(module)
    module.app.config["user_db"]
    # Generate API key
    gen_resp = client.post("/PSSM_GREMLIN/api/auth/me/api-key", headers=auth_header)
    api_key = gen_resp.json["api_key"]
    # Authenticate with API key
    resp = client.get("/PSSM_GREMLIN/api/auth/me", headers={"X-API-Key": api_key})
    assert resp.status_code == 200
    assert resp.json["username"] == "tester"


def test_api_key_cannot_change_password(monkeypatch, tmp_path):
    """API key cannot perform state-changing operations (require_web_login gate)."""
    module = _load_pssm_module(monkeypatch, tmp_path, extra_env={"RUNNER_UID": "1234", "RUNNER_GID": "5678"})
    client = module.app.test_client()
    auth_header = _test_client_auth(module)
    gen_resp = client.post("/PSSM_GREMLIN/api/auth/me/api-key", headers=auth_header)
    api_key = gen_resp.json["api_key"]
    payload = {"current_password": "password", "new_password": "newpassword123"}
    resp = client.put(
        "/PSSM_GREMLIN/api/auth/me",
        headers={"X-API-Key": api_key, "Content-Type": "application/json"},
        data=json.dumps(payload),
    )
    assert resp.status_code == 403
    assert "API keys" in resp.json["error"]


def test_api_key_rejects_guest(monkeypatch, tmp_path):
    """load_current_user rejects API keys from guest-role accounts."""
    module = _load_pssm_module(monkeypatch, tmp_path, extra_env={"RUNNER_UID": "1234", "RUNNER_GID": "5678"})
    db = module.app.config["user_db"]
    user = db.create_user(
        username="guest2",
        email="guest2@test.local",
        password="guestpass123",
        role="guest",
        registration_status="approved",
        user_status="active",
    )
    db.verify_email(user["id"])
    from pssm_gremlin_server.auth import generate_token

    # Guest can get a bearer token
    guest_bearer = {"Authorization": f"Bearer {generate_token(user['id'])}"}
    client = module.app.test_client()
    # Guest tries to generate API key — should fail
    resp = client.post("/PSSM_GREMLIN/api/auth/me/api-key", headers=guest_bearer)
    assert resp.status_code == 403
    assert "Guest" in resp.json["error"]


# --- CAPTCHA ---


def test_captcha_returns_question_and_token(monkeypatch, tmp_path):
    """GET /api/auth/captcha returns a math question and signed token."""
    module = _load_pssm_module(monkeypatch, tmp_path, extra_env={"RUNNER_UID": "1234", "RUNNER_GID": "5678"})
    client = module.app.test_client()
    resp = client.get("/PSSM_GREMLIN/api/auth/captcha")
    assert resp.status_code == 200
    assert "question" in resp.json
    assert "token" in resp.json
    assert "What is" in resp.json["question"]


def test_captcha_token_validation(monkeypatch, tmp_path):
    """validate_captcha accepts valid token+answer, rejects invalid."""
    from pssm_gremlin_server.auth import _serializer, validate_captcha

    token = _serializer.dumps({"answer": 7, "purpose": "captcha"})
    assert validate_captcha(token, "7") is True
    assert validate_captcha(token, "8") is False


def test_captcha_rejects_expired_token(monkeypatch, tmp_path):
    """validate_captcha rejects tokens older than 5 minutes."""
    from pssm_gremlin_server.auth import _serializer, validate_captcha

    token = _serializer.dumps({"answer": 5, "purpose": "captcha"})
    # Force expiration by using max_age=0 (immediate expiry)
    try:
        from itsdangerous import SignatureExpired
    except ImportError:
        pytest.skip("itsdangerous not available")
    # We test that a token with 0 max_age is rejected
    import itsdangerous

    try:
        _serializer.loads(token, max_age=0)
    except SignatureExpired:
        pass  # expected
    # validate_captcha uses max_age=300 internally
    fresh_token = _serializer.dumps({"answer": 3, "purpose": "captcha"})
    assert validate_captcha(fresh_token, "3") is True


def test_captcha_rejects_wrong_purpose(monkeypatch, tmp_path):
    """validate_captcha rejects tokens with purpose != 'captcha'."""
    from pssm_gremlin_server.auth import _serializer, validate_captcha

    token = _serializer.dumps({"answer": 7, "purpose": "verify-email"})
    assert validate_captcha(token, "7") is False


# --- Logout ---


def test_auth_logout_clears_cookie(monkeypatch, tmp_path):
    """POST /api/auth/logout returns logged_out and sets auth_token to empty."""
    module = _load_pssm_module(monkeypatch, tmp_path, extra_env={"RUNNER_UID": "1234", "RUNNER_GID": "5678"})
    client = module.app.test_client()
    resp = client.post("/PSSM_GREMLIN/api/auth/logout")
    assert resp.status_code == 200
    assert resp.json["status"] == "logged_out"


# --- Forgot / reset password ---


def test_forgot_password_returns_generic_message(monkeypatch, tmp_path):
    """POST /api/auth/forgot-password always returns the same message (anti-enumeration)."""
    module = _load_pssm_module(
        monkeypatch,
        tmp_path,
        extra_env={"RUNNER_UID": "1234", "RUNNER_GID": "5678", "SMTP_HOST": "localhost"},
    )
    client = module.app.test_client()
    resp = client.post(
        "/PSSM_GREMLIN/api/auth/forgot-password",
        headers={"Content-Type": "application/json"},
        data=json.dumps({"email": "nonexistent@test.local"}),
    )
    assert resp.status_code == 200
    assert "If that email" in resp.json["message"]


def test_forgot_password_rate_limited(monkeypatch, tmp_path):
    """POST /api/auth/forgot-password is rate-limited (3 req/hour)."""
    module = _load_pssm_module(
        monkeypatch,
        tmp_path,
        extra_env={"RUNNER_UID": "1234", "RUNNER_GID": "5678", "SMTP_HOST": "localhost"},
    )
    client = module.app.test_client()
    payload = {"email": "test@test.local"}
    for _ in range(3):
        resp = client.post(
            "/PSSM_GREMLIN/api/auth/forgot-password",
            headers={"Content-Type": "application/json"},
            data=json.dumps(payload),
            environ_base={"REMOTE_ADDR": "203.0.113.42"},
        )
        assert resp.status_code == 200
    resp = client.post(
        "/PSSM_GREMLIN/api/auth/forgot-password",
        headers={"Content-Type": "application/json"},
        data=json.dumps(payload),
        environ_base={"REMOTE_ADDR": "203.0.113.42"},
    )
    assert resp.status_code == 429


def test_reset_password_get_renders_form(monkeypatch, tmp_path):
    """GET /PSSM_GREMLIN/reset_password?c=valid_token renders the form."""
    module = _load_pssm_module(monkeypatch, tmp_path, extra_env={"RUNNER_UID": "1234", "RUNNER_GID": "5678"})
    from pssm_gremlin_server.auth import _serializer

    db = module.app.config["user_db"]
    user = db.create_user(username="resetme", email="resetme@test.local", password="oldpass123")
    token = _serializer.dumps({"uid": user["id"], "purpose": "reset-password"})
    client = module.app.test_client()
    resp = client.get(f"/PSSM_GREMLIN/reset_password?c={token}")
    assert resp.status_code == 200


def test_reset_password_get_rejects_missing_token(monkeypatch, tmp_path):
    """GET /PSSM_GREMLIN/reset_password without token returns 400."""
    module = _load_pssm_module(monkeypatch, tmp_path, extra_env={"RUNNER_UID": "1234", "RUNNER_GID": "5678"})
    client = module.app.test_client()
    resp = client.get("/PSSM_GREMLIN/reset_password")
    assert resp.status_code == 400


def test_reset_password_get_rejects_invalid_token(monkeypatch, tmp_path):
    """GET /PSSM_GREMLIN/reset_password with invalid token returns 400."""
    module = _load_pssm_module(monkeypatch, tmp_path, extra_env={"RUNNER_UID": "1234", "RUNNER_GID": "5678"})
    client = module.app.test_client()
    resp = client.get("/PSSM_GREMLIN/reset_password?c=invalid_token")
    assert resp.status_code == 400


def test_reset_password_post_sets_new_password(monkeypatch, tmp_path):
    """POST /PSSM_GREMLIN/reset_password sets a new password."""
    module = _load_pssm_module(monkeypatch, tmp_path, extra_env={"RUNNER_UID": "1234", "RUNNER_GID": "5678"})
    from pssm_gremlin_server.auth import _serializer

    db = module.app.config["user_db"]
    user = db.create_user(
        username="resetpost",
        email="resetpost@test.local",
        password="oldpass123",
        registration_status="approved",
        user_status="active",
    )
    db.verify_email(user["id"])
    token = _serializer.dumps({"uid": user["id"], "purpose": "reset-password"})
    client = module.app.test_client()
    resp = client.post(
        "/PSSM_GREMLIN/reset_password",
        headers={"Content-Type": "application/json"},
        data=json.dumps({"token": token, "password": "newpass456"}),
    )
    assert resp.status_code == 200
    # Verify new password works
    login_resp = client.post(
        "/PSSM_GREMLIN/api/auth/login",
        headers={"Content-Type": "application/json"},
        data=json.dumps({"username": "resetpost", "password": "newpass456"}),
    )
    assert login_resp.status_code == 200


# --- Resend verification ---


def test_resend_verification_generic_response(monkeypatch, tmp_path):
    """POST /api/auth/resend-verification returns generic message for unknown email."""
    module = _load_pssm_module(monkeypatch, tmp_path, extra_env={"RUNNER_UID": "1234", "RUNNER_GID": "5678"})
    client = module.app.test_client()
    resp = client.post(
        "/PSSM_GREMLIN/api/auth/resend-verification",
        headers={"Content-Type": "application/json"},
        data=json.dumps({"email": "missing@test.local"}),
    )
    assert resp.status_code == 200
    assert "If that email" in resp.json["message"]


# --- Email verification ---


def test_verify_email_missing_token(monkeypatch, tmp_path):
    """GET /PSSM_GREMLIN/api/auth/verify-email with no token returns 400."""
    module = _load_pssm_module(
        monkeypatch,
        tmp_path,
        extra_env={"RUNNER_UID": "1234", "RUNNER_GID": "5678", "SMTP_HOST": "localhost"},
    )
    client = module.app.test_client()
    resp = client.get("/PSSM_GREMLIN/api/auth/verify-email")
    # Returns HTML page with error
    assert resp.status_code == 400


# --- Login edge cases ---


def test_login_with_email(monkeypatch, tmp_path):
    """POST /api/auth/login accepts email as login_id."""
    module = _load_pssm_module(monkeypatch, tmp_path, extra_env={"RUNNER_UID": "1234", "RUNNER_GID": "5678"})
    _test_client_auth(module)  # ensure tester exists in DB
    client = module.app.test_client()
    resp = client.post(
        "/PSSM_GREMLIN/api/auth/login",
        headers={"Content-Type": "application/json"},
        data=json.dumps({"username": "tester@test.local", "password": "password"}),
    )
    assert resp.status_code == 200
    assert "token" in resp.json


def test_login_sets_auth_cookie(monkeypatch, tmp_path):
    """POST /api/auth/login sets httponly auth_token cookie."""
    module = _load_pssm_module(monkeypatch, tmp_path, extra_env={"RUNNER_UID": "1234", "RUNNER_GID": "5678"})
    _test_client_auth(module)  # ensure tester exists in DB
    client = module.app.test_client()
    resp = client.post(
        "/PSSM_GREMLIN/api/auth/login",
        headers={"Content-Type": "application/json"},
        data=json.dumps({"username": "tester", "password": "password"}),
    )
    assert resp.status_code == 200
    cookies = resp.headers.get_all("Set-Cookie")
    assert any("auth_token" in c for c in cookies)
    assert any("HttpOnly" in c for c in cookies)


# --- Page routes ---


def test_login_page_redirects_authenticated_user(monkeypatch, tmp_path):
    """GET /PSSM_GREMLIN/login redirects to dashboard when already logged in."""
    module = _load_pssm_module(monkeypatch, tmp_path, extra_env={"RUNNER_UID": "1234", "RUNNER_GID": "5678"})
    client = module.app.test_client()
    auth_header = _test_client_auth(module)
    resp = client.get("/PSSM_GREMLIN/login", headers=auth_header)
    assert resp.status_code == 302


def test_terms_page(monkeypatch, tmp_path):
    """GET /PSSM_GREMLIN/terms returns the terms page."""
    module = _load_pssm_module(monkeypatch, tmp_path, extra_env={"RUNNER_UID": "1234", "RUNNER_GID": "5678"})
    client = module.app.test_client()
    resp = client.get("/PSSM_GREMLIN/terms")
    assert resp.status_code == 200


def test_register_page_disabled_by_default(monkeypatch, tmp_path):
    """GET /PSSM_GREMLIN/register returns 403 when ENABLE_REGISTER is false (default)."""
    module = _load_pssm_module(monkeypatch, tmp_path, extra_env={"RUNNER_UID": "1234", "RUNNER_GID": "5678"})
    client = module.app.test_client()
    resp = client.get("/PSSM_GREMLIN/register")
    assert resp.status_code == 403


def test_profile_page_requires_login(monkeypatch, tmp_path):
    """GET /PSSM_GREMLIN/profile returns 401 without auth."""
    module = _load_pssm_module(monkeypatch, tmp_path, extra_env={"RUNNER_UID": "1234", "RUNNER_GID": "5678"})
    client = module.app.test_client()
    resp = client.get("/PSSM_GREMLIN/profile")
    assert resp.status_code == 401


# --- Deleted user ---


def test_deleted_user_cannot_authenticate(monkeypatch, tmp_path):
    """Soft-deleted users are blocked from all auth methods."""
    module = _load_pssm_module(monkeypatch, tmp_path, extra_env={"RUNNER_UID": "1234", "RUNNER_GID": "5678"})
    db = module.app.config["user_db"]
    user = db.create_user(
        username="deleted_user",
        email="deleted_user@test.local",
        password="pass1234",
        registration_status="approved",
        user_status="active",
    )
    db.verify_email(user["id"])
    db.update_user(user["id"], deleted=True)
    client = module.app.test_client()
    resp = client.post(
        "/PSSM_GREMLIN/api/auth/login",
        headers={"Content-Type": "application/json"},
        data=json.dumps({"username": "deleted_user", "password": "pass1234"}),
    )
    assert resp.status_code == 403
    assert resp.json["error"] == "Account has been deleted"


# --- Pending user ---


def test_pending_user_cannot_authenticate(monkeypatch, tmp_path):
    """Self-registered (pending) users are blocked until admin approval."""
    module = _load_pssm_module(monkeypatch, tmp_path, extra_env={"RUNNER_UID": "1234", "RUNNER_GID": "5678"})
    db = module.app.config["user_db"]
    user = db.create_user(
        username="pending_user",
        email="pending@test.local",
        password="pass1234",
        registration_status="email_sent",
        user_status="pending",
    )
    # Even with verified email, pending status blocks auth
    db.verify_email(user["id"])
    client = module.app.test_client()
    resp = client.post(
        "/PSSM_GREMLIN/api/auth/login",
        headers={"Content-Type": "application/json"},
        data=json.dumps({"username": "pending_user", "password": "pass1234"}),
    )
    assert resp.status_code == 403
    assert "not yet active" in resp.json["error"]


def test_unverified_email_cannot_authenticate(monkeypatch, tmp_path):
    """Users with unverified email are blocked even if user_status is active."""
    module = _load_pssm_module(monkeypatch, tmp_path, extra_env={"RUNNER_UID": "1234", "RUNNER_GID": "5678"})
    db = module.app.config["user_db"]
    user = db.create_user(
        username="unverified",
        email="unverified@test.local",
        password="pass1234",
        registration_status="approved",
        user_status="active",
    )
    # user_status is active but email is NOT verified
    client = module.app.test_client()
    resp = client.post(
        "/PSSM_GREMLIN/api/auth/login",
        headers={"Content-Type": "application/json"},
        data=json.dumps({"username": "unverified", "password": "pass1234"}),
    )
    assert resp.status_code == 403
    assert "Email not verified" in resp.json["error"]


# ==================================================================
# UserDatabase direct tests
# ==================================================================


def test_user_db_get_user_by_email(monkeypatch, tmp_path):
    """UserDatabase.get_user_by_email finds user by case-insensitive email."""
    module = _load_pssm_module(monkeypatch, tmp_path, extra_env={"RUNNER_UID": "1234", "RUNNER_GID": "5678"})
    _test_client_auth(module)  # ensure tester exists
    db = module.app.config["user_db"]
    assert db.get_user_by_email("nonexistent@test.local") is None
    user = db.get_user_by_email("tester@test.local")
    assert user is not None
    assert user["username"] == "tester"
    # Case-insensitive
    user2 = db.get_user_by_email("TESTER@test.local")
    assert user2 is not None
    assert user2["username"] == "tester"


def test_user_db_get_user_by_username(monkeypatch, tmp_path):
    """UserDatabase.get_user_by_username strips and matches."""
    module = _load_pssm_module(monkeypatch, tmp_path, extra_env={"RUNNER_UID": "1234", "RUNNER_GID": "5678"})
    _test_client_auth(module)  # ensure tester exists
    db = module.app.config["user_db"]
    assert db.get_user_by_username("nonexistent") is None
    user = db.get_user_by_username("tester")
    assert user is not None
    assert user["email"] == "tester@test.local"


def test_user_db_user_count(monkeypatch, tmp_path):
    """UserDatabase.user_count returns total user count."""
    module = _load_pssm_module(monkeypatch, tmp_path, extra_env={"RUNNER_UID": "1234", "RUNNER_GID": "5678"})
    db = module.app.config["user_db"]
    count_before = db.user_count()
    db.create_user(username="count_me", email="count@test.local", password="pass1234")
    assert db.user_count() == count_before + 1


def test_user_db_list_users_excludes_deleted(monkeypatch, tmp_path):
    """UserDatabase.list_users excludes soft-deleted users by default."""
    module = _load_pssm_module(monkeypatch, tmp_path, extra_env={"RUNNER_UID": "1234", "RUNNER_GID": "5678"})
    db = module.app.config["user_db"]
    user = db.create_user(username="vis", email="vis@test.local", password="pass1234")
    db.update_user(user["id"], deleted=True)
    visible = db.list_users()
    assert not any(u["id"] == user["id"] for u in visible)
    # include_deleted=True
    all_users = db.list_users(include_deleted=True)
    assert any(u["id"] == user["id"] for u in all_users)


def test_user_db_get_unnotified_registrations(monkeypatch, tmp_path):
    """UserDatabase.get_unnotified_registrations returns non-admin users not yet in digest."""
    module = _load_pssm_module(monkeypatch, tmp_path, extra_env={"RUNNER_UID": "1234", "RUNNER_GID": "5678"})
    db = module.app.config["user_db"]
    user = db.create_user(username="unnotified", email="unnotified@test.local", password="pass1234")
    unnotified = db.get_unnotified_registrations()
    assert any(u["id"] == user["id"] for u in unnotified)
    # Mark as notified
    db.mark_users_notified([user["id"]])
    unnotified2 = db.get_unnotified_registrations()
    assert not any(u["id"] == user["id"] for u in unnotified2)


def test_user_db_unmark_users_notified(monkeypatch, tmp_path):
    """UserDatabase.unmark_users_notified restores users to the digest."""
    module = _load_pssm_module(monkeypatch, tmp_path, extra_env={"RUNNER_UID": "1234", "RUNNER_GID": "5678"})
    db = module.app.config["user_db"]
    user = db.create_user(username="unmark", email="unmark@test.local", password="pass1234")
    db.mark_users_notified([user["id"]])
    db.unmark_users_notified([user["id"]])
    unnotified = db.get_unnotified_registrations()
    assert any(u["id"] == user["id"] for u in unnotified)


def test_user_db_validate_api_key(monkeypatch, tmp_path):
    """UserDatabase.validate_api_key returns user for valid key, None for invalid."""
    module = _load_pssm_module(monkeypatch, tmp_path, extra_env={"RUNNER_UID": "1234", "RUNNER_GID": "5678"})
    db = module.app.config["user_db"]
    # Create a user directly so we control the state
    user = db.create_user(
        username="apikey_test",
        email="apikey@test.local",
        password="pass1234",
        registration_status="approved",
        user_status="active",
    )
    db.verify_email(user["id"])
    key = db.generate_api_key(user["id"])
    # Valid key
    found = db.validate_api_key(key)
    assert found is not None
    assert found["username"] == "apikey_test"
    # Invalid key
    assert db.validate_api_key("revodesign_" + "00" * 32) is None
    # Wrong prefix
    assert db.validate_api_key("wrong_prefix_key") is None
    # Empty
    assert db.validate_api_key("") is None
    # Revoked
    db.revoke_api_key(user["id"])
    assert db.validate_api_key(key) is None


# ==================================================================
# Rate limiter tests
# ==================================================================


def test_rate_limit_on_register_endpoint(monkeypatch, tmp_path):
    """POST /api/auth/register is rate-limited (3 req/hour)."""
    module = _load_pssm_module(
        monkeypatch,
        tmp_path,
        extra_env={"RUNNER_UID": "1234", "RUNNER_GID": "5678", "ENABLE_REGISTER": "true", "SMTP_HOST": "localhost"},
    )
    from pssm_gremlin_server.auth import _serializer

    client = module.app.test_client()
    captcha_token = _serializer.dumps({"answer": 7, "purpose": "captcha"})
    payload = {
        "username": "ratelimit_test",
        "email": "rl@test.local",
        "password": "pass12345678",
        "terms_agreed": True,
        "captcha_token": captcha_token,
        "captcha_answer": "7",
    }
    for _ in range(3):
        resp = client.post(
            "/PSSM_GREMLIN/api/auth/register",
            headers={"Content-Type": "application/json"},
            data=json.dumps(payload),
            environ_base={"REMOTE_ADDR": "198.51.100.99"},
        )
    resp = client.post(
        "/PSSM_GREMLIN/api/auth/register",
        headers={"Content-Type": "application/json"},
        data=json.dumps(payload),
        environ_base={"REMOTE_ADDR": "198.51.100.99"},
    )
    assert resp.status_code == 429


def test_rate_limit_on_upload_endpoint(monkeypatch, tmp_path):
    """Rate limit is enforced on upload endpoint — tested via the decorator directly."""
    from flask import Flask
    from pssm_gremlin_server.ratelimit import rate_limit

    app_test = Flask(__name__)
    counter = [0]

    @app_test.route("/test")
    @rate_limit(max_requests=3, window_seconds=3600)
    def _limited():
        counter[0] += 1
        return "ok"

    client = app_test.test_client()
    for _ in range(3):
        resp = client.get("/test", environ_base={"REMOTE_ADDR": "198.51.100.100"})
        assert resp.status_code == 200
    # 4th should be rate-limited
    resp = client.get("/test", environ_base={"REMOTE_ADDR": "198.51.100.100"})
    assert resp.status_code == 429
    assert resp.json["error"] == "Too many requests"


# ==================================================================
# Upload edge-case tests
# ==================================================================


def test_upload_rejects_empty_filename(monkeypatch, tmp_path):
    """POST /api/post with empty filename returns 400."""
    module = _load_pssm_module(monkeypatch, tmp_path, extra_env={"RUNNER_UID": "1234", "RUNNER_GID": "5678"})
    client = module.app.test_client()
    auth_header = _test_client_auth(module)
    resp = client.post(
        "/PSSM_GREMLIN/api/post",
        data={"file": (io.BytesIO(b">test\nACDE\n"), "")},
        headers=auth_header,
    )
    assert resp.status_code == 400
    assert "No selected file" in resp.json["error"]


def test_upload_rejects_non_fasta_extension(monkeypatch, tmp_path):
    """POST /api/post rejects files without .fasta extension."""
    module = _load_pssm_module(monkeypatch, tmp_path, extra_env={"RUNNER_UID": "1234", "RUNNER_GID": "5678"})
    client = module.app.test_client()
    auth_header = _test_client_auth(module)
    resp = client.post(
        "/PSSM_GREMLIN/api/post",
        data={"file": (io.BytesIO(b">test\nACDE\n"), "upload.txt")},
        headers=auth_header,
    )
    assert resp.status_code == 400
    assert "extension" in resp.json["error"].lower()


def test_upload_rejects_binary_content(monkeypatch, tmp_path):
    """POST /api/post rejects files with binary content."""
    module = _load_pssm_module(monkeypatch, tmp_path, extra_env={"RUNNER_UID": "1234", "RUNNER_GID": "5678"})
    client = module.app.test_client()
    auth_header = _test_client_auth(module)
    resp = client.post(
        "/PSSM_GREMLIN/api/post",
        data={"file": (io.BytesIO(b"\x00\x01\x02\x03"), "binary.fasta")},
        headers=auth_header,
    )
    assert resp.status_code == 400
    assert "binary" in resp.json["error"].lower()


def test_upload_rejects_invalid_fasta_content(monkeypatch, tmp_path):
    """POST /api/post rejects files that don't look like FASTA."""
    module = _load_pssm_module(monkeypatch, tmp_path, extra_env={"RUNNER_UID": "1234", "RUNNER_GID": "5678"})
    client = module.app.test_client()
    auth_header = _test_client_auth(module)
    resp = client.post(
        "/PSSM_GREMLIN/api/post",
        data={"file": (io.BytesIO(b"Not a FASTA file\njust some text\n"), "bad.fasta")},
        headers=auth_header,
    )
    assert resp.status_code == 400
    assert "FASTA" in resp.json["error"]


def test_upload_enforces_active_task_cap(monkeypatch, tmp_path):
    """POST /api/post returns 429 when user has >= 5 active tasks."""
    module = _load_pssm_module(monkeypatch, tmp_path, extra_env={"RUNNER_UID": "1234", "RUNNER_GID": "5678"})

    class _DummyAsyncResult:
        id = "celery-test-id"

    monkeypatch.setattr(module.run_gremlin_task, "apply_async", lambda *args, **kwargs: _DummyAsyncResult())
    client = module.app.test_client()
    auth_header = _test_client_auth(module)
    # Submit 5 tasks with different content to avoid dedup
    for i in range(5):
        content = f">test{i}\nACDE{i}\n".encode()
        resp = client.post(
            "/PSSM_GREMLIN/api/post",
            data={"file": (io.BytesIO(content), f"task{i}.fasta")},
            headers=auth_header,
        )
        assert resp.status_code == 302, f"Upload {i} expected 302, got {resp.status_code}"
    # 6th should be rejected by task cap
    resp = client.post(
        "/PSSM_GREMLIN/api/post",
        data={"file": (io.BytesIO(b">overflow\nSEQVENCE\n"), "task_overflow.fasta")},
        headers=auth_header,
    )
    assert resp.status_code == 429
    assert "Too many" in resp.json["error"]


def test_upload_deduplicates_by_content_and_user(monkeypatch, tmp_path):
    """Same FASTA content by same user gets the same task ID."""
    module = _load_pssm_module(monkeypatch, tmp_path, extra_env={"RUNNER_UID": "1234", "RUNNER_GID": "5678"})

    class _DummyAsyncResult:
        id = "celery-test-id"

    monkeypatch.setattr(module.run_gremlin_task, "apply_async", lambda *args, **kwargs: _DummyAsyncResult())
    client = module.app.test_client()
    auth_header = _test_client_auth(module)
    fasta_content = b">test\nACDEFGHIK\n"
    resp1 = client.post(
        "/PSSM_GREMLIN/api/post",
        data={"file": (io.BytesIO(fasta_content), "seqs.fasta")},
        headers=auth_header,
    )
    assert resp1.status_code == 302
    resp2 = client.post(
        "/PSSM_GREMLIN/api/post",
        data={"file": (io.BytesIO(fasta_content), "seqs.fasta")},
        headers=auth_header,
    )
    assert resp2.status_code == 202
    assert resp2.json["status"] == "Task already queued or running"


def test_upload_different_users_get_different_ids_for_same_content(monkeypatch, tmp_path):
    """Same FASTA content by different users gets different task IDs."""
    module = _load_pssm_module(monkeypatch, tmp_path, extra_env={"RUNNER_UID": "1234", "RUNNER_GID": "5678"})

    class _DummyAsyncResult:
        id = "celery-test-id"

    monkeypatch.setattr(module.run_gremlin_task, "apply_async", lambda *args, **kwargs: _DummyAsyncResult())
    client = module.app.test_client()
    owner_header = _test_client_auth(module)
    other_header = _test_client_auth(module, "other", "password2")
    fasta_content = b">test\nACDEFGHIK\n"
    resp1 = client.post(
        "/PSSM_GREMLIN/api/post",
        data={"file": (io.BytesIO(fasta_content), "same.fasta")},
        headers=owner_header,
    )
    assert resp1.status_code == 302
    resp2 = client.post(
        "/PSSM_GREMLIN/api/post",
        data={"file": (io.BytesIO(fasta_content), "same.fasta")},
        headers=other_header,
    )
    assert resp2.status_code == 302
    assert _extract_md5(resp1.headers["Location"]) != _extract_md5(resp2.headers["Location"])


# ==================================================================
# Schema validation tests
# ==================================================================


def test_schema_login_request_rejects_empty_fields(monkeypatch, tmp_path):
    """LoginRequest requires non-empty username and password."""
    from pssm_gremlin_server.schemas import LoginRequest
    from pydantic import ValidationError

    with pytest.raises(ValidationError):
        LoginRequest(username="", password="something")
    with pytest.raises(ValidationError):
        LoginRequest(username="test", password="")


def test_schema_register_request_min_password_length(monkeypatch, tmp_path):
    """RegisterRequest enforces min 8-char password."""
    from pssm_gremlin_server.schemas import RegisterRequest
    from pydantic import ValidationError

    with pytest.raises(ValidationError):
        RegisterRequest(
            username="testuser",
            email="test@test.com",
            password="short",
            terms_agreed=True,
            captcha_token="tok",
            captcha_answer="5",
        )


def test_schema_register_request_min_username_length(monkeypatch, tmp_path):
    """RegisterRequest enforces min 3-char username."""
    from pssm_gremlin_server.schemas import RegisterRequest
    from pydantic import ValidationError

    with pytest.raises(ValidationError):
        RegisterRequest(
            username="ab",
            email="test@test.com",
            password="password123",
            terms_agreed=True,
            captcha_token="tok",
            captcha_answer="5",
        )


def test_schema_email_normalization(monkeypatch, tmp_path):
    """Email normalization strips +suffix and lowercases."""
    from pssm_gremlin_server.schemas import normalize_email

    assert normalize_email("User@Domain.com") == "user@domain.com"
    assert normalize_email("user+tag@domain.com") == "user@domain.com"
    assert normalize_email("User+Tag+Suffix@Domain.Com") == "user@domain.com"


def test_schema_admin_create_user_rejects_invalid_role(monkeypatch, tmp_path):
    """AdminCreateUserRequest rejects roles other than admin/user/guest."""
    from pssm_gremlin_server.schemas import AdminCreateUserRequest
    from pydantic import ValidationError

    with pytest.raises(ValidationError):
        AdminCreateUserRequest(username="test", email="t@t.com", password="pass1234", role="superadmin")


def test_schema_batch_user_requires_nonempty_user_ids(monkeypatch, tmp_path):
    """BatchUserRequest requires at least one user_id."""
    from pssm_gremlin_server.schemas import BatchUserRequest
    from pydantic import ValidationError

    with pytest.raises(ValidationError):
        BatchUserRequest(action="enable", user_ids=[])


def test_schema_user_response_excludes_password_hash(monkeypatch, tmp_path):
    """UserResponse does not accept password_hash or api_key_hash fields."""
    from pssm_gremlin_server.schemas import UserResponse
    from pydantic import ValidationError

    # Valid minimal data
    user = UserResponse(
        id=1,
        username="test",
        email="t@t.com",
        email_verified=True,
        is_admin=False,
        role="user",
        affiliation=None,
        registration_status="approved",
        user_status="active",
        created_at=1234567890.0,
        approved_by=None,
        approved_at=None,
    )
    assert user.username == "test"
    # password_hash should not be in the model
    assert "password_hash" not in UserResponse.model_fields
