# Copyright (c) 2026 The REvoDesign Developers.
# Distributed under the terms of the GNU General Public License v3.0.
# SPDX-License-Identifier: GPL-3.0-only

"""Security-hardening tests: API key digests, rate limiting, CAPTCHA nonces.

Redis is optional at runtime — these tests cover both paths (a throwaway
local ``redis-server``, and the in-memory fallback when Redis is down).  The
Redis client is cached per process, so every test that changes ``REDIS_URL``
must call ``get_redis.cache_clear()`` first.
"""

from __future__ import annotations

import hashlib
import re
import shutil
import socket
import sqlite3
import subprocess
import time

import pytest
import redis
from flask import Flask
from revocompute.auth import UserDatabase, _used_captcha_nonces, generate_captcha, validate_captcha
from revocompute.ratelimit import rate_limit
from revocompute.redis_util import get_redis
from werkzeug.security import generate_password_hash


@pytest.fixture(autouse=True)
def _reset_redis_probe():
    """Re-probe Redis in every test — the client is cached per process."""
    yield
    get_redis.cache_clear()
    _used_captcha_nonces.clear()


# ---------------------------------------------------------------------------
# API keys — sha256 digest storage, single indexed lookup
# ---------------------------------------------------------------------------


def test_api_key_generate_and_validate(tmp_path):
    """A generated key validates; wrong keys, prefixes, and empties do not."""
    db = UserDatabase(str(tmp_path / "users.sqlite3"))
    user = db.create_user("alice", "alice@example.com", "password123")
    key = db.generate_api_key(user["id"])
    assert key.startswith("revodesign_")
    # Re-read after generate — the stored value must be the sha256 digest,
    # never the plaintext key.
    stored = db.get_user(user["id"])
    assert stored is not None and stored["api_key_digest"] == hashlib.sha256(key.encode("utf-8")).hexdigest()
    assert stored["api_key_digest"] != key

    got = db.validate_api_key(key)
    assert got is not None
    assert got["username"] == "alice"

    assert db.validate_api_key("revodesign_" + "0" * 64) is None  # wrong key
    assert db.validate_api_key("not-an-api-key") is None  # no prefix
    assert db.validate_api_key("") is None
    assert db.validate_api_key(key[:-1]) is None  # truncated
    db.revoke_api_key(user["id"])
    assert db.validate_api_key(key) is None  # revoked key is dead


def test_api_key_validation_with_several_users(tmp_path):
    """Validation resolves the right user among several, by digest lookup."""
    db = UserDatabase(str(tmp_path / "users.sqlite3"))
    keys: dict[str, str] = {}
    for i, name in enumerate(("alice", "bob", "carol", "dave")):
        user = db.create_user(name, f"{name}@example.com", f"password{i}123")
        keys[name] = db.generate_api_key(user["id"])

    for name, key in keys.items():
        got = db.validate_api_key(key)
        assert got is not None and got["username"] == name

    # valid prefix, wrong content — digest matches nothing
    assert db.validate_api_key(keys["alice"] + "ff") is None

    # the digest column is actually indexed — validation is one lookup
    with db.engine.connect() as conn:
        indexes = {row[1] for row in conn.exec_driver_sql("PRAGMA index_list(users)")}
    assert "ix_users_api_key_digest" in indexes


def test_old_api_key_schema_fails_without_mutating_state(tmp_path):
    path = tmp_path / "legacy.sqlite3"
    old_kdf_hash = generate_password_hash("revodesign_old-key")
    conn = sqlite3.connect(path)
    conn.execute(
        """
        CREATE TABLE users (
            id INTEGER PRIMARY KEY,
            username VARCHAR(128) NOT NULL UNIQUE,
            email VARCHAR(256) NOT NULL UNIQUE,
            password_hash VARCHAR(256) NOT NULL,
            email_verified BOOLEAN NOT NULL DEFAULT 0,
            created_at FLOAT NOT NULL,
            api_key_hash VARCHAR(256),
            full_name VARCHAR(128),
            affiliation VARCHAR(256),
            position VARCHAR(64),
            pi_name VARCHAR(128),
            terms_agreed BOOLEAN NOT NULL DEFAULT 0,
            registration_status VARCHAR(32) NOT NULL DEFAULT 'email_sent',
            user_status VARCHAR(32) NOT NULL DEFAULT 'pending',
            approved_by INTEGER,
            approved_at FLOAT,
            deleted BOOLEAN NOT NULL DEFAULT 0,
            role VARCHAR(32) NOT NULL DEFAULT 'user',
            admin_notified BOOLEAN NOT NULL DEFAULT 0,
            verification_resend_count INTEGER NOT NULL DEFAULT 0,
            verification_resend_at FLOAT,
            registration_ip VARCHAR(45),
            registration_country VARCHAR(8),
            token_version INTEGER NOT NULL DEFAULT 0,
            allow_gpu_use BOOLEAN NOT NULL DEFAULT 0,
            storage_key VARCHAR(128) NOT NULL UNIQUE
        )
        """
    )
    conn.execute(
        "INSERT INTO users (username, email, password_hash, email_verified, created_at, api_key_hash, storage_key)"
        " VALUES (?, ?, ?, 1, ?, ?, ?)",
        (
            "legacy",
            "legacy@example.com",
            generate_password_hash("password123"),
            time.time(),
            old_kdf_hash,
            "legacy-abcdef",
        ),
    )
    conn.commit()
    conn.close()

    with pytest.raises(RuntimeError, match="predates the Project Scope schema epoch"):
        UserDatabase(str(path))

    conn = sqlite3.connect(path)
    columns = {row[1] for row in conn.execute("PRAGMA table_info(users)")}
    row = conn.execute("SELECT username FROM users").fetchone()
    conn.close()
    assert "api_key_digest" not in columns
    assert "api_key_hash" in columns
    assert row == ("legacy",)


# ---------------------------------------------------------------------------
# Rate limiting — Redis path and in-memory fallback
# ---------------------------------------------------------------------------


def _free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


@pytest.fixture
def live_redis(monkeypatch, tmp_path):
    """Start a throwaway redis-server and point REDIS_URL at it.

    Skips cleanly when the redis-server binary is absent.
    """
    if shutil.which("redis-server") is None:
        pytest.skip("redis-server binary not available")
    # redis-py 8 speaks RESP3 (HELLO); pre-6.0 servers do not know the
    # command.  Production pins redis:7.2-alpine — this skip only covers
    # ancient local binaries used as a live test double.
    version_out = subprocess.run(["redis-server", "--version"], capture_output=True, text=True).stdout
    version_match = re.search(r"v=(\d+)", version_out)
    if version_match and int(version_match.group(1)) < 6:
        pytest.skip("local redis-server predates RESP3 HELLO; redis-py 8 requires redis >= 6")
    port = _free_port()
    proc = subprocess.Popen(
        [
            "redis-server",
            "--port",
            str(port),
            "--save",
            "",
            "--appendonly",
            "no",
            "--bind",
            "127.0.0.1",
            "--dir",
            str(tmp_path),
        ],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    client = None
    deadline = time.monotonic() + 10
    while time.monotonic() < deadline:
        try:
            client = redis.Redis(host="127.0.0.1", port=port, socket_timeout=0.5)
            client.ping()
            break
        except Exception:
            time.sleep(0.05)
    if client is None:
        proc.terminate()
        pytest.fail("redis-server did not become ready")
    monkeypatch.setenv("REDIS_URL", f"redis://127.0.0.1:{port}/0")
    get_redis.cache_clear()
    yield client
    proc.terminate()
    proc.wait(timeout=10)
    get_redis.cache_clear()


def _limited_app(max_requests: int, window_seconds: int, calls: list) -> Flask:
    """Return a Flask app whose POST /login is rate limited (fresh state)."""
    app = Flask(__name__)

    @app.route("/login", methods=["POST"])
    @rate_limit(max_requests=max_requests, window_seconds=window_seconds)
    def login():
        calls.append(1)
        return "ok", 200

    return app


def test_rate_limit_fallback_without_redis(monkeypatch):
    """No reachable Redis → in-memory per-worker limiter still 429s."""
    monkeypatch.setenv("REDIS_URL", "redis://127.0.0.1:1/0")  # nothing listens
    get_redis.cache_clear()
    assert get_redis() is None

    calls: list = []
    client = _limited_app(max_requests=2, window_seconds=60, calls=calls).test_client()
    assert client.post("/login").status_code == 200
    assert client.post("/login").status_code == 200
    resp = client.post("/login")
    assert resp.status_code == 429
    assert resp.json["error"] == "Too many requests"
    assert resp.json["retry_after_seconds"] >= 1
    assert len(calls) == 2  # the 429 never reached the endpoint


def test_rate_limit_redis_path(live_redis):
    """With Redis up: fixed-window counter, 429 past the limit with TTL."""
    calls: list = []
    app = _limited_app(max_requests=3, window_seconds=60, calls=calls)
    client = app.test_client()
    for _ in range(3):
        assert client.post("/login").status_code == 200
    resp = client.post("/login")
    assert resp.status_code == 429
    assert resp.json["retry_after_seconds"] >= 1
    assert len(calls) == 3

    # the fixed-window key exists in Redis with a live TTL
    view = client.application.view_functions["login"]
    key = f"{view.__wrapped__.__module__}.{view.__wrapped__.__qualname__}:127.0.0.1"
    assert live_redis.get(key) is not None
    assert 0 < live_redis.ttl(key) <= 60


# ---------------------------------------------------------------------------
# CAPTCHA nonces — Redis-first, in-memory fallback
# ---------------------------------------------------------------------------


def _captcha_answer(question: str) -> int:
    m = re.search(r"(\d+) \+ (\d+)", question)
    assert m is not None, f"unparseable CAPTCHA question: {question!r}"
    return int(m.group(1)) + int(m.group(2))


def test_captcha_valid_then_replay_fails(live_redis):
    """A correct answer passes once; the Redis nonce rejects the replay."""
    question, token = generate_captcha()
    answer = str(_captcha_answer(question))
    assert validate_captcha(token, answer) is True
    assert validate_captcha(token, answer) is False  # replay


def test_captcha_wrong_answer_does_not_burn_nonce(live_redis):
    """A wrong answer fails without consuming the nonce — retry works."""
    question, token = generate_captcha()
    assert validate_captcha(token, "999999") is False
    assert validate_captcha(token, str(_captcha_answer(question))) is True


def test_captcha_tampered_token_rejected(live_redis):
    """A token with a broken signature is rejected outright."""
    _, token = generate_captcha()
    tampered = token[:-6] + ("0" if token[-6] != "0" else "1") + token[-5:]
    assert validate_captcha(tampered, "1") is False


def test_captcha_redis_down_fallback(monkeypatch):
    """Redis down → per-process nonce store: passes once, replay fails."""
    monkeypatch.setenv("REDIS_URL", "redis://127.0.0.1:1/0")
    get_redis.cache_clear()
    assert get_redis() is None

    question, token = generate_captcha()
    answer = str(_captcha_answer(question))
    assert validate_captcha(token, answer) is True
    assert validate_captcha(token, answer) is False  # replay in memory
