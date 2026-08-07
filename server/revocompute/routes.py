# Copyright (c) 2026 The REvoDesign Developers.
# Distributed under the terms of the GNU General Public License v3.0.
# SPDX-License-Identifier: GPL-3.0-only

"""HTTP route handlers for the REvoCompute server.

All ``@app.route`` decorators live here.  The module is imported by
``revocompute.__init__`` *after* ``revocompute.app`` has
created the Flask ``app``, so the decorators register against an
already-initialised application.
"""

from __future__ import annotations

import hashlib
import json
import logging
import os
import re
import shutil
import time
from datetime import datetime
from pathlib import Path
from typing import Any

from celery.result import AsyncResult
from flask import Response, current_app, g, jsonify, redirect, render_template, request, send_from_directory, url_for
from pydantic import ValidationError
from revocompute.app import (
    ENABLE_REGISTER,
    TEMPLATE_IMAGE_DIR,
    _client_country,
    _client_ip,
    _current_username,
    _delete_task_artifacts,
    _deleted_status_from_task,
    _is_admin_user,
    _is_binary_file,
    _is_deleted_status,
    _is_fasta_content,
    _request_metadata,
    _revoke_celery_task,
    _task_access_allowed,
    _task_access_denied,
    _task_delete_allowed,
    _task_id_for_upload,
    _task_zip_download_name,
    app,
)
from revocompute.auth import (
    _DUMMY_PASSWORD_HASH,
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
from revocompute.ratelimit import rate_limit
from revocompute.schemas import (
    AdminCreateUserRequest,
    AdminUpdateUserRequest,
    BatchUserRequest,
    ChangePasswordRequest,
    ForgotPasswordRequest,
    LoginRequest,
    RegisterRequest,
    ResetPasswordRequest,
    TaskSubmissionRequest,
    UserResponse,
)
from revocompute.task_runtime import (
    _build_running_trace,
    _get_task_type,
    _local_user_identity,
    _normalize_task_id,
    _pack_failed_results_archive,
    _safe_join,
    _sanitize_task_error,
    _task_zip_path,
    _virtual_upload_path,
    format_times,
    format_walltime,
    run_compute_task,
    task_store,
)
from revocompute.task_types import list_types
from werkzeug.security import check_password_hash, generate_password_hash
from werkzeug.utils import secure_filename

# ---------------------------------------------------------------------------
# Page routes
# ---------------------------------------------------------------------------


@app.route("/compute/login", methods=["GET"])
def login_page():
    if load_current_user() is not None:
        return redirect(url_for("task_dashboard"))
    return render_template("login.html")


@app.route("/compute/terms", methods=["GET"])
def terms_page():
    return render_template("terms.html")


@app.route("/compute/register", methods=["GET"])
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


@app.route("/compute/create_task", methods=["GET"])
@login_required
def create_task():
    return render_template("create_task.html")


@app.route("/compute/profile", methods=["GET"])
@login_required
def profile_page():
    return render_template("profile.html")


@app.route("/compute/user_control", methods=["GET"])
@login_required
def user_control_page():
    """Admin-only user management page."""
    if g.current_user.get("role") != "admin":
        return render_template("error.html", code=403, message="Admin access required"), 403
    return render_template("user_control.html", is_admin_user=True)


@app.route("/compute/logs", methods=["GET"])
@login_required
def log_viewer_page():
    """Admin-only active-log viewer."""
    if g.current_user.get("role") != "admin":
        return render_template("error.html", code=403, message="Admin access required"), 403
    return render_template("log_viewer.html")


@app.route("/favicon.ico", methods=["GET"])
def favicon():
    return send_from_directory(TEMPLATE_IMAGE_DIR, "logo.ico", mimetype="image/vnd.microsoft.icon")


@app.route("/compute/logo.svg", methods=["GET"])
def logo_svg():
    return send_from_directory(TEMPLATE_IMAGE_DIR, "logo.svg", mimetype="image/svg+xml")


@app.route("/PSSM_GREMLIN/")
def legacy_dashboard_redirect():
    """302 redirect to the current dashboard root."""
    return redirect(url_for("task_dashboard")), 302


# ---------------------------------------------------------------------------
# Task API routes
# ---------------------------------------------------------------------------


@app.route("/compute/api/types", methods=["GET"])
def task_types_list():
    """Return registered task types (public — needed by the create-task page)."""
    types_data = [
        {
            "name": tt.name,
            "display_name": tt.display_name,
            "input_extension": tt.input_extension,
            "input_label": tt.input_label,
            "params": [
                {"name": p.name, "type": p.type, "default": p.default, "description": p.description} for p in tt.params
            ],
            "stage_markers": tt.stage_markers,
        }
        for tt in list_types()
    ]
    return jsonify(types_data)


@app.route("/compute/api/types/<name>", methods=["GET"])
def task_type_form(name: str):
    """Return a single task type's full form definition (public).

    The client fetches this when the user selects a task type, then
    dynamically builds the upload form from the response.
    """
    try:
        tt, _ = _get_task_type(name)
    except KeyError:
        return jsonify({"error": f"Unknown task type: {name!r}"}), 404

    return jsonify(
        {
            "name": tt.name,
            "display_name": tt.display_name,
            "file_input": {
                "accept": tt.input_extension,
                "label": tt.input_label,
                "required": True,
            },
            "params": [
                {"name": p.name, "type": p.type, "default": p.default, "description": p.description} for p in tt.params
            ],
            "show_sequence_editor": tt.input_extension == ".fasta",
        }
    )


def _validate_input_upload(task_type: str = "gremlin"):
    """Return a validated upload and safe filename, or an HTTP error."""
    if "file" not in request.files:
        return None, None, (jsonify({"error": "No file part"}), 400)

    uploaded_file = request.files["file"]
    if uploaded_file.filename == "":
        return None, None, (jsonify({"error": "No selected file"}), 400)

    safe_filename = secure_filename(uploaded_file.filename)
    if not safe_filename:
        return None, None, (jsonify({"error": "Invalid filename"}), 400)

    try:
        tt, _ = _get_task_type(task_type)
    except KeyError:
        return None, None, (jsonify({"error": f"Unknown task type: {task_type}"}), 400)

    ext = tt.input_extension
    if not safe_filename.lower().endswith(ext.lower()):
        return None, None, (jsonify({"error": f"Uploaded file must have the {ext} extension"}), 400)
    return uploaded_file, safe_filename, None


def _save_uploaded_fasta(uploaded_file, safe_filename: str) -> tuple[str, str, dict[str, str]]:
    """Persist one upload and return its task ID, path, and request metadata."""
    temp_name = f".tmp_{os.urandom(8).hex()}_{safe_filename}"
    temp_path = _safe_join(app.config["UPLOAD_FOLDER"], temp_name)
    uploaded_file.save(temp_path)

    hasher = hashlib.md5(usedforsecurity=False)
    with open(temp_path, "rb") as handle:
        for chunk in iter(lambda: handle.read(65536), b""):
            hasher.update(chunk)

    metadata = _request_metadata()
    md5sum = _task_id_for_upload(hasher.hexdigest(), metadata["username"])
    upload_path = _safe_join(app.config["UPLOAD_FOLDER"], f"{md5sum}.fasta")
    os.rename(temp_path, upload_path)
    return md5sum, upload_path, metadata


def _existing_upload_response(existing_task: dict[str, Any] | None, md5sum: str):
    if not existing_task:
        return None
    if not _task_access_allowed(existing_task):
        return _task_access_denied(md5sum)
    if existing_task["status"] == "finished":
        return redirect(f"/compute/api/running/{md5sum}", code=302)
    if existing_task["status"] in {
        "pending",
        "running",
        "packing results",
        *task_store.CLEANUP_CLAIM_STATUSES,
    }:
        return jsonify({"status": "Task already queued or running", "md5sum": md5sum}), 202
    return None


def _prepare_task_record(
    md5sum: str,
    upload_path: str,
    safe_filename: str,
    metadata: dict[str, str],
    task_type: str = "gremlin",
    input_form: dict[str, Any] | None = None,
) -> dict[str, Any]:
    result_dir = _safe_join(app.config["RESULTS_FOLDER"], md5sum)
    if os.path.exists(result_dir):
        shutil.rmtree(result_dir)
    os.makedirs(result_dir, exist_ok=True)
    shutil.copy(upload_path, _safe_join(result_dir, safe_filename))

    zip_path = _task_zip_path(md5sum)
    if os.path.exists(zip_path):
        os.remove(zip_path)

    return {
        "filename": safe_filename,
        "file_path": upload_path,
        "result_dir": result_dir,
        "uploaded_at": time.time(),
        "started_at": None,
        "finished_at": None,
        "walltime": None,
        "is_binary": int(_is_binary_file(upload_path)),
        "source_ip": metadata["ip"],
        "user_agent": metadata["user_agent"],
        "username": metadata["username"],
        "request_headers": metadata["headers_json"],
        "local_user": _local_user_identity(),
        "celery_task_id": None,
        "run_stage": None,
        "task_type": task_type,
        "input_form": json.dumps(input_form) if input_form else None,
    }


def _reject_invalid_fasta(md5sum: str, base_record: dict[str, Any]):
    upload_path = base_record["file_path"]
    if base_record["is_binary"]:
        error_message = "Binary file uploads are not supported."
        response_message = "Uploaded file contains binary content"
    elif not _is_fasta_content(upload_path):
        error_message = "Uploaded file does not appear to be a valid FASTA file."
        response_message = "Uploaded file does not appear to be a valid FASTA file"
    else:
        return None

    failed_task = {**base_record, "md5sum": md5sum, "status": "failed", "error": error_message}
    task_store.upsert_task(md5sum, **base_record, status="failed", error=error_message)
    _pack_failed_results_archive(failed_task, error_message)
    return jsonify({"error": response_message}), 400


@app.route("/compute/api/post", methods=["POST"])
@login_required
@rate_limit(max_requests=30, window_seconds=3600)
def upload_file():  # skipcq: PY-R1000 -- route validation branches form one transactional request boundary.
    if _blocked := require_bearer_auth():
        return _blocked

    # Parse flat form data ("params[key]=value") into nested dict
    raw_form = request.form.to_dict(flat=True)
    form_data: dict[str, Any] = {}
    nested_params: dict[str, Any] = {}
    for key, value in raw_form.items():
        if key.startswith("params[") and key.endswith("]"):
            nested_params[key[len("params[") : -1]] = value
        else:
            form_data[key] = value
    if nested_params:
        form_data["params"] = nested_params

    try:
        submission = TaskSubmissionRequest.model_validate(form_data)
    except ValidationError as exc:
        errors = [{"field": ".".join(str(p) for p in e["loc"]), "message": e["msg"]} for e in exc.errors()]
        return jsonify({"error": "Validation failed", "details": errors}), 400

    task_type = submission.task_type
    coerced_params = submission.coerce_params()

    uploaded_file, safe_filename, upload_error = _validate_input_upload(task_type)
    if upload_error is not None:
        return upload_error
    md5sum, upload_path, metadata = _save_uploaded_fasta(uploaded_file, safe_filename)

    existing_task = task_store.get_task(md5sum)
    if existing_response := _existing_upload_response(existing_task, md5sum):
        return existing_response

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

    # Build entities — one list for files and params together.
    entities: list[dict[str, Any]] = []

    # File entity
    result_dir = _safe_join(app.config["RESULTS_FOLDER"], md5sum)
    entities.append(
        {
            "name": "file",
            "type": "file",
            "value": uploaded_file.filename,
            "verified_value": safe_filename,
            "stored_at": os.path.join(result_dir, safe_filename),
            "mounted": f"/workspace/inputs/{safe_filename}",
            "hash": md5sum,
        }
    )

    # Param entities — raw form value vs pydantic-coerced verified_value
    tt, _ = _get_task_type(task_type)
    known_params = {p.name: p for p in tt.params}
    for key, raw in submission.params.items():
        param = known_params[key]
        entities.append(
            {
                "name": key,
                "type": param.type,
                "value": raw,
                "verified_value": coerced_params[key],
            }
        )

    input_form = {
        "user": metadata["username"],
        "submitted_at": datetime.now(tz=datetime.timezone.utc).isoformat(),
        "entities": entities,
    }

    base_record = _prepare_task_record(
        md5sum,
        upload_path,
        safe_filename,
        metadata,
        task_type=task_type,
        input_form=input_form,
    )
    if invalid_response := _reject_invalid_fasta(md5sum, base_record):
        return invalid_response

    task_store.upsert_task(
        md5sum,
        **base_record,
        status="pending",
        error=None,
    )

    try:
        async_result = run_compute_task.apply_async(args=[md5sum], kwargs={"task_type": task_type})
    except Exception:
        logging.exception("Failed to submit compute task %s to Celery", md5sum)
        error_message = "Task queue unavailable — please try again later"
        failed_task = task_store.get_task(md5sum) or dict(md5sum=md5sum, **base_record)
        _pack_failed_results_archive(failed_task, error_message)
        task_store.update_task(
            md5sum,
            status="failed",
            error=error_message,
        )
        return jsonify({"error": error_message}), 503
    task_store.update_task(md5sum, celery_task_id=async_result.id)

    return redirect(f"/compute/api/running/{md5sum}", code=302)


@app.route("/compute/api/running/<md5sum>", methods=["GET"])
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
    if status in task_store.CLEANUP_CLAIM_STATUSES:
        return jsonify({"status": status, "md5sum": md5sum}), 202
    if status in task_store.CLEANUP_STATUSES:
        return jsonify({"status": status, "md5sum": md5sum}), 200
    if status == "deleted:finshed":
        return jsonify({"status": "deleted:finshed", "md5sum": md5sum}), 200
    if status == "deleted:cancel":
        return jsonify({"status": "deleted:cancel", "md5sum": md5sum}), 200

    return (
        jsonify({"status": "unknown", "md5sum": md5sum, "error": "Invalid task status"}),
        500,
    )


@app.route("/compute/api/results/<md5sum>", methods=["GET"])
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
        return redirect(f"/compute/api/running/{md5sum}", code=302)

    return redirect(f"/compute/api/download/{md5sum}", code=302)


@app.route("/compute/api/download/<md5sum>", methods=["GET"])
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

    if app.config["RESULT_DOWNLOAD_MODE"] == "nginx":
        archive_name = os.path.basename(zip_filename)
        response = Response(status=200, mimetype="application/zip")
        response.headers["X-Accel-Redirect"] = f"/_protected_results/{archive_name}"
        response.headers.set("Content-Disposition", "attachment", filename=_task_zip_download_name(task))
        response.headers["Cache-Control"] = "private, no-store"
        return response

    return send_from_directory(
        app.config["RESULTS_FOLDER"],
        os.path.basename(zip_filename),
        as_attachment=True,
        download_name=_task_zip_download_name(task),
    )


@app.route("/compute/api/cancel/<md5sum>", methods=["POST"])
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


def _dashboard_task_status(task: dict[str, Any], index: int, current_user: str, is_admin: bool) -> dict[str, Any]:
    submitted_time = task.get("uploaded_at")
    finished_time = task.get("finished_at")
    if task.get("is_binary"):
        fasta_seq = "Binary file rejected"
    else:
        try:
            with open(task["file_path"]) as handle:
                fasta_seq = handle.read().strip()
        except (OSError, UnicodeDecodeError) as exc:
            reason = "file not found" if isinstance(exc, FileNotFoundError) else "file unavailable"
            fasta_seq = (
                f"Unable to read sequence: {reason} at "
                f"{_virtual_upload_path(task.get('filename', 'unknown.fasta'))}"
            )

    return {
        "id": index,
        "md5": task["md5sum"],
        "status": task["status"],
        "fasta_fn": task["filename"],
        "submitted_time": format_times(submitted_time),
        "finished_time": format_times(finished_time) if finished_time else "-",
        "walltime": format_walltime(task.get("walltime")),
        "submitted_timestamp": submitted_time or 0,
        "sequence": fasta_seq,
        "owner": task.get("username") or "-",
        "can_delete": (is_admin or task.get("username") == current_user)
        and task["status"] not in task_store.CLEANUP_CLAIM_STATUSES,
        "task_type": task.get("task_type", "gremlin"),
        "running_trace": _build_running_trace(task),
        "error": _sanitize_task_error(task, task.get("error")),
    }


@app.route("/compute/dashboard", methods=["GET"])
@login_required
def task_dashboard():  # skipcq: PY-R1000 -- dashboard filtering and response assembly share request state.
    current_user = _current_username() or ""
    is_admin = _is_admin_user()
    all_tasks = task_store.list_tasks()
    scoped_tasks = all_tasks if is_admin else [task for task in all_tasks if task.get("username") == current_user]
    visible_tasks = [task for task in scoped_tasks if not _is_deleted_status(task.get("status"))]
    task_statuses = [
        _dashboard_task_status(task, index, current_user, is_admin) for index, task in enumerate(visible_tasks)
    ]
    sorted_task_statuses = sorted(task_statuses, key=lambda x: x["submitted_timestamp"], reverse=True)

    return render_template(
        "dashboard.html",
        sorted_task_statuses=sorted_task_statuses,
        current_username=current_user,
        is_admin_user=is_admin,
    )


def _soft_delete_task(md5sum: str, task: dict[str, Any]) -> None:
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


@app.route("/compute/api/delete/<md5sum>", methods=["DELETE"])
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
    if task["status"] in task_store.CLEANUP_CLAIM_STATUSES:
        return jsonify({"error": "Task cleanup is already in progress", "md5sum": md5sum}), 409

    _soft_delete_task(md5sum, task)
    return jsonify({"status": "deleted", "md5sum": md5sum}), 200


@app.route("/compute/api/delete", methods=["POST"])
@login_required
def delete_tasks_batch():  # skipcq: PY-R1000 -- per-task authorization and outcome accounting are intentionally atomic.
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
        if task["status"] in task_store.CLEANUP_CLAIM_STATUSES:
            ignored.append(md5sum)
            continue

        _soft_delete_task(md5sum, task)
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
    """Return 403 unless the current user has the canonical admin role."""
    if _blocked := require_web_login():
        return _blocked
    if g.current_user.get("role") != "admin":
        return jsonify({"error": "Admin access required"}), 403
    return None


_ADMIN_LOG_FILES = {
    "gunicorn-access": "gunicorn-access.log",
    "gunicorn-error": "gunicorn-error.log",
    "celery-worker": "celery-worker.log",
    "maintenance": "maintenance.log",
}
_ADMIN_LOG_ARCHIVE_PATTERN = re.compile(
    rf"(?:{'|'.join(re.escape(name) for name in _ADMIN_LOG_FILES.values())})" r"\.\d{8}T\d{12}Z\.zip"
)


def _admin_log_archive_path(archive_name: str) -> Path | None:
    """Resolve one managed rotated-log ZIP without allowing arbitrary paths."""
    if _ADMIN_LOG_ARCHIVE_PATTERN.fullmatch(archive_name) is None:
        return None
    log_dir = os.environ.get("LOG_DIR", "").strip()
    if not log_dir:
        return None
    archive_path = Path(log_dir).resolve() / archive_name
    if archive_path.is_symlink() or not archive_path.is_file():
        return None
    return archive_path


@app.route("/compute/api/auth/admin/logs/archives", methods=["GET"])
@login_required
def admin_log_archives():
    """List managed rotated-log ZIPs grouped by active log."""
    if _blocked := require_admin():
        return _blocked
    log_dir = os.environ.get("LOG_DIR", "").strip()
    if not log_dir:
        return jsonify({"error": "LOG_DIR is not configured"}), 503

    directory = Path(log_dir).resolve()
    groups = []
    for log_name, filename in _ADMIN_LOG_FILES.items():
        archives = []
        for archive in directory.glob(f"{filename}.*.zip"):
            if (
                _ADMIN_LOG_ARCHIVE_PATTERN.fullmatch(archive.name) is None
                or archive.is_symlink()
                or not archive.is_file()
            ):
                continue
            try:
                stat = archive.stat()
            except OSError:
                continue
            archives.append(
                {
                    "filename": archive.name,
                    "size": stat.st_size,
                    "modified_at": stat.st_mtime,
                }
            )
        archives.sort(key=lambda item: (item["modified_at"], item["filename"]), reverse=True)
        groups.append(
            {
                "id": log_name,
                "filename": filename,
                "archives": archives,
            }
        )
    return jsonify({"logs": groups})


@app.route(
    "/compute/api/auth/admin/logs/archives/<archive_name>",
    methods=["GET"],
)
@login_required
def admin_download_log_archive(archive_name: str):
    """Download one managed rotated-log ZIP."""
    if _blocked := require_admin():
        return _blocked
    archive_path = _admin_log_archive_path(archive_name)
    if archive_path is None:
        return jsonify({"error": "Log archive is not available"}), 404
    response = send_from_directory(
        archive_path.parent,
        archive_path.name,
        as_attachment=True,
        download_name=archive_path.name,
        mimetype="application/zip",
    )
    response.headers["Cache-Control"] = "no-store"
    return response


@app.route("/compute/api/auth/admin/logs/<log_name>", methods=["GET"])
@login_required
def admin_stream_log(log_name: str):
    """Stream one fixed, unrotated server log to an administrator."""
    if _blocked := require_admin():
        return _blocked
    filename = _ADMIN_LOG_FILES.get(log_name)
    if filename is None:
        return jsonify({"error": "Unknown log"}), 404

    log_dir = os.environ.get("LOG_DIR", "").strip()
    if not log_dir:
        return jsonify({"error": "LOG_DIR is not configured"}), 503
    log_path = Path(log_dir).resolve() / filename
    if log_path.is_symlink() or not log_path.is_file():
        return jsonify({"error": "Log is not available"}), 404
    try:
        handle = log_path.open("rb")
    except OSError:
        return jsonify({"error": "Log is not available"}), 404

    def stream():
        with handle:
            while chunk := handle.read(64 * 1024):
                yield chunk

    return Response(
        stream(),
        mimetype="text/plain",
        headers={
            "Cache-Control": "no-store",
            "Content-Disposition": f'inline; filename="{filename}"',
            "X-Accel-Buffering": "no",
        },
    )


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


@app.route("/compute/api/auth/login", methods=["POST"])
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
    # Constant-time: always run check_password_hash so response latency does
    # not reveal whether the username exists (timing side-channel defence).
    pwd_ok = check_password_hash(
        user["password_hash"] if user is not None else _DUMMY_PASSWORD_HASH,
        req.password,
    )
    if user is None or not pwd_ok:
        return jsonify({"error": "Invalid username or password"}), 401

    if blocked := _is_account_blocked(user):
        return jsonify({"error": blocked}), 403

    token = generate_token(user["id"], user.get("token_version", 0))
    response = jsonify({"token": token, "username": user["username"]})
    # ponytail: set cookie so browser page navigations (not just fetch())
    # carry the auth token.  HttpOnly; SameSite=Lax prevents CSRF.
    # secure=True only when SERVER_BASE_URL uses https — plain-http dev
    # environments would silently drop Secure cookies.
    _cookie_secure = _env_str("SERVER_BASE_URL", "http://localhost:8080").startswith("https://")
    response.set_cookie("auth_token", token, httponly=True, samesite="Lax", secure=_cookie_secure)
    return response


@app.route("/compute/api/auth/forgot-password", methods=["POST"])
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


@app.route("/compute/reset_password", methods=["GET"])
def auth_reset_password_page():
    """Render the password-reset page for a valid reset token."""
    token = request.args.get("c", "").strip()
    if not token:
        return render_template("error.html", code=400, message="Missing reset token."), 400
    user_id = validate_reset_token(token)
    if user_id is None:
        return render_template("error.html", code=400, message="Invalid or expired reset token."), 400
    return render_template("reset-password.html", token=token), 200


@app.route("/compute/reset_password", methods=["POST"])
def auth_reset_password():
    """Set a new password using a password-reset token."""
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


@app.route("/compute/api/auth/logout", methods=["POST"])
@optional_user
def auth_logout():
    """Clear the auth cookie and invalidate all tokens for the current user.

    No auth required — idempotent.  If the user is authenticated (cookie or
    Bearer token), their ``token_version`` is incremented so all previously
    issued tokens become invalid.
    """
    user = g.get("current_user")
    if user is not None:
        db = _get_user_db()
        db.increment_token_version(user["id"])
    response = jsonify({"status": "logged_out"})
    secure = _env_str("SERVER_BASE_URL", "http://localhost:8080").startswith("https://")
    response.set_cookie("auth_token", "", max_age=0, path="/", httponly=True, samesite="Lax", secure=secure)
    return response


@app.route("/compute/api/auth/captcha", methods=["GET"])
def auth_captcha():
    """Return a math CAPTCHA challenge with a signed token (5-min expiry)."""
    question, token = generate_captcha()
    return jsonify({"question": question, "token": token}), 200


@app.route("/compute/api/auth/register", methods=["POST"])
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
        full_name=req.full_name,
        affiliation=req.affiliation,
        position=req.position,
        pi_name=req.pi_name,
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


@app.route("/compute/api/auth/resend-verification", methods=["POST"])
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

    # Return a generic response for all non-actionable cases to prevent
    # account enumeration (unknown, deleted, banned, already verified).
    _generic = (
        jsonify({"message": "If that email is registered and unverified, a new verification email has been sent."}),
        200,
    )
    if user is None:
        return _generic
    if user.get("deleted") or user.get("user_status") == "banned":
        return _generic
    if user.get("email_verified"):
        return _generic

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


@app.route("/compute/api/auth/verify-email", methods=["GET"])
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


@app.route("/compute/user_verify", methods=["GET"])
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


@app.route("/compute/api/auth/me", methods=["GET"])
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
                "role": user.get("role", "user"),
                "full_name": user.get("full_name"),
                "affiliation": user.get("affiliation"),
                "position": user.get("position"),
                "pi_name": user.get("pi_name"),
            }
        ),
        200,
    )


@app.route("/compute/api/auth/me", methods=["PUT"])
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
    db.increment_token_version(user["id"])
    return jsonify({"message": "Password updated"}), 200


# ---------------------------------------------------------------------------
# Token refresh — cookie-authenticated endpoint that returns a fresh Bearer
# token so pages loaded via cookie navigation can perform state-changing
# operations that require Bearer auth (CSRF protection).
# ---------------------------------------------------------------------------


@app.route("/compute/api/auth/token", methods=["GET"])
@login_required
def auth_get_token():
    """Return a fresh Bearer token (cookie or Bearer auth accepted)."""
    user = g.current_user
    token = generate_token(user["id"], user.get("token_version", 0))
    return jsonify({"token": token}), 200


# ---------------------------------------------------------------------------
# API key management (long-lived, user-revokable)
# ---------------------------------------------------------------------------


@app.route("/compute/api/auth/me/api-key", methods=["GET"])
@login_required
def auth_api_key_status():
    """Return whether the current user has an active API key."""
    if _blocked := require_web_login():
        return _blocked
    db = _get_user_db()
    user = db.get_user(g.current_user["id"])
    has_key = bool(user and user.get("api_key_hash"))
    return jsonify({"has_api_key": has_key}), 200


@app.route("/compute/api/auth/me/api-key", methods=["POST"])
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


@app.route("/compute/api/auth/me/api-key", methods=["DELETE"])
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


@app.route("/compute/api/auth/admin/users", methods=["GET"])
@login_required
def admin_users():
    """Admin-only user listing with safe fields only."""
    if _blocked := require_admin():
        return _blocked

    db = _get_user_db()
    users = db.list_users()
    safe = [UserResponse.model_validate(u).model_dump() for u in users]
    return jsonify({"users": safe}), 200


@app.route("/compute/api/auth/admin/users", methods=["POST"])
@login_required
def admin_create_user():
    """Admin-only user creation for pre-approved accounts."""
    if _blocked := require_admin():
        return _blocked
    if _blocked := require_bearer_auth():
        return _blocked

    db = _get_user_db()
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
        role=req.role,
        full_name=req.full_name,
        affiliation=req.affiliation,
        position=req.position,
        pi_name=req.pi_name,
        registration_status="approved",
        user_status="active",
    )
    db.verify_email(new_user["id"])  # admin-created accounts are pre-verified

    logging.info("Admin %r created user %r", g.current_user["username"], req.username)
    return jsonify({"message": "User created", "username": req.username}), 201


def _admin_email_update(db: UserDatabase, user_id: int, email: str | None):
    if email is None:
        return {}, None
    existing = db.get_user_by_email(email)
    if existing and existing["id"] != user_id:
        return None, (jsonify({"error": "Email address already in use"}), 409)
    return {"email": email}, None


def _admin_profile_update_fields(req: AdminUpdateUserRequest) -> dict[str, Any]:
    update_fields = {
        field: value
        for field in ("affiliation", "full_name", "pi_name", "user_status")
        if (value := getattr(req, field)) is not None
    }
    if "position" in req.model_fields_set:
        update_fields["position"] = req.position
    if req.password is not None:
        update_fields["password_hash"] = generate_password_hash(req.password)
    return update_fields


def _admin_registration_update_fields(
    db: UserDatabase,
    user_id: int,
    user: dict[str, Any],
    registration_status: str | None,
) -> dict[str, Any]:
    update_fields: dict[str, Any] = {}
    if registration_status is None:
        return update_fields
    update_fields["registration_status"] = registration_status
    # Admin approval implies email verification — avoid the gap where
    # an unverified self-registered account becomes active without
    # proving email ownership.
    if registration_status == "approved":
        if not user.get("email_verified"):
            db.verify_email(user_id)
        update_fields["approved_by"] = g.current_user["id"]
        update_fields["approved_at"] = time.time()
    return update_fields


def _admin_user_update_fields(
    db: UserDatabase,
    user_id: int,
    user: dict[str, Any],
    is_self: bool,
    req: AdminUpdateUserRequest,
):
    """Build validated fields for an admin user update."""
    update_fields, update_error = _admin_email_update(db, user_id, req.email)
    if update_error is not None:
        return None, update_error
    if is_self and req.user_status == "banned":
        return None, (jsonify({"error": "Administrators cannot ban their own account"}), 400)
    update_fields.update(_admin_profile_update_fields(req))
    update_fields.update(_admin_registration_update_fields(db, user_id, user, req.registration_status))
    if req.role is not None:
        if is_self:
            return None, (jsonify({"error": "Administrators cannot change their own role"}), 400)
        update_fields["role"] = req.role
    return update_fields, None


def _notify_admin_user_update(
    db: UserDatabase,
    user_id: int,
    user: dict[str, Any],
    registration_status: str | None,
) -> None:
    if registration_status == "approved":
        approved_user = db.get_user(user_id) or user
        if not send_approval_email(approved_user):
            logging.warning("Approval email failed for %r", user_id)
    elif registration_status == "rejected" and not send_rejection_email(user):
        logging.warning("Rejection email failed for %r", user_id)


@app.route("/compute/api/auth/admin/users/<int:user_id>", methods=["PUT", "DELETE"])
@login_required
def admin_manage_user(user_id):  # skipcq: PY-R1000 -- admin state transitions are kept in one audited transaction.
    """Admin-only: update or soft-delete a user."""
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

    req = _parse_body(AdminUpdateUserRequest)
    if isinstance(req, tuple):
        return req
    update_fields, update_error = _admin_user_update_fields(db, user_id, user, is_self, req)
    if update_error is not None:
        return update_error

    if update_fields:
        db.update_user(user_id, **update_fields)
        _notify_admin_user_update(db, user_id, user, update_fields.get("registration_status"))

    return jsonify({"message": "User updated"}), 200


@app.route("/compute/api/auth/admin/users/batch", methods=["POST"])
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
            "email_verified": True,
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
        if user.get("role") == "admin" and req.action == "disable":
            continue  # don't disable other admins
        db.update_user(uid, **updates)
        count += 1

    return jsonify({"message": f"{req.action} action applied to {count} user(s)", "count": count}), 200
