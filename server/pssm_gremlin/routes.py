# Copyright (c) 2026 The REvoDesign Developers.
# Distributed under the terms of the GNU General Public License v3.0.
# SPDX-License-Identifier: GPL-3.0-only

"""HTTP route handlers for the GREMLIN server.

All ``@app.route`` decorators live here.  The module is imported by
``pssm_gremlin.__init__`` *after* ``pssm_gremlin.pssm_gremlin`` has
created the Flask ``app``, so the decorators register against an
already-initialised application.
"""

from __future__ import annotations

import hashlib
import logging
import os
import shutil
import time

from celery.result import AsyncResult
from flask import current_app, g, jsonify, redirect, render_template, request, send_from_directory
from pssm_gremlin.auth import (
    UserDatabase,
    _env_str,
    generate_token,
    load_current_user,
    login_required,
    optional_user,
    require_web_login,
    send_verification_email,
    validate_email_token,
)
from pssm_gremlin.pssm_gremlin import (
    CONFIG,
    ENABLE_REGISTER,
    TEMPLATE_IMAGE_DIR,
    _build_running_trace,
    _current_username,
    _delete_task_artifacts,
    _deleted_status_from_task,
    _is_admin_user,
    _is_binary_file,
    _is_deleted_status,
    _local_user_identity,
    _normalize_task_id,
    _request_metadata,
    _revoke_celery_task,
    _safe_join,
    _sanitize_task_error,
    _task_access_allowed,
    _task_access_denied,
    _task_delete_allowed,
    _task_id_for_upload,
    _task_zip_download_name,
    _task_zip_path,
    _virtual_upload_path,
    app,
    format_times,
    format_walltime,
    run_gremlin_task,
    task_store,
)
from pssm_gremlin.ratelimit import rate_limit
from werkzeug.security import check_password_hash, generate_password_hash
from werkzeug.utils import secure_filename

# ---------------------------------------------------------------------------
# Page routes
# ---------------------------------------------------------------------------


@app.route("/PSSM_GREMLIN/login", methods=["GET"])
def login_page():
    if load_current_user() is not None:
        return redirect(url_for("task_dashboard"))
    return render_template("login.html")


@app.route("/PSSM_GREMLIN/register", methods=["GET"])
def register_page():
    if load_current_user() is not None:
        return redirect(url_for("task_dashboard"))
    if not ENABLE_REGISTER:
        return render_template("error.html", code=403, message="Registration is disabled on this server"), 403
    if not _smtp_configured():
        return render_template("error.html", code=403, message="Registration requires SMTP to be configured"), 403
    return render_template("register.html")


@app.route("/PSSM_GREMLIN/create_task", methods=["GET"])
@login_required
def create_task():
    return render_template("create_task.html")


@app.route("/PSSM_GREMLIN/profile", methods=["GET"])
@login_required
def profile_page():
    return render_template("profile.html")


@app.route("/favicon.ico", methods=["GET"])
def favicon():
    return send_from_directory(TEMPLATE_IMAGE_DIR, "logo.ico", mimetype="image/vnd.microsoft.icon")


@app.route("/PSSM_GREMLIN/logo.svg", methods=["GET"])
def logo_svg():
    return send_from_directory(TEMPLATE_IMAGE_DIR, "logo.svg", mimetype="image/svg+xml")


# ---------------------------------------------------------------------------
# Task API routes
# ---------------------------------------------------------------------------


@app.route("/PSSM_GREMLIN/api/post", methods=["POST"])
@login_required
def upload_file():
    if "file" not in request.files:
        return jsonify({"error": "No file part"}), 400

    uploaded_file = request.files["file"]
    if uploaded_file.filename == "":
        return jsonify({"error": "No selected file"}), 400

    safe_filename = secure_filename(uploaded_file.filename)
    if not safe_filename:
        return jsonify({"error": "Invalid filename"}), 400

    if not safe_filename.lower().endswith(".fasta"):
        return (
            jsonify({"error": "Uploaded file must have the .fasta extension"}),
            400,
        )

    upload_path = _safe_join(app.config["UPLOAD_FOLDER"], safe_filename)
    uploaded_file.save(upload_path)

    hasher = hashlib.md5(usedforsecurity=False)
    with open(upload_path, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            hasher.update(chunk)
    content_md5 = hasher.hexdigest()
    metadata = _request_metadata()
    md5sum = _task_id_for_upload(content_md5, metadata["username"])

    existing_task = task_store.get_task(md5sum)
    if existing_task and not _task_access_allowed(existing_task):
        return _task_access_denied(md5sum)
    if existing_task and existing_task["status"] == "finished":
        return redirect(f"/PSSM_GREMLIN/api/running/{md5sum}", code=302)

    if existing_task and existing_task["status"] in {"pending", "running", "packing results"}:
        return jsonify({"status": "Task already queued or running", "md5sum": md5sum}), 202

    result_dir = _safe_join(app.config["RESULTS_FOLDER"], md5sum)
    if os.path.exists(result_dir):
        shutil.rmtree(result_dir)
    os.makedirs(result_dir, exist_ok=True)
    result_fasta_path = _safe_join(result_dir, safe_filename)
    shutil.copy(upload_path, result_fasta_path)

    zip_path = _task_zip_path(md5sum)
    if os.path.exists(zip_path):
        os.remove(zip_path)

    is_binary = _is_binary_file(upload_path)
    now = time.time()
    base_record = {
        "filename": safe_filename,
        "file_path": upload_path,
        "result_dir": result_dir,
        "uploaded_at": now,
        "started_at": None,
        "finished_at": None,
        "walltime": None,
        "is_binary": int(is_binary),
        "source_ip": metadata["ip"],
        "user_agent": metadata["user_agent"],
        "username": metadata["username"],
        "request_headers": metadata["headers_json"],
        "local_user": _local_user_identity(),
        "celery_task_id": None,
        "run_stage": None,
    }

    if is_binary:
        task_store.upsert_task(
            md5sum,
            **base_record,
            status="failed",
            error="Binary file uploads are not supported.",
        )
        return jsonify({"error": "Uploaded file contains binary content"}), 400

    task_store.upsert_task(
        md5sum,
        **base_record,
        status="pending",
        error=None,
    )

    async_result = run_gremlin_task.apply_async(args=[md5sum])
    task_store.update_task(md5sum, celery_task_id=async_result.id)

    return redirect(f"/PSSM_GREMLIN/api/running/{md5sum}", code=302)


@app.route("/PSSM_GREMLIN/api/running/<md5sum>", methods=["GET"])
@login_required
def run_gremlin(md5sum):
    md5sum = _normalize_task_id(md5sum)
    if md5sum is None:
        return jsonify({"status": "bad_request", "message": "Invalid task id"}), 400
    task = task_store.get_task(md5sum)
    if not task:
        return jsonify({"status": "not_found", "md5sum": md5sum}), 404
    if not _task_access_allowed(task):
        return _task_access_denied(md5sum)

    status = task["status"]
    if status == "finished":
        return jsonify({"status": "finished", "md5sum": md5sum}), 200
    if status == "failed":
        return (
            jsonify({"status": "failed", "md5sum": md5sum, "error": _sanitize_task_error(task, task.get("error"))}),
            404,
        )
    if status == "running":
        return jsonify({"status": "running", "md5sum": md5sum}), 202
    if status == "pending":
        return jsonify({"status": "pending", "md5sum": md5sum}), 202
    if status == "packing results":
        return jsonify({"status": "packing results", "md5sum": md5sum}), 202
    if status == "cancelled":
        return jsonify({"status": "cancelled", "md5sum": md5sum}), 200
    if status == "deleted:finshed":
        return jsonify({"status": "deleted:finshed", "md5sum": md5sum}), 200
    if status == "deleted:cancel":
        return jsonify({"status": "deleted:cancel", "md5sum": md5sum}), 200

    return (
        jsonify({"status": "unknown", "md5sum": md5sum, "error": "Invalid task status"}),
        500,
    )


@app.route("/PSSM_GREMLIN/api/results/<md5sum>", methods=["GET"])
@login_required
def get_results(md5sum):
    md5sum = _normalize_task_id(md5sum)
    if md5sum is None:
        return jsonify({"status": "bad_request", "message": "Invalid task id"}), 400
    task = task_store.get_task(md5sum)
    if not task:
        return jsonify({"status": "not_found", "md5sum": md5sum}), 404
    if not _task_access_allowed(task):
        return _task_access_denied(md5sum)

    if task["status"] != "finished":
        return redirect(f"/PSSM_GREMLIN/api/running/{md5sum}", code=302)

    return redirect(f"/PSSM_GREMLIN/api/download/{md5sum}", code=302)


@app.route("/PSSM_GREMLIN/api/download/<md5sum>", methods=["GET"])
@login_required
def download_results(md5sum):
    md5sum = _normalize_task_id(md5sum)
    if md5sum is None:
        return jsonify({"status": "bad_request", "message": "Invalid task id"}), 400
    task = task_store.get_task(md5sum)
    if not task:
        return jsonify({"status": "not_found", "md5sum": md5sum}), 404
    if not _task_access_allowed(task):
        return _task_access_denied(md5sum)

    if task["status"] != "finished":
        return (
            jsonify(
                {
                    "status": "error",
                    "md5sum": md5sum,
                    "message": "results are not ready",
                }
            ),
            400,
        )

    zip_filename = _task_zip_path(task)
    if os.path.exists(zip_filename):
        return send_from_directory(
            app.config["RESULTS_FOLDER"],
            os.path.basename(zip_filename),
            as_attachment=True,
            download_name=_task_zip_download_name(task),
        )

    return (
        jsonify(
            {
                "status": "error",
                "md5sum": md5sum,
                "message": "result file not found",
            }
        ),
        404,
    )


@app.route("/PSSM_GREMLIN/api/cancel/<md5sum>", methods=["POST"])
@login_required
def cancel_task(md5sum):
    md5sum = _normalize_task_id(md5sum)
    if md5sum is None:
        return jsonify({"status": "bad_request", "message": "Invalid task id"}), 400
    task = task_store.get_task(md5sum)
    if not task:
        return jsonify({"error": "Task not found"}), 404
    if not _task_access_allowed(task):
        return _task_access_denied(md5sum)

    if task["status"] not in {"pending", "running"}:
        return (
            jsonify({"error": "Task cannot be cancelled as it is not pending or running"}),
            400,
        )

    celery_id = task.get("celery_task_id")
    if celery_id:
        try:
            result = AsyncResult(celery_id)
            result.revoke(terminate=True)
        except Exception as exc:  # pylint: disable=broad-except
            logging.warning("Failed to revoke Celery task %s: %s", celery_id, exc)

    _delete_task_artifacts(task)

    now = time.time()
    started_at = task.get("started_at")
    walltime = (now - started_at) if started_at else None
    task_store.update_task(
        md5sum,
        status="cancelled",
        finished_at=now,
        walltime=walltime,
        error="Task cancelled by user",
    )
    return jsonify({"status": "cancelled", "md5sum": md5sum}), 200


@app.route("/PSSM_GREMLIN/dashboard", methods=["GET"])
@login_required
def task_dashboard():
    current_user = _current_username() or ""
    is_admin = _is_admin_user(current_user)
    all_tasks = task_store.list_tasks()
    if is_admin or CONFIG.public_dashboard:
        scoped_tasks = all_tasks
    else:
        scoped_tasks = [task for task in all_tasks if task.get("username") == current_user]
    visible_tasks = [task for task in scoped_tasks if not _is_deleted_status(task.get("status"))]

    task_statuses = []
    for i, task in enumerate(visible_tasks):
        submitted_time = task.get("uploaded_at")
        finished_time = task.get("finished_at")
        walltime = task.get("walltime")
        if task.get("is_binary"):
            fasta_seq = "Binary file rejected"
        else:
            try:
                with open(task["file_path"]) as f:
                    fasta_seq = f.read().strip()
            except (OSError, UnicodeDecodeError) as exc:
                reason = "file not found" if isinstance(exc, FileNotFoundError) else "file unavailable"
                fasta_seq = (
                    f"Unable to read sequence: {reason} at "
                    f"{_virtual_upload_path(task.get('filename', 'unknown.fasta'))}"
                )

        task_statuses.append(
            {
                "id": i,
                "md5": task["md5sum"],
                "status": task["status"],
                "fasta_fn": task["filename"],
                "submitted_time": format_times(submitted_time),
                "finished_time": format_times(finished_time) if finished_time else "-",
                "walltime": format_walltime(walltime),
                "submitted_timestamp": submitted_time or 0,
                "sequence": fasta_seq,
                "owner": task.get("username") or "-",
                "can_delete": is_admin or (task.get("username") == current_user),
                "running_trace": _build_running_trace(task),
            }
        )

    sorted_task_statuses = sorted(task_statuses, key=lambda x: x["submitted_timestamp"], reverse=True)

    return render_template(
        "pssm_gremlin_dashboard.html",
        sorted_task_statuses=sorted_task_statuses,
        current_username=current_user,
        is_admin_user=is_admin,
    )


@app.route("/PSSM_GREMLIN/api/delete/<md5sum>", methods=["DELETE"])
@login_required
def delete_task(md5sum):
    md5sum = _normalize_task_id(md5sum)
    if md5sum is None:
        return jsonify({"status": "bad_request", "message": "Invalid task id"}), 400
    task = task_store.get_task(md5sum)
    if not task:
        return jsonify({"status": "not_found", "md5sum": md5sum}), 404
    if not _task_delete_allowed(task):
        return _task_access_denied(md5sum)

    if task["status"] in {"pending", "running", "packing results"}:
        _revoke_celery_task(task)

    _delete_task_artifacts(task)
    now = time.time()
    deleted_status = _deleted_status_from_task(task)
    started_at = task.get("started_at")
    walltime = task.get("walltime")
    if walltime is None and started_at:
        walltime = now - started_at
    finished_at = task.get("finished_at")
    if deleted_status == "deleted:cancel" or not finished_at:
        finished_at = now
    task_store.update_task(
        md5sum,
        status=deleted_status,
        finished_at=finished_at,
        walltime=walltime,
        error="Task deleted by user",
        celery_task_id=None,
    )
    return jsonify({"status": "deleted", "md5sum": md5sum}), 200


@app.route("/PSSM_GREMLIN/api/delete", methods=["POST"])
@login_required
def delete_tasks_batch():
    payload = request.get_json(silent=True) or {}
    md5sums = payload.get("md5sums")
    if not isinstance(md5sums, list):
        return jsonify({"error": "md5sums must be a JSON list"}), 400

    deleted: list[str] = []
    not_found: list[str] = []
    ignored: list[str] = []
    forbidden: list[str] = []
    seen: set[str] = set()

    for raw_md5 in md5sums:
        raw_md5_text = str(raw_md5).strip()
        md5sum = _normalize_task_id(raw_md5_text)
        if md5sum is None:
            if raw_md5_text:
                ignored.append(raw_md5_text)
            continue
        if md5sum in seen:
            continue
        seen.add(md5sum)

        task = task_store.get_task(md5sum)
        if not task:
            not_found.append(md5sum)
            continue
        if not _task_delete_allowed(task):
            forbidden.append(md5sum)
            continue

        if task["status"] in {"pending", "running", "packing results"}:
            _revoke_celery_task(task)
        _delete_task_artifacts(task)
        now = time.time()
        deleted_status = _deleted_status_from_task(task)
        started_at = task.get("started_at")
        walltime = task.get("walltime")
        if walltime is None and started_at:
            walltime = now - started_at
        finished_at = task.get("finished_at")
        if deleted_status == "deleted:cancel" or not finished_at:
            finished_at = now
        task_store.update_task(
            md5sum,
            status=deleted_status,
            finished_at=finished_at,
            walltime=walltime,
            error="Task deleted by user",
            celery_task_id=None,
        )
        deleted.append(md5sum)

    return (
        jsonify(
            {
                "status": "ok",
                "deleted": deleted,
                "not_found": not_found,
                "ignored": ignored,
                "forbidden": forbidden,
            }
        ),
        200,
    )


# ---------------------------------------------------------------------------
# Auth API routes
# ---------------------------------------------------------------------------


def _smtp_configured() -> bool:
    return bool(_env_str("SMTP_HOST", ""))


def _allowed_email_domains() -> set[str]:
    """Return the set of allowed email domains from ``ALLOWED_EMAIL_DOMAINS``.

    Empty set means all domains are allowed.
    """
    raw = _env_str("ALLOWED_EMAIL_DOMAINS", "")
    if not raw.strip():
        return set()
    return {d.strip().lower() for d in raw.split(",") if d.strip()}


def _normalize_email(email: str) -> str:
    """Normalize an email address: lowercase, strip ``+suffix`` from local part.

    ``user+tag@domain.com`` → ``user@domain.com`` — prevents one person
    from creating multiple accounts via plus-aliased addresses.
    """
    email = email.strip().lower()
    local, at, domain = email.partition("@")
    local = local.split("+")[0]
    return f"{local}{at}{domain}"


def _get_user_db() -> UserDatabase:
    return current_app.config["user_db"]  # type: ignore[no-any-return]


@app.route("/PSSM_GREMLIN/api/auth/login", methods=["POST"])
@rate_limit(max_requests=5, window_seconds=60)
def auth_login():
    """Exchange username+password for a Bearer token."""
    payload = request.get_json(silent=True) or {}
    username = str(payload.get("username", "")).strip()
    password = str(payload.get("password", "") or "")

    if not username or not password:
        return jsonify({"error": "Username and password are required"}), 400

    db = _get_user_db()
    user = db.get_user_by_username(username)
    if user is None or not check_password_hash(user["password_hash"], password):
        return jsonify({"error": "Invalid username or password"}), 401

    token = generate_token(user["id"])
    response = jsonify({"token": token, "username": user["username"]})
    # ponytail: set cookie so browser page navigations (not just fetch())
    # carry the auth token.  HttpOnly; SameSite=Lax prevents CSRF.
    response.set_cookie("auth_token", token, httponly=True, samesite="Lax")
    return response


@app.route("/PSSM_GREMLIN/api/auth/logout", methods=["POST"])
def auth_logout():
    """Clear the auth cookie.  No auth required — idempotent."""
    response = jsonify({"status": "logged_out"})
    response.set_cookie("auth_token", "", max_age=0, path="/")
    return response


@app.route("/PSSM_GREMLIN/api/auth/register", methods=["POST"])
@rate_limit(max_requests=3, window_seconds=3600)
def auth_register():
    """Register a new user account.

    Requires ``ENABLE_REGISTER=true`` AND a configured SMTP server.
    """
    if not ENABLE_REGISTER:
        return jsonify({"error": "Registration is disabled on this server"}), 403
    if not _smtp_configured():
        return jsonify({"error": "Registration requires SMTP to be configured"}), 403

    payload = request.get_json(silent=True) or {}
    username = str(payload.get("username", "")).strip()
    email = _normalize_email(str(payload.get("email", "")))
    password = str(payload.get("password", "") or "")

    # Basic validation
    if not username or not email or not password:
        return jsonify({"error": "Username, email, and password are required"}), 400
    if len(username) < 3 or len(username) > 64:
        return jsonify({"error": "Username must be between 3 and 64 characters"}), 400
    if len(password) < 8:
        return jsonify({"error": "Password must be at least 8 characters"}), 400
    if "@" not in email or "." not in email.split("@")[-1]:
        return jsonify({"error": "Invalid email address"}), 400

    # Domain allowlist
    allowed = _allowed_email_domains()
    if allowed:
        domain = email.partition("@")[2]
        if domain not in allowed:
            return jsonify({"error": f"Email domain @{domain} is not allowed"}), 400

    db = _get_user_db()
    if db.get_user_by_username(username):
        return jsonify({"error": "Username already taken"}), 409
    if db.get_user_by_email(email):
        return jsonify({"error": "Email address already registered"}), 409

    user = db.create_user(username=username, email=email, password=password)

    sent = send_verification_email(user)
    if not sent:
        logging.warning("Email verification failed for %r; account created but not verified", username)

    return (
        jsonify({"message": "Registration successful — check your email to verify your account", "username": username}),
        201,
    )


@app.route("/PSSM_GREMLIN/api/auth/verify-email", methods=["GET"])
def auth_verify_email():
    """Verify an email address via a one-time token (renders an HTML page)."""
    if not _smtp_configured():
        return (
            render_template(
                "verify-email.html",
                success=False,
                error="Email verification is not available — SMTP is not configured.",
            ),
            403,
        )

    token = request.args.get("token", "").strip()
    if not token:
        return render_template("verify-email.html", success=False, error="Missing verification token."), 400

    user_id = validate_email_token(token)
    if user_id is None:
        return render_template("verify-email.html", success=False, error="Invalid or expired verification token."), 400

    db = _get_user_db()
    user = db.get_user(user_id)
    if user is None:
        return render_template("verify-email.html", success=False, error="User not found."), 404

    db.verify_email(user_id)
    return render_template("verify-email.html", success=True, email=user["email"]), 200


@app.route("/PSSM_GREMLIN/api/auth/me", methods=["GET"])
@login_required
def auth_me():
    """Return the current authenticated user's profile."""
    user = g.current_user
    return (
        jsonify(
            {
                "username": user["username"],
                "email": user["email"],
                "email_verified": user["email_verified"],
                "is_admin": user["is_admin"],
            }
        ),
        200,
    )


@app.route("/PSSM_GREMLIN/api/auth/me", methods=["PUT"])
@login_required
def auth_update_me():
    """Change the current user's password."""
    if _blocked := require_web_login():
        return _blocked
    user = g.current_user
    payload = request.get_json(silent=True) or {}

    current_password = str(payload.get("current_password", "") or "")
    new_password = str(payload.get("new_password", "") or "")

    if not current_password or not new_password:
        return jsonify({"error": "current_password and new_password are required"}), 400
    if len(new_password) < 8:
        return jsonify({"error": "Password must be at least 8 characters"}), 400
    if not check_password_hash(user["password_hash"], current_password):
        return jsonify({"error": "Current password is incorrect"}), 401

    db = _get_user_db()
    db.update_user(user["id"], password_hash=generate_password_hash(new_password))
    return jsonify({"message": "Password updated"}), 200


# ---------------------------------------------------------------------------
# API key management (long-lived, user-revokable)
# ---------------------------------------------------------------------------


@app.route("/PSSM_GREMLIN/api/auth/me/api-key", methods=["GET"])
@login_required
def auth_api_key_status():
    """Return whether the current user has an active API key."""
    if _blocked := require_web_login():
        return _blocked
    db = _get_user_db()
    user = db.get_user(g.current_user["id"])
    has_key = bool(user and user.get("api_key_hash"))
    return jsonify({"has_api_key": has_key}), 200


@app.route("/PSSM_GREMLIN/api/auth/me/api-key", methods=["POST"])
@login_required
def auth_generate_api_key():
    """Generate a new API key — returns the plaintext key once."""
    if _blocked := require_web_login():
        return _blocked
    db = _get_user_db()
    plaintext = db.generate_api_key(g.current_user["id"])
    return jsonify({"api_key": plaintext, "message": "Store this key securely — it will not be shown again."}), 201


@app.route("/PSSM_GREMLIN/api/auth/me/api-key", methods=["DELETE"])
@login_required
def auth_revoke_api_key():
    """Revoke the current user's API key."""
    if _blocked := require_web_login():
        return _blocked
    db = _get_user_db()
    db.revoke_api_key(g.current_user["id"])
    return jsonify({"message": "API key revoked"}), 200


@app.route("/PSSM_GREMLIN/api/auth/admin/users", methods=["POST"])
@login_required
def admin_create_user():
    """Admin-only: create a new user account.

    Auto-verifies the email so the account is usable immediately.
    """
    if _blocked := require_web_login():
        return _blocked
    if not g.current_user.get("is_admin"):
        return jsonify({"error": "Admin access required"}), 403

    payload = request.get_json(silent=True) or {}
    username = str(payload.get("username", "")).strip()
    email = _normalize_email(str(payload.get("email", "")))
    password = str(payload.get("password", "") or "")

    if not username or not email or not password:
        return jsonify({"error": "Username, email, and password are required"}), 400
    if len(username) < 3 or len(username) > 64:
        return jsonify({"error": "Username must be between 3 and 64 characters"}), 400
    if len(password) < 8:
        return jsonify({"error": "Password must be at least 8 characters"}), 400
    if "@" not in email or "." not in email.split("@")[-1]:
        return jsonify({"error": "Invalid email address"}), 400

    db = _get_user_db()
    if db.get_user_by_username(username):
        return jsonify({"error": "Username already taken"}), 409
    if db.get_user_by_email(email):
        return jsonify({"error": "Email address already registered"}), 409

    new_user = db.create_user(
        username=username,
        email=email,
        password=password,
        is_admin=payload.get("is_admin", False),
    )
    db.verify_email(new_user["id"])  # admin-created accounts are pre-verified

    logging.info("Admin %r created user %r", g.current_user["username"], username)
    return jsonify({"message": "User created", "username": username}), 201
