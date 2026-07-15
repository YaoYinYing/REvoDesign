# Copyright (c) 2026 The REvoDesign Developers.
# Distributed under the terms of the GNU General Public License v3.0.
# SPDX-License-Identifier: GPL-3.0-only

"""HTTP route handlers for the GREMLIN server.

All ``@app.route`` decorators live here.  The module is imported by
``pssm_gremlin_server.__init__`` *after* ``pssm_gremlin_server.pssm_gremlin`` has
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
from flask import current_app, g, jsonify, redirect, render_template, request, send_from_directory, url_for
from pssm_gremlin_server.auth import (
    UserDatabase,
    _env_str,
    _is_account_blocked,
    generate_captcha,
    generate_token,
    load_current_user,
    login_required,
    optional_user,
    require_bearer_auth,
    require_web_login,
    send_approval_email,
    send_password_reset_email,
    send_rejection_email,
    send_verification_email,
    validate_captcha,
    validate_email_token,
    validate_reset_token,
)
from pssm_gremlin_server.pssm_gremlin import (
    CONFIG,
    ENABLE_REGISTER,
    TEMPLATE_IMAGE_DIR,
    _build_running_trace,
    _client_country,
    _client_ip,
    _current_username,
    _delete_task_artifacts,
    _deleted_status_from_task,
    _is_admin_user,
    _is_binary_file,
    _is_deleted_status,
    _is_fasta_content,
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
from pssm_gremlin_server.ratelimit import rate_limit
from pssm_gremlin_server.schemas import (
    AdminCreateUserRequest,
    AdminUpdateUserRequest,
    BatchUserRequest,
    ChangePasswordRequest,
    ForgotPasswordRequest,
    LoginRequest,
    RegisterRequest,
    ResetPasswordRequest,
    UserResponse,
)
from pydantic import ValidationError
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


@app.route("/PSSM_GREMLIN/terms", methods=["GET"])
def terms_page():
    return render_template("terms.html")


@app.route("/PSSM_GREMLIN/register", methods=["GET"])
def register_page():
    if load_current_user() is not None:
        return redirect(url_for("task_dashboard"))
    if not ENABLE_REGISTER:
        return render_template("error.html", code=403, message="Registration is disabled on this server"), 403
    if not _email_configured():
        return (
            render_template("error.html", code=403, message="Registration requires email service to be configured"),
            403,
        )
    return render_template("register.html")


@app.route("/PSSM_GREMLIN/create_task", methods=["GET"])
@login_required
def create_task():
    return render_template("create_task.html")


@app.route("/PSSM_GREMLIN/profile", methods=["GET"])
@login_required
def profile_page():
    return render_template("profile.html")


@app.route("/PSSM_GREMLIN/user_control", methods=["GET"])
@login_required
def user_control_page():
    """Admin-only user management page."""
    if not g.current_user.get("is_admin"):
        return render_template("error.html", code=403, message="Admin access required"), 403
    return render_template("user_control.html", is_admin_user=True)


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
@rate_limit(max_requests=30, window_seconds=3600)
def upload_file():
    if _blocked := require_bearer_auth():
        return _blocked
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

    # Save to a temp name first to avoid filename collisions — two users
    # uploading "seqs.fasta" would otherwise overwrite each other.
    temp_name = f".tmp_{os.urandom(8).hex()}_{safe_filename}"
    temp_path = _safe_join(app.config["UPLOAD_FOLDER"], temp_name)
    uploaded_file.save(temp_path)

    hasher = hashlib.md5(usedforsecurity=False)
    with open(temp_path, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            hasher.update(chunk)
    content_md5 = hasher.hexdigest()
    metadata = _request_metadata()
    md5sum = _task_id_for_upload(content_md5, metadata["username"])

    # Rename to the owner-scoped task ID so on-disk names are unique.
    upload_path = _safe_join(app.config["UPLOAD_FOLDER"], f"{md5sum}.fasta")
    os.rename(temp_path, upload_path)

    existing_task = task_store.get_task(md5sum)
    if existing_task and not _task_access_allowed(existing_task):
        return _task_access_denied(md5sum)
    if existing_task and existing_task["status"] == "finished":
        return redirect(f"/PSSM_GREMLIN/api/running/{md5sum}", code=302)

    if existing_task and existing_task["status"] in {"pending", "running", "packing results"}:
        return jsonify({"status": "Task already queued or running", "md5sum": md5sum}), 202

    # ponytail: per-user cap on active tasks — the expensive resource is the
    # Celery/Docker queue, not the HTTP layer.  Raise MAX_ACTIVE_TASKS_PER_USER
    # if users routinely hit it with legitimate batch work.
    MAX_ACTIVE_TASKS_PER_USER = 5
    if task_store.count_user_active_tasks(metadata["username"]) >= MAX_ACTIVE_TASKS_PER_USER:
        return (
            jsonify(
                {
                    "error": "Too many pending or running tasks. "
                    "Please wait for existing tasks to complete before submitting new ones."
                }
            ),
            429,
        )

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

    if not _is_fasta_content(upload_path):
        task_store.upsert_task(
            md5sum,
            **base_record,
            status="failed",
            error="Uploaded file does not appear to be a valid FASTA file.",
        )
        return jsonify({"error": "Uploaded file does not appear to be a valid FASTA file"}), 400

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

    if task["status"] not in {"finished", "failed"}:
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

    if task["status"] not in {"finished", "failed"}:
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
    if not os.path.exists(zip_filename):
        # Pack on-the-fly for failed tasks where the result dir survives.
        result_dir = task.get("result_dir")
        if result_dir and os.path.isdir(result_dir):
            zip_base = os.path.splitext(zip_filename)[0]
            shutil.make_archive(zip_base, "zip", result_dir)
        else:
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

    return send_from_directory(
        app.config["RESULTS_FOLDER"],
        os.path.basename(zip_filename),
        as_attachment=True,
        download_name=_task_zip_download_name(task),
    )


@app.route("/PSSM_GREMLIN/api/cancel/<md5sum>", methods=["POST"])
@login_required
def cancel_task(md5sum):
    if _blocked := require_bearer_auth():
        return _blocked
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
                "error": task.get("error") or None,
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
    if _blocked := require_bearer_auth():
        return _blocked
    if _blocked := _reject_guest():
        return _blocked
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
    if _blocked := require_bearer_auth():
        return _blocked
    if _blocked := _reject_guest():
        return _blocked
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


def _email_configured() -> bool:
    """Return True if email sending is configured (Resend or SMTP)."""
    return bool(_env_str("RESEND_API_KEY", "") or _env_str("SMTP_HOST", ""))


def _allowed_email_domains() -> set[str]:
    """Return the set of allowed email domains from ``ALLOWED_EMAIL_DOMAINS``.

    Empty set means all domains are allowed.
    """
    raw = _env_str("ALLOWED_EMAIL_DOMAINS", "")
    if not raw.strip():
        return set()
    return {d.strip().lower() for d in raw.split(",") if d.strip()}


def _get_user_db() -> UserDatabase:
    return current_app.config["user_db"]  # type: ignore[no-any-return]


def require_admin():
    """Return 403 if the current user is not an admin (DB ``is_admin`` column)."""
    if _blocked := require_web_login():
        return _blocked
    if not g.current_user.get("is_admin"):
        return jsonify({"error": "Admin access required"}), 403
    return None


def _reject_guest():
    """Return 403 if the current user is a guest account."""
    if g.current_user.get("role") == "guest":
        return jsonify({"error": "Guest accounts cannot perform this action"}), 403
    return None


def _parse_body(model_cls: type):
    """Validate request JSON against *model_cls*.  Returns the model instance
    or a ``(json_response, status_code)`` error tuple."""
    try:
        return model_cls.model_validate(request.get_json(silent=True) or {})
    except ValidationError as e:
        return jsonify({"error": e.errors()[0]["msg"]}), 400


@app.route("/PSSM_GREMLIN/api/auth/login", methods=["POST"])
@rate_limit(max_requests=5, window_seconds=60)
def auth_login():
    """Exchange username+password for a Bearer token.

    Accepts a ``username`` field that may be either a username or an email
    address — admin-created users may only know their email.
    """
    req = _parse_body(LoginRequest)
    if isinstance(req, tuple):
        return req

    db = _get_user_db()
    if "@" in req.login_id:
        user = db.get_user_by_email(req.login_id)  # already normalised by schema
    else:
        user = db.get_user_by_username(req.login_id)
    if user is None or not check_password_hash(user["password_hash"], req.password):
        return jsonify({"error": "Invalid username or password"}), 401

    if blocked := _is_account_blocked(user):
        return jsonify({"error": blocked}), 403

    token = generate_token(user["id"])
    response = jsonify({"token": token, "username": user["username"]})
    # ponytail: set cookie so browser page navigations (not just fetch())
    # carry the auth token.  HttpOnly; SameSite=Lax prevents CSRF.
    # secure=True only when SERVER_BASE_URL uses https — plain-http dev
    # environments would silently drop Secure cookies.
    _cookie_secure = _env_str("SERVER_BASE_URL", "http://localhost:8080").startswith("https://")
    response.set_cookie("auth_token", token, httponly=True, samesite="Lax", secure=_cookie_secure)
    return response


@app.route("/PSSM_GREMLIN/api/auth/forgot-password", methods=["POST"])
@rate_limit(max_requests=3, window_seconds=3600)
def auth_forgot_password():
    """Send a password-reset link to the given email address."""
    if not _email_configured():
        return jsonify({"error": "Password reset requires email service to be configured"}), 503

    req = _parse_body(ForgotPasswordRequest)
    if isinstance(req, tuple):
        return req
    email = req.email

    if not email or "@" not in email:
        # Don't leak whether the email is registered
        return jsonify({"message": "If that email is registered, a reset link has been sent."}), 200

    db = _get_user_db()
    send_password_reset_email(email, db)
    return jsonify({"message": "If that email is registered, a reset link has been sent."}), 200


@app.route("/PSSM_GREMLIN/reset_password", methods=["GET", "POST"])
def auth_reset_password():
    """Password-reset page.

    ``GET`` — renders the new-password form (requires ``?c=`` token).
    ``POST`` — sets the new password.
    """
    if request.method == "GET":
        token = request.args.get("c", "").strip()
        if not token:
            return render_template("error.html", code=400, message="Missing reset token."), 400
        user_id = validate_reset_token(token)
        if user_id is None:
            return render_template("error.html", code=400, message="Invalid or expired reset token."), 400
        return render_template("reset-password.html", token=token), 200

    # POST
    req = _parse_body(ResetPasswordRequest)
    if isinstance(req, tuple):
        return req

    user_id = validate_reset_token(req.token)
    if user_id is None:
        return jsonify({"error": "Invalid or expired reset token"}), 400

    db = _get_user_db()
    db.update_user(user_id, password_hash=generate_password_hash(req.password))
    logging.info("User %d reset their password", user_id)
    return jsonify({"message": "Password updated — you can now log in."}), 200


@app.route("/PSSM_GREMLIN/api/auth/logout", methods=["POST"])
def auth_logout():
    """Clear the auth cookie.  No auth required — idempotent."""
    response = jsonify({"status": "logged_out"})
    response.set_cookie("auth_token", "", max_age=0, path="/")
    return response


@app.route("/PSSM_GREMLIN/api/auth/captcha", methods=["GET"])
def auth_captcha():
    """Return a math CAPTCHA challenge with a signed token (5-min expiry)."""
    question, token = generate_captcha()
    return jsonify({"question": question, "token": token}), 200


@app.route("/PSSM_GREMLIN/api/auth/register", methods=["POST"])
@rate_limit(max_requests=3, window_seconds=3600)
def auth_register():
    """Register a new user account.

    Requires ``ENABLE_REGISTER=true`` AND a configured email service (Resend).
    """
    if not ENABLE_REGISTER:
        return jsonify({"error": "Registration is disabled on this server"}), 403
    if not _email_configured():
        return jsonify({"error": "Registration requires email service to be configured"}), 403

    req = _parse_body(RegisterRequest)
    if isinstance(req, tuple):
        return req

    # CAPTCHA — block bot / programmatic registration
    if not validate_captcha(req.captcha_token, req.captcha_answer):
        return jsonify({"error": "CAPTCHA validation failed. Please try again."}), 400

    # Domain allowlist
    allowed = _allowed_email_domains()
    if allowed:
        domain = req.email.partition("@")[2]
        if domain not in allowed:
            return jsonify({"error": f"Email domain @{domain} is not allowed"}), 400

    db = _get_user_db()
    if db.get_user_by_username(req.username):
        return jsonify({"error": "Username already taken"}), 409
    if db.get_user_by_email(req.email):
        return jsonify({"error": "Email address already registered"}), 409

    user = db.create_user(
        username=req.username,
        email=req.email,
        password=req.password,
        affiliation=req.affiliation,
        terms_agreed=req.terms_agreed,
        registration_ip=_client_ip(),
        registration_country=_client_country(),
    )

    sent = send_verification_email(user)
    if not sent:
        logging.warning("Email verification failed for %r; account created but not verified", req.username)

    if sent:
        message = "Registration successful — check your email to verify your account."
    else:
        message = (
            "Account created, but the verification email could not be sent. "
            + "Contact an administrator to verify your account."
        )

    return jsonify({"message": message, "username": req.username, "email_sent": sent}), 201


@app.route("/PSSM_GREMLIN/api/auth/resend-verification", methods=["POST"])
@rate_limit(max_requests=10, window_seconds=3600)
def auth_resend_verification():
    """Resend the verification email for an unverified account.

    Per-email backoff: first resend is immediate, then 10×n minutes where
    *n* is the number of previous resends.
    """
    req = _parse_body(ForgotPasswordRequest)
    if isinstance(req, tuple):
        return req

    email = req.email
    if not email or "@" not in email:
        return (
            jsonify({"message": "If that email is registered and unverified, a new verification email has been sent."}),
            200,
        )

    db = _get_user_db()
    user = db.get_user_by_email(email)
    if user is None:
        return jsonify({"error": "No account found with this email address"}), 404

    if user.get("deleted"):
        return jsonify({"error": "Account has been deleted"}), 403
    if user.get("user_status") == "banned":
        return jsonify({"error": "Account has been suspended"}), 403

    if user.get("email_verified"):
        return jsonify({"message": "This email is already verified. You can log in."}), 200

    # Per-email backoff: 10×n minutes since last resend
    count = user.get("verification_resend_count") or 0
    last_at = user.get("verification_resend_at")
    if last_at and count > 0:
        cooldown = 10 * 60 * count  # seconds
        elapsed = time.time() - last_at
        if elapsed < cooldown:
            remaining = int((cooldown - elapsed) / 60) + 1
            return jsonify({"error": f"Please wait {remaining} min before requesting another verification email"}), 429

    sent = send_verification_email(user)
    if not sent:
        return jsonify({"error": "Failed to send verification email. Contact an administrator."}), 500

    db.update_user(user["id"], verification_resend_count=count + 1, verification_resend_at=time.time())
    return jsonify({"message": "Verification email sent. Check your inbox."}), 200


@app.route("/PSSM_GREMLIN/api/auth/verify-email", methods=["GET"])
def auth_verify_email():
    """Verify an email address via a one-time token (renders an HTML page)."""
    if not _email_configured():
        return (
            render_template(
                "verify-email.html",
                success=False,
                error="Email verification is not available — email service is not configured.",
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
    db.update_user(user_id, registration_status="verified")
    return (
        render_template(
            "verify-email.html",
            success=True,
            email=user["email"],
            registration_pending=user.get("user_status") != "active",
        ),
        200,
    )


@app.route("/PSSM_GREMLIN/user_verify", methods=["GET"])
def auth_user_verify():
    """Verify email via serializer token (2-day expiry)."""
    token = request.args.get("c", "").strip()
    if not token:
        return render_template("verify-email.html", success=False, error="Missing verification token."), 400

    user_id = validate_email_token(token)
    if user_id is None:
        return (
            render_template(
                "verify-email.html",
                success=False,
                error="Invalid or expired verification token (valid for 2 days).",
            ),
            400,
        )

    db = _get_user_db()
    user = db.get_user(user_id)
    if user is None:
        return render_template("verify-email.html", success=False, error="User not found."), 404

    db.verify_email(user_id)
    db.update_user(user_id, registration_status="verified")
    # user_status stays "pending" — admin must approve
    return (
        render_template(
            "verify-email.html",
            success=True,
            email=user["email"],
            registration_pending=user.get("user_status") != "active",
        ),
        200,
    )


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
                "role": user.get("role", "user"),
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
    if _blocked := _reject_guest():
        return _blocked
    if _blocked := require_bearer_auth():
        return _blocked
    user = g.current_user
    req = _parse_body(ChangePasswordRequest)
    if isinstance(req, tuple):
        return req

    if not check_password_hash(user["password_hash"], req.current_password):
        return jsonify({"error": "Current password is incorrect"}), 401

    db = _get_user_db()
    db.update_user(user["id"], password_hash=generate_password_hash(req.new_password))
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
    if _blocked := _reject_guest():
        return _blocked
    if _blocked := require_bearer_auth():
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
    if _blocked := _reject_guest():
        return _blocked
    if _blocked := require_bearer_auth():
        return _blocked
    db = _get_user_db()
    db.revoke_api_key(g.current_user["id"])
    return jsonify({"message": "API key revoked"}), 200


@app.route("/PSSM_GREMLIN/api/auth/admin/users", methods=["GET", "POST"])
@login_required
def admin_users():
    """Admin-only user management.

    ``GET`` — list all users (safe fields only).
    ``POST`` — create a new user (auto-verified, immediately active).
    """
    if _blocked := require_admin():
        return _blocked

    db = _get_user_db()

    if request.method == "GET":
        users = db.list_users()
        safe = [UserResponse.model_validate(u).model_dump() for u in users]
        return jsonify({"users": safe}), 200

    # POST — state-changing, require Bearer token for CSRF protection
    if _blocked := require_bearer_auth():
        return _blocked
    req = _parse_body(AdminCreateUserRequest)
    if isinstance(req, tuple):
        return req

    if db.get_user_by_username(req.username):
        return jsonify({"error": "Username already taken"}), 409
    if db.get_user_by_email(req.email):
        return jsonify({"error": "Email address already registered"}), 409

    new_user = db.create_user(
        username=req.username,
        email=req.email,
        password=req.password,
        is_admin=req.is_admin or (req.role == "admin"),
        role=req.role,
        affiliation=req.affiliation,
        registration_status="approved",
        user_status="active",
    )
    db.verify_email(new_user["id"])  # admin-created accounts are pre-verified

    logging.info("Admin %r created user %r", g.current_user["username"], req.username)
    return jsonify({"message": "User created", "username": req.username}), 201


@app.route("/PSSM_GREMLIN/api/auth/admin/users/<int:user_id>", methods=["PUT", "DELETE"])
@login_required
def admin_manage_user(user_id):
    """Admin-only: update user status or delete a user.

    ``PUT`` — update ``registration_status``, ``user_status``, or ``is_admin``.
    ``DELETE`` — permanently remove the user.
    """
    if _blocked := require_admin():
        return _blocked
    if _blocked := require_bearer_auth():
        return _blocked

    db = _get_user_db()
    user = db.get_user(user_id)
    if not user:
        return jsonify({"error": "User not found"}), 404
    is_self = user_id == g.current_user["id"]

    if request.method == "DELETE":
        if is_self:
            return jsonify({"error": "Administrators cannot delete their own account"}), 400
        # ponytail: soft-delete — hides from user table, recoverable.
        db.update_user(user_id, deleted=True)
        logging.info("Admin %r soft-deleted user %r", g.current_user["username"], user.get("username"))
        return jsonify({"message": "User deleted"}), 200

    # PUT
    req = _parse_body(AdminUpdateUserRequest)
    if isinstance(req, tuple):
        return req

    # Build update dict from set fields only (all optional)
    update_fields: dict[str, Any] = {}
    if req.email is not None:
        email = req.email
        existing = db.get_user_by_email(email)
        if existing and existing["id"] != user_id:
            return jsonify({"error": "Email address already in use"}), 409
        update_fields["email"] = email
    if is_self and req.user_status == "banned":
        return jsonify({"error": "Administrators cannot ban their own account"}), 400
    if req.affiliation is not None:
        update_fields["affiliation"] = req.affiliation
    if req.password is not None:
        update_fields["password_hash"] = generate_password_hash(req.password)
    if req.registration_status is not None:
        update_fields["registration_status"] = req.registration_status
        # Admin approval implies email verification — avoid the gap where
        # an unverified self-registered account becomes active without
        # proving email ownership.
        if req.registration_status == "approved" and not user.get("email_verified"):
            db.verify_email(user_id)
    if req.user_status is not None:
        update_fields["user_status"] = req.user_status
    if req.role is not None:
        if is_self:
            return jsonify({"error": "Administrators cannot change their own role"}), 400
        update_fields["role"] = req.role
        if req.role == "admin":
            update_fields["is_admin"] = True

    # Only set approved_by / approved_at when the admin is actually approving.
    new_reg = update_fields.get("registration_status")
    if new_reg == "approved":
        update_fields["approved_by"] = g.current_user["id"]
        update_fields["approved_at"] = time.time()

    if update_fields:
        db.update_user(user_id, **update_fields)

        # Notify user on approval or rejection (use refreshed data).
        if new_reg == "approved":
            approved_user = db.get_user(user_id) or user
            if not send_approval_email(approved_user):
                logging.warning("Approval email failed for %r", approved_user["email"])
        elif new_reg == "rejected":
            if not send_rejection_email(user):
                logging.warning("Rejection email failed for %r", user["email"])

    return jsonify({"message": "User updated"}), 200


@app.route("/PSSM_GREMLIN/api/auth/admin/users/batch", methods=["POST"])
@login_required
def admin_batch_users():
    """Admin-only batch operations on users.

    Accepts ``{"action": "enable"|"disable"|"delete", "user_ids": [...]}``.
    """
    if _blocked := require_admin():
        return _blocked
    if _blocked := require_bearer_auth():
        return _blocked

    req = _parse_body(BatchUserRequest)
    if isinstance(req, tuple):
        return req

    db = _get_user_db()
    now = time.time()
    admin_id = g.current_user["id"]

    if req.action == "enable":
        updates = {
            "user_status": "active",
            "registration_status": "approved",
            "deleted": False,
            "approved_by": admin_id,
            "approved_at": now,
        }
    elif req.action == "disable":
        updates = {"user_status": "banned", "approved_by": admin_id, "approved_at": now}
    else:  # delete
        updates = {"deleted": True}

    count = 0
    for uid in req.user_ids:
        user = db.get_user(uid)
        if user is None:
            continue
        if uid == admin_id and req.action in {"disable", "delete"}:
            continue  # don't let an admin lock themselves out
        if user.get("is_admin") and req.action == "disable":
            continue  # don't disable other admins
        db.update_user(uid, **updates)
        count += 1

    return jsonify({"message": f"{req.action} action applied to {count} user(s)", "count": count}), 200
