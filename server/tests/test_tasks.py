# Copyright (c) 2026 The REvoDesign Developers.
# Distributed under the terms of the GNU General Public License v3.0.
# SPDX-License-Identifier: GPL-3.0-only

from __future__ import annotations

import hashlib
import io
import json
import os
import time
import uuid
import zipfile
from dataclasses import replace
from pathlib import Path

import requests
from conftest import _extract_md5, _load_pssm_module
from werkzeug.utils import secure_filename

import docker

SERVER_PACKAGE = Path(__file__).resolve().parents[1] / "revocompute"

# Flask test-client tests
# ==================================================================


def test_server_exposes_local_favicon_assets(monkeypatch, tmp_path):
    module = _load_pssm_module(
        monkeypatch,
        tmp_path,
        extra_env={
            "RUNNER_UID": "1234",
            "RUNNER_GID": "5678",
        },
    )
    client = module.app.test_client()
    auth_header = _test_client_auth(module)

    favicon = client.get("/favicon.ico")
    assert favicon.status_code == 200
    assert "image" in (favicon.content_type or "")

    logo_svg = client.get("/compute/logo.svg")
    assert logo_svg.status_code == 200
    assert "svg" in (logo_svg.content_type or "")

    page = client.get("/compute/create_task", headers=auth_header)
    assert page.status_code == 200
    html = page.get_data(as_text=True)
    assert 'href="/favicon.ico"' in html
    assert 'href="/compute/logo.svg"' in html
    assert 'class="btn btn-soft theme-toggle mode-auto"' in html
    assert 'class="theme-icon" aria-hidden="true">◐</span>' in html
    assert 'src="/static/js/theme.js"' in html
    assert 'type="file" name="file" id="fileInput" class="sr-only"' in html
    assert 'id="fileButton"' in html
    assert "file-input-offscreen" not in html


def test_task_type_api_exposes_runtime_family_and_gpu_contract(monkeypatch, tmp_path):
    module = _load_pssm_module(
        monkeypatch,
        tmp_path,
        extra_env={
            "RUNNER_UID": "1234",
            "RUNNER_GID": "5678",
            "ENABLED_TASKRUNNERS": "lasermpnn",
        },
    )
    client = module.app.test_client()

    response = client.get("/compute/api/types")
    assert response.status_code == 200
    laser = next(item for item in response.get_json() if item["name"] == "lasermpnn")
    assert laser["runtime_family"] == "mpnn"
    assert laser["gpus"] is False

    form_response = client.get("/compute/api/types/lasermpnn")
    assert form_response.status_code == 200
    form = form_response.get_json()
    assert form["runtime_family"] == "mpnn"
    assert form["gpus"] is False


def test_dashboard_links_to_dedicated_manifest_first_result_workspace():
    dashboard_script = (SERVER_PACKAGE / "static" / "js" / "dashboard.js").read_text(encoding="utf-8")
    script = (SERVER_PACKAGE / "static" / "js" / "task-results.js").read_text(encoding="utf-8")
    styles = (SERVER_PACKAGE / "static" / "css" / "task-results.css").read_text(encoding="utf-8")
    template = (SERVER_PACKAGE / "templates" / "task_results.html").read_text(encoding="utf-8")

    assert 'window.location.assign("/compute/results/"' in dashboard_script
    assert 'A.authFetch("/compute/api/results/"' in script
    assert "Main Results" in template
    assert "Scientific previews" not in template
    assert 'MOLSTAR_VERSION = "5.10.0"' in script
    assert "MOLSTAR_SCRIPT_INTEGRITY" in script
    assert "RIontCdJN53gEl2f" in script
    assert "A.authFetch(artifact.url)" in script
    assert "loadStructureFromData" in script
    assert "loadStructureFromUrl" not in script
    assert 'PY2DMOL_COMMIT = "8c95fd9efae6007e124e143cd276244d89228c66"' in script
    assert "PY2DMOL_SCRIPT_INTEGRITY" in script
    assert "renderPy2DmolFallback" in script
    assert "parseCifAlphaCarbons" in script
    assert "var previewPlugins = Object.freeze" in script
    assert "await plugin.render(artifact, stage)" in script
    assert ".artifact-table-preview" in styles
    assert ".artifact-molstar-preview" in styles


def test_execution_logs_are_diagnostic_text_artifacts_not_main_results():
    runtime = (SERVER_PACKAGE / "task_runtime.py").read_text(encoding="utf-8")
    results = (SERVER_PACKAGE / "static" / "js" / "task-results.js").read_text(encoding="utf-8")
    assert 'artifact["role"] = "diagnostic"' in runtime
    assert 'artifact.role !== "diagnostic"' in results
    assert 'Execution log · ' in results


def test_full_stack_smoke_uses_manifest_first_result_contract():
    script = (Path(__file__).parent / "full_stack_smoke.py").read_text(encoding="utf-8")
    assert 'manifest = results.json()' in script
    assert 'artifact["url"]' in script
    assert 'f"{base_url}/compute/api/results/{task_id}/archive"' in script
    assert "artifact_prefix = fasta_path.stem" in script
    assert "2KL8_ascii_mtx_file" not in script
    assert 'os.environ.get("FULL_STACK_ADMIN_USERNAME", "admin")' in script
    assert '"REvoCompute Task Dashboard"' in script
    assert '"Create Compute Task"' in script
    assert '"PSSM GREMLIN Task Dashboard"' not in script
    assert '"Create PSSM GREMLIN Task"' not in script
    assert "results.status_code == 302" not in script


def _insert_pending_task(
    module, result_dir: Path, filename: str = "input.fasta", entities: list[dict] | None = None
) -> str:
    result_dir.mkdir(parents=True, exist_ok=True)
    fasta_path = result_dir / filename
    content = b">test\nACDE\n"
    fasta_path.write_bytes(content)
    md5sum = uuid.uuid4().hex
    blob_hash = hashlib.sha256(content).hexdigest()
    snapshot_root = Path(module.task_runtime.CONFIG.workspace_folder) / "tester" / md5sum / "inputs"
    snapshot_path = snapshot_root / filename
    snapshot_path.parent.mkdir(parents=True, exist_ok=True)
    snapshot_path.write_bytes(content)
    if entities is None:
        entities = [
            {
                "name": "file",
                "type": "file",
                "value": filename,
                "verified_value": filename,
                "relative_path": filename,
                "mounted": f"/mnt/revocompute/tester/inputs/{filename}",
                "hash": blob_hash,
                "snapshot_path": str(snapshot_path),
                "snapshot_root": str(snapshot_root),
                "workspace_key": "tester",
            }
        ]
    # _execute_compute_task verifies the upload file exists at
    # CONFIG.upload_folder/<hash>.upload before launching Docker.
    upload_file = Path(module.task_runtime.CONFIG.upload_folder) / f"{blob_hash}.upload"
    upload_file.parent.mkdir(parents=True, exist_ok=True)
    upload_file.write_bytes(content)
    module.task_store.upsert_task(
        md5sum,
        filename=filename,
        file_path=str(fasta_path),
        result_dir=str(result_dir),
        uploaded_at=time.time(),
        status="pending",
        is_binary=0,
        source_ip="127.0.0.1",
        user_agent="pytest",
        username="tester",
        input_form=json.dumps({"user": "tester", "submitted_at": "2026-01-01T00:00:00Z", "entities": entities}),
    )
    return md5sum


def test_run_compute_task_handles_docker_daemon_error(monkeypatch, tmp_path):
    module = _load_pssm_module(
        monkeypatch,
        tmp_path,
        extra_env={
            "RUNNER_UID": "1234",
            "RUNNER_GID": "5678",
        },
    )
    md5sum = _insert_pending_task(module, tmp_path / "result")

    def _raise_docker_error(task_id, tt, runner, entities, output_dir, stage_callback=None, username=""):
        del task_id, tt, runner, entities, output_dir, stage_callback, username
        raise docker.errors.DockerException(
            "Error while fetching server API version: ('Connection aborted.', PermissionError(13, 'Permission denied'))"
        )

    monkeypatch.setattr(module.task_runtime, "_run_compute_job", _raise_docker_error)

    module.run_compute_task(md5sum)
    task = module.task_store.get_task(md5sum)

    assert task is not None
    assert task["status"] == "failed"
    assert task["error"].startswith("docker:")
    assert "Permission denied" in task["error"]

    result_dir = Path(task["result_dir"])
    assert result_dir.is_dir()
    manifest = json.loads((result_dir / "manifest.json").read_text(encoding="utf-8"))
    assert {item["path"] for item in manifest["artifacts"]} >= {"input.fasta", "task_failed.txt"}
    assert "Permission denied" in (result_dir / "task_failed.txt").read_text(encoding="utf-8")
    assert not (Path(module.app.config["RESULTS_FOLDER"]) / f"{md5sum}_results.zip").exists()


def test_run_compute_task_finalizes_uncompressed_result_manifest(monkeypatch, tmp_path):
    module = _load_pssm_module(
        monkeypatch,
        tmp_path,
        extra_env={
            "RUNNER_UID": "1234",
            "RUNNER_GID": "5678",
        },
    )
    md5sum = _insert_pending_task(module, tmp_path / "result")
    observed_statuses: list[str] = []
    original_update_task = module.task_store.update_task

    def _track_update(md5_value: str, **fields):
        if "status" in fields:
            observed_statuses.append(fields["status"])
        return original_update_task(md5_value, **fields)

    def _fake_runner(task_id, tt, runner, entities, output_dir, stage_callback=None, username=""):
        del task_id, tt, runner, entities, username
        if stage_callback:
            stage_callback("hhblits")
            stage_callback("hhfilter")
            stage_callback("gremlin")
            stage_callback("blast")
        output_path = Path(output_dir)
        (output_path / "log").mkdir(parents=True, exist_ok=True)
        (output_path / "log" / "task_finished").write_text("done\n", encoding="utf-8")
        (output_path / "pssm_msa").mkdir(parents=True, exist_ok=True)
        (output_path / "pssm_msa" / "input_ascii_mtx_file").write_text("pssm\n", encoding="utf-8")

    monkeypatch.setattr(module.task_store, "update_task", _track_update)
    monkeypatch.setattr(module.task_runtime, "_run_compute_job", _fake_runner)
    monkeypatch.setattr(module.task_runtime, "_local_user_identity", lambda: "pytest:staff-1000:20")

    module.run_compute_task(md5sum)

    task = module.task_store.get_task(md5sum)
    assert task is not None
    assert task["status"] == "finished"
    assert task["local_user"] == "pytest:staff-1000:20"
    assert task["run_stage"] == "blast"
    result_dir = Path(task["result_dir"])
    assert result_dir.is_dir()
    manifest = json.loads((result_dir / "manifest.json").read_text(encoding="utf-8"))
    names = {item["path"] for item in manifest["artifacts"]}
    assert "log/task_finished" in names
    assert "pssm_msa/input_ascii_mtx_file" in names
    assert all(len(item["sha256"]) == 64 for item in manifest["artifacts"])
    assert not (Path(module.app.config["RESULTS_FOLDER"]) / f"{md5sum}_results.zip").exists()

    assert "running" in observed_statuses
    assert "finished" in observed_statuses
    assert observed_statuses.index("running") < observed_statuses.index("finished")


def test_single_stage_slurm_task_transitions_from_queued_to_running(monkeypatch, tmp_path):
    module = _load_pssm_module(
        monkeypatch,
        tmp_path,
        extra_env={
            "RUNNER_UID": "1234",
            "RUNNER_GID": "5678",
            "ENABLED_TASKRUNNERS": "opendde",
        },
    )
    result_dir = tmp_path / "result"
    md5sum = _insert_pending_task(module, result_dir)
    module.task_store.update_task(md5sum, task_type="opendde")
    observed_statuses: list[str] = []
    original_update_task = module.task_store.update_task

    def _track_update(md5_value: str, **fields):
        if "status" in fields:
            observed_statuses.append(fields["status"])
        return original_update_task(md5_value, **fields)

    def _fake_runner(task_id, tt, runner, entities, output_dir, stage_callback=None, username=""):
        del task_id, tt, runner, entities, username
        if stage_callback:
            stage_callback("opendde")
        output_path = Path(output_dir)
        output_path.mkdir(parents=True, exist_ok=True)
        (output_path / "model.cif").write_text("data_model\n", encoding="utf-8")

    monkeypatch.setattr(module.task_runtime, "_get_job_executor", lambda: "slurm")
    monkeypatch.setattr(module.task_store, "update_task", _track_update)
    monkeypatch.setattr(module.task_runtime, "_run_compute_job", _fake_runner)

    module.run_compute_task(md5sum, "opendde", {})

    assert observed_statuses == ["queued", "running", "finished"]


def test_multi_file_submission_creates_isolated_workspace_snapshot(monkeypatch, tmp_path):
    module = _load_pssm_module(
        monkeypatch,
        tmp_path,
        extra_env={"RUNNER_UID": "1234", "RUNNER_GID": "5678"},
    )
    base_type, runner = module.task_runtime._get_task_type("gremlin")
    module.task_runtime._register_tt(
        replace(
            base_type,
            name="multi_structure",
            display_name="Multi Structure",
                input_extension=".pdb",
                input_extensions=(".pdb", ".json"),
                primary_input_extensions=(".pdb",),
            input_label="Structure bundle",
            allow_multiple_inputs=True,
            max_input_files=4,
            params=(),
        ),
        runner,
    )
    class _Queued:
        id = "queued-multi"

    monkeypatch.setattr(module.run_compute_task, "apply_async", lambda *args, **kwargs: _Queued())
    client = module.app.test_client()
    auth_header = _test_client_auth(module)

    response = client.post(
        "/compute/api/post",
        data={
            "task_type": "multi_structure",
            "files": [
                (io.BytesIO(b"ATOM      1  CA  ALA A   1\n"), "model.pdb"),
                (io.BytesIO(b'{"contigs": ["A1-10"]}\n'), "settings.json"),
            ],
            "input_paths": ["structures/model.pdb", "config/settings.json"],
        },
        headers=auth_header,
    )

    assert response.status_code == 302, response.get_json()
    md5sum = response.headers["Location"].rsplit("/", 1)[-1]
    task = module.task_store.get_task(md5sum)
    form = json.loads(task["input_form"])
    files = [entity for entity in form["entities"] if entity["type"] == "file"]
    assert [entity["relative_path"] for entity in files] == ["structures/model.pdb", "config/settings.json"]
    assert files[0]["mounted"] == "/mnt/revocompute/tester/inputs/structures/model.pdb"
    assert form["virtual_root"] == "/mnt/revocompute/tester"
    for entity in files:
        snapshot = Path(entity["snapshot_path"])
        assert snapshot.is_file()
        assert snapshot.resolve().is_relative_to(Path(module.app.config["WORKSPACE_FOLDER"]).resolve())
    assert not any(Path(task["result_dir"]).iterdir())


def test_optional_archive_keeps_result_tree(monkeypatch, tmp_path):
    module = _load_pssm_module(
        monkeypatch,
        tmp_path,
        extra_env={"RUNNER_UID": "1234", "RUNNER_GID": "5678"},
    )
    md5sum = uuid.uuid4().hex
    result_dir = tmp_path / "optional_archive"
    result_dir.mkdir()
    (result_dir / "result.csv").write_text("score\n1.0\n", encoding="utf-8")
    _upsert_task_for_user(
        module,
        md5sum,
        filename="input.pdb",
        file_path=result_dir / "input.pdb",
        result_dir=result_dir,
        username="tester",
        status="finished",
    )
    task = module.task_store.get_task(md5sum)
    module.task_runtime._finalize_results_manifest(task)
    (result_dir / "late-unpublished.txt").write_text("not in manifest\n", encoding="utf-8")

    archive_path = Path(module.task_runtime._build_results_archive(task))

    assert archive_path.is_file()
    assert (result_dir / "result.csv").is_file()
    assert (result_dir / "manifest.json").is_file()
    with zipfile.ZipFile(archive_path) as archive:
        assert {"result.csv", "manifest.json"} <= set(archive.namelist())
        assert "late-unpublished.txt" not in archive.namelist()


def test_result_manifest_allows_only_published_artifacts(monkeypatch, tmp_path):
    module = _load_pssm_module(
        monkeypatch,
        tmp_path,
        extra_env={"RUNNER_UID": "1234", "RUNNER_GID": "5678"},
    )
    client = module.app.test_client()
    auth_header = _test_client_auth(module)
    md5sum = uuid.uuid4().hex
    result_dir = tmp_path / "manifest_artifacts"
    (result_dir / "scores").mkdir(parents=True)
    (result_dir / "scores" / "result.csv").write_text("score\n1.0\n", encoding="utf-8")
    _upsert_task_for_user(
        module,
        md5sum,
        filename="input.pdb",
        file_path=result_dir / "input.pdb",
        result_dir=result_dir,
        username="tester",
        status="finished",
    )
    module.task_runtime._finalize_results_manifest(module.task_store.get_task(md5sum))
    (result_dir / "not-published.txt").write_text("late mutation", encoding="utf-8")

    manifest_response = client.get(f"/compute/api/results/{md5sum}", headers=auth_header)
    result_page = client.get(f"/compute/results/{md5sum}", headers=auth_header)
    artifact = manifest_response.json["artifacts"][0]
    inline = client.get(artifact["url"], headers=auth_header)
    download = client.get(f"{artifact['url']}?download=1", headers=auth_header)
    unpublished = client.get(
        f"/compute/api/results/{md5sum}/artifacts/not-published.txt",
        headers=auth_header,
    )

    assert manifest_response.status_code == 200
    assert result_page.status_code == 200
    assert "Main Results" in result_page.get_data(as_text=True)
    assert md5sum in result_page.get_data(as_text=True)
    assert artifact["path"] == "scores/result.csv"
    assert artifact["preview"] == "table"
    assert inline.status_code == 200
    assert inline.get_data(as_text=True) == "score\n1.0\n"
    assert download.headers["Content-Disposition"].startswith("attachment;")
    assert unpublished.status_code == 404


def test_archive_endpoint_queues_only_on_explicit_request(monkeypatch, tmp_path):
    module = _load_pssm_module(
        monkeypatch,
        tmp_path,
        extra_env={"RUNNER_UID": "1234", "RUNNER_GID": "5678"},
    )
    client = module.app.test_client()
    auth_header = _test_client_auth(module)
    md5sum = uuid.uuid4().hex
    result_dir = tmp_path / "archive_request"
    result_dir.mkdir()
    (result_dir / "result.txt").write_text("done\n", encoding="utf-8")
    _upsert_task_for_user(
        module,
        md5sum,
        filename="input.fasta",
        file_path=result_dir / "input.fasta",
        result_dir=result_dir,
        username="tester",
        status="finished",
    )
    module.task_runtime._finalize_results_manifest(module.task_store.get_task(md5sum))

    queued: list[list[str]] = []

    class _Queued:
        id = "archive-job"

    monkeypatch.setattr(
        module.task_runtime.build_results_archive,
        "apply_async",
        lambda args: queued.append(args) or _Queued(),
    )

    status = client.get(f"/compute/api/results/{md5sum}", headers=auth_header)
    request_archive = client.post(f"/compute/api/results/{md5sum}/archive", headers=auth_header)

    assert status.status_code == 200
    assert status.json["archive"]["ready"] is False
    assert queued == [[md5sum]]
    assert request_archive.status_code == 202
    assert request_archive.json["status"] == "building"


def test_task_store_update_ignores_late_non_deleted_updates(monkeypatch, tmp_path):
    module = _load_pssm_module(
        monkeypatch,
        tmp_path,
        extra_env={
            "RUNNER_UID": "1234",
            "RUNNER_GID": "5678",
        },
    )
    md5sum = _insert_pending_task(module, tmp_path / "result")
    deleted_at = time.time()
    module.task_store.update_task(
        md5sum,
        status="deleted:cancel",
        finished_at=deleted_at,
        error="Task deleted by user",
    )

    # Simulate stale worker writes arriving after a delete request.
    module.task_store.update_task(md5sum, status="running", run_stage="blast")
    module.task_store.update_task(md5sum, status="finished", walltime=12.3, error=None)
    module.task_store.update_task(md5sum, run_stage="hhblits")

    task = module.task_store.get_task(md5sum)
    assert task is not None
    assert task["status"] == "deleted:cancel"
    assert task["error"] == "Task deleted by user"
    assert task["finished_at"] == deleted_at


def test_run_compute_task_does_not_resurrect_deleted_task(monkeypatch, tmp_path):
    module = _load_pssm_module(
        monkeypatch,
        tmp_path,
        extra_env={
            "RUNNER_UID": "1234",
            "RUNNER_GID": "5678",
        },
    )
    md5sum = _insert_pending_task(module, tmp_path / "result")
    observed_statuses: list[str] = []
    original_update_task = module.task_store.update_task

    def _track_update(md5_value: str, **fields):
        if "status" in fields:
            observed_statuses.append(fields["status"])
        return original_update_task(md5_value, **fields)

    def _fake_runner(task_id, tt, runner, entities, output_dir, stage_callback=None, username=""):
        del task_id, tt, runner, entities, username
        if stage_callback:
            stage_callback("blast")
        output_path = Path(output_dir)
        (output_path / "log").mkdir(parents=True, exist_ok=True)
        (output_path / "log" / "task_finished").write_text("done\n", encoding="utf-8")
        original_update_task(
            md5sum,
            status="deleted:cancel",
            finished_at=time.time(),
            walltime=0.1,
            error="Task deleted by user",
            celery_task_id=None,
        )
        task = module.task_store.get_task(md5sum)
        assert task is not None
        module._delete_task_artifacts(task)

    monkeypatch.setattr(module.task_store, "update_task", _track_update)
    monkeypatch.setattr(module.task_runtime, "_run_compute_job", _fake_runner)
    monkeypatch.setattr(module.task_runtime, "_local_user_identity", lambda: "pytest:staff-1000:20")

    module.run_compute_task(md5sum)

    task = module.task_store.get_task(md5sum)
    assert task is not None
    assert task["status"] == "deleted:cancel"
    assert "packing results" not in observed_statuses
    assert "finished" not in observed_statuses
    zip_path = Path(module.app.config["RESULTS_FOLDER"]) / f"{md5sum}_results.zip"
    assert not zip_path.exists()


def test_delete_task_artifacts_skips_paths_outside_results_folder(monkeypatch, tmp_path):
    module = _load_pssm_module(
        monkeypatch,
        tmp_path,
        extra_env={
            "RUNNER_UID": "1234",
            "RUNNER_GID": "5678",
        },
    )

    md5sum = uuid.uuid4().hex
    external_result_dir = tmp_path / "legacy_external_results"
    external_result_dir.mkdir(parents=True, exist_ok=True)
    (external_result_dir / "artifact.txt").write_text("payload\n", encoding="utf-8")

    module._delete_task_artifacts(
        {
            "md5sum": md5sum,
            "result_dir": str(external_result_dir),
        }
    )

    assert external_result_dir.exists()


def test_cleanup_expired_task_artifacts_only_removes_old_terminal_results(monkeypatch, tmp_path):
    module = _load_pssm_module(
        monkeypatch,
        tmp_path,
        extra_env={
            "RUNNER_UID": "1234",
            "RUNNER_GID": "5678",
        },
    )
    now = 2_000_000_000.0
    old_finished_at = now - 31 * 86400
    recent_finished_at = now - 29 * 86400
    tasks = (
        ("finished", old_finished_at, "cleaned:finished", True),
        ("failed", old_finished_at, "cleaned:cancel", True),
        ("cancelled", old_finished_at, "cleaned:cancel", True),
        ("deleting:finished", old_finished_at, "cleaned:finished", True),
        ("finished", recent_finished_at, "finished", False),
        ("running", old_finished_at, "running", False),
    )
    task_artifacts = []

    for status, finished_at, _expected_status, _expired in tasks:
        md5sum = uuid.uuid4().hex
        result_dir = Path(module.app.config["RESULTS_FOLDER"]) / md5sum
        result_dir.mkdir(parents=True)
        (result_dir / "result.txt").write_text("result\n", encoding="utf-8")
        zip_path = Path(module.app.config["RESULTS_FOLDER"]) / f"{md5sum}_results.zip"
        zip_path.write_bytes(b"archive")
        module.task_store.upsert_task(
            md5sum,
            filename="input.fasta",
            file_path=str(result_dir / "input.fasta"),
            result_dir=str(result_dir),
            uploaded_at=finished_at - 60,
            finished_at=finished_at,
            status=status,
            is_binary=0,
            source_ip="127.0.0.1",
            user_agent="pytest",
            username="tester",
        )
        task_artifacts.append((md5sum, result_dir, zip_path))

    from revocompute.maintenance.tasks.result_cleanup import cleanup_expired_task_artifacts

    assert (
        cleanup_expired_task_artifacts(
            30,
            task_store=module.task_store,
            results_folder=module.app.config["RESULTS_FOLDER"],
            now=now,
        )
        == 4
    )

    for (_status, _finished_at, expected_status, expired), (md5sum, result_dir, zip_path) in zip(
        tasks, task_artifacts, strict=True
    ):
        task = module.task_store.get_task(md5sum)
        assert task is not None
        assert task["status"] == expected_status
        assert result_dir.exists() is not expired
        assert zip_path.exists() is not expired


def test_cleanup_skips_task_replaced_before_atomic_claim(monkeypatch, tmp_path):
    module = _load_pssm_module(
        monkeypatch,
        tmp_path,
        extra_env={
            "RUNNER_UID": "1234",
            "RUNNER_GID": "5678",
        },
    )
    now = 2_000_000_000.0
    md5sum = uuid.uuid4().hex
    result_dir = Path(module.app.config["RESULTS_FOLDER"]) / md5sum
    result_dir.mkdir(parents=True)
    fresh_artifact = result_dir / "fresh-result.txt"
    module.task_store.upsert_task(
        md5sum,
        filename="input.fasta",
        file_path=str(result_dir / "input.fasta"),
        result_dir=str(result_dir),
        uploaded_at=now - 32 * 86400,
        finished_at=now - 31 * 86400,
        status="finished",
        is_binary=0,
        username="tester",
    )
    original_claim = module.task_store.claim_task_cleanup

    def replace_then_claim(task_id, **claim):
        module.task_store.update_task(
            task_id,
            uploaded_at=now,
            finished_at=None,
            status="pending",
        )
        fresh_artifact.write_text("new run\n", encoding="utf-8")
        return original_claim(task_id, **claim)

    monkeypatch.setattr(module.task_store, "claim_task_cleanup", replace_then_claim)
    from revocompute.maintenance.tasks.result_cleanup import cleanup_expired_task_artifacts

    assert (
        cleanup_expired_task_artifacts(
            30,
            task_store=module.task_store,
            results_folder=module.app.config["RESULTS_FOLDER"],
            now=now,
        )
        == 0
    )
    assert module.task_store.get_task(md5sum)["status"] == "pending"
    assert fresh_artifact.read_text(encoding="utf-8") == "new run\n"


def test_upload_records_headers_and_local_user(monkeypatch, tmp_path):
    module = _load_pssm_module(
        monkeypatch,
        tmp_path,
        extra_env={
            "RUNNER_UID": "1234",
            "RUNNER_GID": "5678",
        },
    )
    upload_file = module.app.view_functions["upload_file"]
    while "_local_user_identity" not in upload_file.__globals__:
        upload_file = upload_file.__wrapped__
    monkeypatch.setitem(upload_file.__globals__, "_local_user_identity", lambda: "pytest:staff-1000:20")

    class _DummyAsyncResult:
        id = "celery-test-id"

    monkeypatch.setattr(module.run_compute_task, "apply_async", lambda *args, **kwargs: _DummyAsyncResult())

    client = module.app.test_client()
    headers = _test_client_auth(module)
    headers["X-Test-Header"] = "abc\tdef"
    response = client.post(
        "/compute/api/post",
        data={"file": (io.BytesIO(b">test\nACDE\n"), "upload.fasta")},
        headers=headers,
    )
    assert response.status_code == 302
    md5sum = _extract_md5(response.headers["Location"])
    task = module.task_store.get_task(md5sum)
    assert task is not None
    assert task["status"] == "pending"
    assert task["local_user"] == "pytest:staff-1000:20"
    assert task["celery_task_id"] == "celery-test-id"

    headers = json.loads(task["request_headers"])
    assert headers["X-Test-Header"] == "abc def"
    assert "\n" not in task["request_headers"]
    assert "\r" not in task["request_headers"]


def _bearer_headers(base_url: str, username: str, password: str) -> dict[str, str]:
    """Log in via the token endpoint and return a Bearer authorization header."""
    resp = requests.post(
        f"{base_url}/compute/api/auth/login",
        json={"username": username, "password": password},
        timeout=10,
    )
    if resp.status_code != 200:
        raise AssertionError(f"Login failed ({resp.status_code}): {resp.text}")
    return {"Authorization": f"Bearer {resp.json()['token']}"}


def _inject_admin_password(db_path: str, username: str, password: str) -> None:
    """Replace the auto-generated admin password with a known one.

    The server bootstraps an admin with a random password on first run.
    This overwrites the hash so tests can authenticate with Bearer headers.
    """
    import sqlite3

    from werkzeug.security import generate_password_hash

    _hash = generate_password_hash(password)
    conn = sqlite3.connect(str(db_path))
    conn.execute("UPDATE users SET password_hash = ? WHERE username = ?", (_hash, username))
    conn.commit()
    conn.close()


def _test_client_auth(module, username: str = "tester", password: str = "password") -> dict[str, str]:
    """Create a test user and return Bearer token headers for Flask test-client tests.

    Unlike :func:`_bearer_headers`, this works without a running HTTP server —
    it creates the user directly in the DB and generates a token locally.
    """
    db = module.app.config["user_db"]
    user = db.get_user_by_username(username)
    if not user:
        user = db.create_user(
            username=username,
            email=f"{username}@test.local",
            password=password,
            user_status="active",
            registration_status="approved",
        )
        db.verify_email(user["id"])
    from revocompute.auth import generate_token

    return {"Authorization": f"Bearer {generate_token(user['id'])}"}


def _upsert_task_for_user(
    module,
    md5sum: str,
    *,
    filename: str,
    file_path: Path | str,
    result_dir: Path | str,
    username: str,
    status: str = "finished",
    run_stage: str | None = None,
) -> None:
    module.task_store.upsert_task(
        md5sum,
        filename=filename,
        file_path=str(file_path),
        result_dir=str(result_dir),
        uploaded_at=time.time(),
        started_at=time.time(),
        finished_at=time.time(),
        walltime=1.0,
        status=status,
        is_binary=0,
        source_ip="127.0.0.1",
        user_agent="pytest",
        username=username,
        run_stage=run_stage,
    )


def test_legacy_dashboard_root_redirects(monkeypatch, tmp_path):
    """Legacy /PSSM_GREMLIN/ returns 302 to /compute/dashboard."""
    module = _load_pssm_module(
        monkeypatch,
        tmp_path,
        extra_env={"RUNNER_UID": "1234", "RUNNER_GID": "5678"},
    )
    with module.app.test_client() as client:
        response = client.get("/PSSM_GREMLIN/")
        assert response.status_code == 302
        assert response.headers["Location"] == "/compute/dashboard"


def test_dashboard_masks_host_file_paths_on_read_errors(monkeypatch, tmp_path):
    module = _load_pssm_module(
        monkeypatch,
        tmp_path,
        extra_env={
            "RUNNER_UID": "1234",
            "RUNNER_GID": "5678",
        },
    )
    client = module.app.test_client()
    auth_header = _test_client_auth(module)

    md5sum = uuid.uuid4().hex
    result_dir = tmp_path / "result"
    result_dir.mkdir(parents=True, exist_ok=True)
    leaked_host_path = "/home/server-user/REvoDesign/playground/server_test/upload/2KL8.fasta"

    _upsert_task_for_user(
        module,
        md5sum,
        filename="2KL8.fasta",
        file_path=leaked_host_path,
        result_dir=result_dir,
        username="tester",
        status="finished",
    )
    response = client.get("/compute/dashboard", headers=auth_header)
    assert response.status_code == 200
    body = response.get_data(as_text=True)
    assert "00:00:01" in body
    assert 'id="logoutBtn"' in body
    assert 'href="https://github.com/YaoYinYing/REvoDesign" target="_blank"' not in body


def test_failed_status_masks_host_paths_in_api_error(monkeypatch, tmp_path):
    module = _load_pssm_module(
        monkeypatch,
        tmp_path,
        extra_env={
            "RUNNER_UID": "1234",
            "RUNNER_GID": "5678",
        },
    )
    client = module.app.test_client()
    auth_header = _test_client_auth(module)

    md5sum = uuid.uuid4().hex
    result_dir = tmp_path / "result"
    result_dir.mkdir(parents=True, exist_ok=True)
    leaked_host_path = "/home/server-user/REvoDesign/playground/server_test/upload/2KL8.fasta"

    _upsert_task_for_user(
        module,
        md5sum,
        filename="2KL8.fasta",
        file_path=leaked_host_path,
        result_dir=result_dir,
        username="tester",
        status="failed",
    )
    module.task_store.update_task(
        md5sum,
        error=f"Unable to read sequence: [Errno 2] No such file or directory: '{leaked_host_path}'",
    )

    response = client.get(f"/compute/api/running/{md5sum}", headers=auth_header)
    assert response.status_code == 404
    payload = response.get_json()
    assert payload["status"] == "failed"
    assert "/srv/REvoDesign/compute/upload/2KL8.fasta" in payload["error"]
    assert "/home/server-user/REvoDesign" not in payload["error"]


def test_private_dashboard_blocks_non_owner_access(monkeypatch, tmp_path):
    module = _load_pssm_module(
        monkeypatch,
        tmp_path,
        extra_env={
            "RUNNER_UID": "1234",
            "RUNNER_GID": "5678",
        },
    )

    class _DummyAsyncResult:
        id = "celery-test-id"

    monkeypatch.setattr(module.run_compute_task, "apply_async", lambda *args, **kwargs: _DummyAsyncResult())

    client = module.app.test_client()
    owner_header = _test_client_auth(module)
    other_header = _test_client_auth(module, "other", "password2")

    upload = client.post(
        "/compute/api/post",
        data={"file": (io.BytesIO(b">test\nACDE\n"), "upload.fasta")},
        headers=owner_header,
    )
    assert upload.status_code == 302
    md5sum = _extract_md5(upload.headers["Location"])

    owner_running = client.get(f"/compute/api/running/{md5sum}", headers=owner_header)
    assert owner_running.status_code == 202
    assert owner_running.json["status"] == "pending"

    for route in ("running", "results", "download", "cancel"):
        method = client.post if route == "cancel" else client.get
        response = method(f"/compute/api/{route}/{md5sum}", headers=other_header)
        assert response.status_code == 403
        assert response.json["status"] == "forbidden"

    result_page = client.get(f"/compute/results/{md5sum}", headers=other_header)
    assert result_page.status_code == 403
    assert result_page.json["status"] == "forbidden"

    owner_dashboard = client.get("/compute/dashboard", headers=owner_header)
    other_dashboard = client.get("/compute/dashboard", headers=other_header)
    assert owner_dashboard.status_code == 200
    assert other_dashboard.status_code == 200
    assert md5sum in owner_dashboard.get_data(as_text=True)
    assert md5sum not in other_dashboard.get_data(as_text=True)


def test_removed_public_dashboard_env_is_silently_ignored(monkeypatch, tmp_path):
    module = _load_pssm_module(
        monkeypatch,
        tmp_path,
        extra_env={
            "RUNNER_UID": "1234",
            "RUNNER_GID": "5678",
            "PUBLIC_DASHBOARD": "true",
        },
    )

    class _DummyAsyncResult:
        id = "celery-test-id"

    monkeypatch.setattr(module.run_compute_task, "apply_async", lambda *args, **kwargs: _DummyAsyncResult())

    client = module.app.test_client()
    owner_header = _test_client_auth(module)
    other_header = _test_client_auth(module, "other", "password2")

    upload = client.post(
        "/compute/api/post",
        data={"file": (io.BytesIO(b">test\nACDE\n"), "upload.fasta")},
        headers=owner_header,
    )
    assert upload.status_code == 302
    md5sum = _extract_md5(upload.headers["Location"])

    for route in ("running", "results", "download", "cancel"):
        method = client.post if route == "cancel" else client.get
        response = method(f"/compute/api/{route}/{md5sum}", headers=other_header)
        assert response.status_code == 403
        assert response.json["status"] == "forbidden"

    other_dashboard = client.get("/compute/dashboard", headers=other_header)
    assert other_dashboard.status_code == 200
    assert md5sum not in other_dashboard.get_data(as_text=True)


def test_dashboard_running_trace_reflects_log_progress(monkeypatch, tmp_path):
    module = _load_pssm_module(
        monkeypatch,
        tmp_path,
        extra_env={
            "RUNNER_UID": "1234",
            "RUNNER_GID": "5678",
        },
    )
    client = module.app.test_client()
    auth_header = _test_client_auth(module)

    md5sum = uuid.uuid4().hex
    result_dir = tmp_path / "trace_result"
    result_dir.mkdir(parents=True, exist_ok=True)
    fasta_path = result_dir / "trace.fasta"
    fasta_path.write_text(">trace\nACDE\n", encoding="utf-8")

    _upsert_task_for_user(
        module,
        md5sum,
        filename="trace.fasta",
        file_path=fasta_path,
        result_dir=result_dir,
        username="tester",
        status="running",
        run_stage="hhfilter",
    )

    response = client.get("/compute/dashboard", headers=auth_header)
    assert response.status_code == 200
    body = response.get_data(as_text=True)
    assert "HHblits MSA generation [done]" in body
    assert "HHfilter filtering [running]" in body
    assert "GREMLIN optimization [pending]" in body
    assert "PSI-BLAST PSSM [pending]" in body


def test_task_id_is_scoped_by_user(monkeypatch, tmp_path):
    module = _load_pssm_module(
        monkeypatch,
        tmp_path,
        extra_env={
            "RUNNER_UID": "1234",
            "RUNNER_GID": "5678",
        },
    )

    class _DummyAsyncResult:
        id = "celery-test-id"

    monkeypatch.setattr(module.run_compute_task, "apply_async", lambda *args, **kwargs: _DummyAsyncResult())

    client = module.app.test_client()
    owner_header = _test_client_auth(module)
    other_header = _test_client_auth(module, "other", "password2")

    owner_upload = client.post(
        "/compute/api/post",
        data={"file": (io.BytesIO(b">test\nACDE\n"), "same.fasta")},
        headers=owner_header,
    )
    assert owner_upload.status_code == 302
    owner_md5 = _extract_md5(owner_upload.headers["Location"])

    other_upload = client.post(
        "/compute/api/post",
        data={"file": (io.BytesIO(b">test\nACDE\n"), "same.fasta")},
        headers=other_header,
    )
    assert other_upload.status_code == 302
    other_md5 = _extract_md5(other_upload.headers["Location"])

    assert owner_md5 != other_md5


def test_admin_can_manage_other_users_tasks_in_private_mode(monkeypatch, tmp_path):
    module = _load_pssm_module(
        monkeypatch,
        tmp_path,
        extra_env={
            "RUNNER_UID": "1234",
            "RUNNER_GID": "5678",
            "ADMIN_USERS": "admin",
        },
    )
    client = module.app.test_client()
    admin_header = _test_client_auth(module, "admin", "admin_password")

    md5sum = uuid.uuid4().hex
    result_dir = tmp_path / "admin_manage_other_user"
    result_dir.mkdir(parents=True, exist_ok=True)
    _upsert_task_for_user(
        module,
        md5sum,
        filename="owner.fasta",
        file_path=result_dir / "owner.fasta",
        result_dir=result_dir,
        username="tester",
        status="finished",
    )
    module.task_runtime._finalize_results_manifest(module.task_store.get_task(md5sum))

    running = client.get(f"/compute/api/running/{md5sum}", headers=admin_header)
    assert running.status_code == 200
    assert running.json["status"] == "finished"

    results = client.get(f"/compute/api/results/{md5sum}", headers=admin_header, follow_redirects=False)
    assert results.status_code == 200
    assert results.json["task_id"] == md5sum

    dashboard = client.get("/compute/dashboard", headers=admin_header)
    assert dashboard.status_code == 200
    assert md5sum in dashboard.get_data(as_text=True)


def test_private_mode_scopes_task_id_by_user(monkeypatch, tmp_path):
    module = _load_pssm_module(
        monkeypatch,
        tmp_path,
        extra_env={
            "RUNNER_UID": "1234",
            "RUNNER_GID": "5678",
        },
    )

    class _DummyAsyncResult:
        id = "celery-test-id"

    monkeypatch.setattr(module.run_compute_task, "apply_async", lambda *args, **kwargs: _DummyAsyncResult())

    client = module.app.test_client()
    owner_header = _test_client_auth(module)
    other_header = _test_client_auth(module, "other", "password2")

    payload = {"file": (io.BytesIO(b">test\nACDE\n"), "same.fasta")}
    owner_upload = client.post("/compute/api/post", data=payload, headers=owner_header)
    assert owner_upload.status_code == 302
    owner_md5 = _extract_md5(owner_upload.headers["Location"])

    other_upload = client.post(
        "/compute/api/post",
        data={"file": (io.BytesIO(b">test\nACDE\n"), "same.fasta")},
        headers=other_header,
    )
    assert other_upload.status_code == 302
    other_md5 = _extract_md5(other_upload.headers["Location"])

    assert owner_md5 != other_md5


def test_owner_can_delete_own_task_results(monkeypatch, tmp_path):
    module = _load_pssm_module(
        monkeypatch,
        tmp_path,
        extra_env={
            "RUNNER_UID": "1234",
            "RUNNER_GID": "5678",
        },
    )

    client = module.app.test_client()
    owner_header = _test_client_auth(module)

    md5sum = uuid.uuid4().hex
    upload_dir = tmp_path / "upload_owner"
    upload_dir.mkdir(parents=True, exist_ok=True)
    upload_file = upload_dir / "owner.fasta"
    upload_file.write_text(">owner\nACDE\n", encoding="utf-8")
    result_dir = Path(module.app.config["RESULTS_FOLDER"]) / "delete_owner"
    result_dir.mkdir(parents=True, exist_ok=True)
    (result_dir / "artifact.txt").write_text("payload\n", encoding="utf-8")
    zip_path = Path(module.app.config["RESULTS_FOLDER"]) / f"{md5sum}_results.zip"
    zip_path.write_bytes(b"zip")

    _upsert_task_for_user(
        module,
        md5sum,
        filename="owner.fasta",
        file_path=upload_file,
        result_dir=result_dir,
        username="tester",
        status="finished",
    )

    response = client.delete(f"/compute/api/delete/{md5sum}", headers=owner_header)
    assert response.status_code == 200
    assert response.json["status"] == "deleted"
    task = module.task_store.get_task(md5sum)
    assert task is not None
    assert task["status"] == "deleted:finshed"
    assert not result_dir.exists()
    assert not zip_path.exists()
    assert upload_file.exists()

    running = client.get(f"/compute/api/running/{md5sum}", headers=owner_header)
    assert running.status_code == 200
    assert running.json["status"] == "deleted:finshed"


def test_cleanup_claim_blocks_resubmission_and_user_deletion(monkeypatch, tmp_path):
    module = _load_pssm_module(
        monkeypatch,
        tmp_path,
        extra_env={
            "RUNNER_UID": "1234",
            "RUNNER_GID": "5678",
        },
    )

    class _DummyAsyncResult:
        id = "celery-test-id"

    monkeypatch.setattr(module.run_compute_task, "apply_async", lambda *args, **kwargs: _DummyAsyncResult())
    client = module.app.test_client()
    auth_header = _test_client_auth(module)
    content = b">cleanup-race\nACDE\n"

    submitted = client.post(
        "/compute/api/post",
        data={"file": (io.BytesIO(content), "cleanup-race.fasta")},
        headers=auth_header,
    )
    assert submitted.status_code == 302
    md5sum = _extract_md5(submitted.headers["Location"])
    module.task_store.update_task(md5sum, status="deleting:cancel")

    resubmitted = client.post(
        "/compute/api/post",
        data={"file": (io.BytesIO(content), "cleanup-race.fasta")},
        headers=auth_header,
    )
    deleted = client.delete(f"/compute/api/delete/{md5sum}", headers=auth_header)

    assert resubmitted.status_code == 202
    assert deleted.status_code == 409
    assert module.task_store.get_task(md5sum)["status"] == "deleting:cancel"


def test_dashboard_hides_deleted_tasks_until_resubmitted(monkeypatch, tmp_path):
    module = _load_pssm_module(
        monkeypatch,
        tmp_path,
        extra_env={
            "RUNNER_UID": "1234",
            "RUNNER_GID": "5678",
        },
    )

    client = module.app.test_client()
    auth_header = _test_client_auth(module)

    md5sum = uuid.uuid4().hex
    upload_file = tmp_path / "deleted_hidden.fasta"
    upload_file.write_text(">hidden\nACDE\n", encoding="utf-8")
    result_dir = tmp_path / "deleted_hidden"
    result_dir.mkdir(parents=True, exist_ok=True)
    (result_dir / "artifact.txt").write_text("payload\n", encoding="utf-8")

    _upsert_task_for_user(
        module,
        md5sum,
        filename="hidden.fasta",
        file_path=upload_file,
        result_dir=result_dir,
        username="tester",
        status="deleted:finshed",
    )

    hidden_dashboard = client.get("/compute/dashboard", headers=auth_header)
    assert hidden_dashboard.status_code == 200
    assert md5sum not in hidden_dashboard.get_data(as_text=True)

    _upsert_task_for_user(
        module,
        md5sum,
        filename="hidden.fasta",
        file_path=upload_file,
        result_dir=result_dir,
        username="tester",
        status="pending",
    )

    visible_dashboard = client.get("/compute/dashboard", headers=auth_header)
    assert visible_dashboard.status_code == 200
    assert md5sum in visible_dashboard.get_data(as_text=True)


def test_delete_pending_task_marks_deleted_cancel(monkeypatch, tmp_path):
    module = _load_pssm_module(
        monkeypatch,
        tmp_path,
        extra_env={
            "RUNNER_UID": "1234",
            "RUNNER_GID": "5678",
        },
    )
    client = module.app.test_client()
    owner_header = _test_client_auth(module)

    md5sum = uuid.uuid4().hex
    upload_file = tmp_path / "upload_pending.fasta"
    upload_file.write_text(">pending\nACDE\n", encoding="utf-8")
    result_dir = Path(module.app.config["RESULTS_FOLDER"]) / "delete_pending"
    result_dir.mkdir(parents=True, exist_ok=True)
    (result_dir / "artifact.txt").write_text("payload\n", encoding="utf-8")

    _upsert_task_for_user(
        module,
        md5sum,
        filename="pending.fasta",
        file_path=upload_file,
        result_dir=result_dir,
        username="tester",
        status="pending",
    )

    response = client.delete(f"/compute/api/delete/{md5sum}", headers=owner_header)
    assert response.status_code == 200
    task = module.task_store.get_task(md5sum)
    assert task is not None
    assert task["status"] == "deleted:cancel"
    assert not result_dir.exists()
    assert upload_file.exists()


def test_non_owner_cannot_delete_task_results(monkeypatch, tmp_path):
    module = _load_pssm_module(
        monkeypatch,
        tmp_path,
        extra_env={
            "RUNNER_UID": "1234",
            "RUNNER_GID": "5678",
        },
    )

    client = module.app.test_client()
    other_header = _test_client_auth(module, "other", "password2")

    md5sum = uuid.uuid4().hex
    result_dir = tmp_path / "delete_denied"
    result_dir.mkdir(parents=True, exist_ok=True)
    _upsert_task_for_user(
        module,
        md5sum,
        filename="owner.fasta",
        file_path=result_dir / "owner.fasta",
        result_dir=result_dir,
        username="tester",
        status="finished",
    )

    response = client.delete(f"/compute/api/delete/{md5sum}", headers=other_header)
    assert response.status_code == 403
    assert response.json["status"] == "forbidden"
    assert module.task_store.get_task(md5sum) is not None


def test_single_delete_rejects_invalid_task_id(monkeypatch, tmp_path):
    module = _load_pssm_module(
        monkeypatch,
        tmp_path,
        extra_env={
            "RUNNER_UID": "1234",
            "RUNNER_GID": "5678",
        },
    )

    client = module.app.test_client()
    auth_header = _test_client_auth(module)

    response = client.delete("/compute/api/delete/not-a-md5", headers=auth_header)
    assert response.status_code == 400
    assert response.json["status"] == "bad_request"


def test_admin_can_batch_delete_tasks(monkeypatch, tmp_path):
    module = _load_pssm_module(
        monkeypatch,
        tmp_path,
        extra_env={
            "RUNNER_UID": "1234",
            "RUNNER_GID": "5678",
            "ADMIN_USERS": "admin",
        },
    )

    client = module.app.test_client()
    admin_header = _test_client_auth(module, "admin", "admin_password")

    md5_a = uuid.uuid4().hex
    md5_b = uuid.uuid4().hex
    missing_md5 = "0" * 32

    result_a = tmp_path / "batch_a"
    result_b = tmp_path / "batch_b"
    result_a.mkdir(parents=True, exist_ok=True)
    result_b.mkdir(parents=True, exist_ok=True)

    _upsert_task_for_user(
        module,
        md5_a,
        filename="a.fasta",
        file_path=result_a / "a.fasta",
        result_dir=result_a,
        username="tester",
        status="finished",
    )
    _upsert_task_for_user(
        module,
        md5_b,
        filename="b.fasta",
        file_path=result_b / "b.fasta",
        result_dir=result_b,
        username="other",
        status="finished",
    )

    response = client.post(
        "/compute/api/delete",
        headers=admin_header,
        json={"md5sums": [md5_a, md5_b, "zz", missing_md5]},
    )
    assert response.status_code == 200
    payload = response.json
    assert set(payload["deleted"]) == {md5_a, md5_b}
    assert payload["not_found"] == [missing_md5]
    assert payload["ignored"] == ["zz"]
    assert payload["forbidden"] == []
    task_a = module.task_store.get_task(md5_a)
    task_b = module.task_store.get_task(md5_b)
    assert task_a is not None and task_a["status"] == "deleted:finshed"
    assert task_b is not None and task_b["status"] == "deleted:finshed"


def test_batch_delete_guards_and_normalizes_each_md5sum(monkeypatch, tmp_path):
    module = _load_pssm_module(
        monkeypatch,
        tmp_path,
        extra_env={
            "RUNNER_UID": "1234",
            "RUNNER_GID": "5678",
            "ADMIN_USERS": "admin",
        },
    )

    client = module.app.test_client()
    admin_header = _test_client_auth(module, "admin", "admin_password")

    md5sum = uuid.uuid4().hex
    result_dir = tmp_path / "batch_guard_normalize"
    result_dir.mkdir(parents=True, exist_ok=True)
    _upsert_task_for_user(
        module,
        md5sum,
        filename="guard.fasta",
        file_path=result_dir / "guard.fasta",
        result_dir=result_dir,
        username="tester",
        status="finished",
    )

    response = client.post(
        "/compute/api/delete",
        headers=admin_header,
        json={"md5sums": [md5sum.upper(), f"  {md5sum}  ", "zz", "", md5sum]},
    )
    assert response.status_code == 200
    payload = response.json
    assert payload["status"] == "ok"
    assert payload["deleted"] == [md5sum]
    assert payload["ignored"] == ["zz"]
    assert payload["not_found"] == []
    assert payload["forbidden"] == []
    task = module.task_store.get_task(md5sum)
    assert task is not None
    assert task["status"] == "deleted:finshed"


def test_non_admin_batch_delete_only_deletes_owned_tasks(monkeypatch, tmp_path):
    module = _load_pssm_module(
        monkeypatch,
        tmp_path,
        extra_env={
            "RUNNER_UID": "1234",
            "RUNNER_GID": "5678",
            "ADMIN_USERS": "admin",
        },
    )

    client = module.app.test_client()
    user_header = _test_client_auth(module)

    own_md5 = uuid.uuid4().hex
    other_md5 = uuid.uuid4().hex
    own_result = tmp_path / "owned_batch_delete"
    other_result = tmp_path / "foreign_batch_delete"
    own_result.mkdir(parents=True, exist_ok=True)
    other_result.mkdir(parents=True, exist_ok=True)
    _upsert_task_for_user(
        module,
        own_md5,
        filename="owned.fasta",
        file_path=own_result / "owned.fasta",
        result_dir=own_result,
        username="tester",
        status="finished",
    )
    _upsert_task_for_user(
        module,
        other_md5,
        filename="foreign.fasta",
        file_path=other_result / "foreign.fasta",
        result_dir=other_result,
        username="other",
        status="finished",
    )

    response = client.post(
        "/compute/api/delete",
        headers=user_header,
        json={"md5sums": [own_md5, other_md5]},
    )
    assert response.status_code == 200
    payload = response.json
    assert payload["status"] == "ok"
    assert payload["deleted"] == [own_md5]
    assert payload["forbidden"] == [other_md5]
    assert payload["ignored"] == []
    assert payload["not_found"] == []
    own_task = module.task_store.get_task(own_md5)
    other_task = module.task_store.get_task(other_md5)
    assert own_task is not None and own_task["status"] == "deleted:finshed"
    assert other_task is not None and other_task["status"] == "finished"


def test_download_uses_safe_fasta_prefix_filename(monkeypatch, tmp_path):
    module = _load_pssm_module(
        monkeypatch,
        tmp_path,
        extra_env={
            "RUNNER_UID": "1234",
            "RUNNER_GID": "5678",
        },
    )
    client = module.app.test_client()
    auth_header = _test_client_auth(module)

    md5sum = uuid.uuid4().hex
    result_dir = tmp_path / "download_safe_name"
    result_dir.mkdir(parents=True, exist_ok=True)
    upload_file = tmp_path / "unsafe_upload.fasta"
    upload_file.write_text(">x\nACDE\n", encoding="utf-8")
    zip_path = Path(module.app.config["RESULTS_FOLDER"]) / f"{md5sum}_results.zip"
    zip_path.write_bytes(b"zip")

    original_filename = "../unsafe name;\r\nX-Test:1.fasta"
    _upsert_task_for_user(
        module,
        md5sum,
        filename=original_filename,
        file_path=upload_file,
        result_dir=result_dir,
        username="tester",
        status="finished",
    )

    response = client.get(f"/compute/api/download/{md5sum}", headers=auth_header)
    assert response.status_code == 200
    assert response.headers["Content-Length"] == str(len(b"zip"))
    disposition = response.headers.get("Content-Disposition", "")
    expected_prefix = secure_filename(os.path.splitext(os.path.basename(original_filename))[0]) or "result"
    assert "attachment" in disposition
    assert expected_prefix in disposition
    assert "\r" not in disposition
    assert "\n" not in disposition


def test_nginx_download_offload_returns_internal_redirect(monkeypatch, tmp_path):
    module = _load_pssm_module(
        monkeypatch,
        tmp_path,
        extra_env={
            "RUNNER_UID": "1234",
            "RUNNER_GID": "5678",
            "RESULT_DOWNLOAD_MODE": "nginx",
        },
    )
    client = module.app.test_client()
    auth_header = _test_client_auth(module)

    md5sum = uuid.uuid4().hex
    result_dir = tmp_path / "nginx_download"
    result_dir.mkdir(parents=True)
    upload_file = result_dir / "input.fasta"
    upload_file.write_text(">x\nACDE\n", encoding="utf-8")
    archive = Path(module.app.config["RESULTS_FOLDER"]) / f"{md5sum}_results.zip"
    archive.write_bytes(b"zip")
    _upsert_task_for_user(
        module,
        md5sum,
        filename="input.fasta",
        file_path=upload_file,
        result_dir=result_dir,
        username="tester",
        status="finished",
    )

    response = client.get(f"/compute/api/download/{md5sum}", headers=auth_header)
    head_response = client.head(f"/compute/api/download/{md5sum}", headers=auth_header)

    assert response.status_code == 200
    assert response.data == b""
    assert response.headers["X-Accel-Redirect"] == f"/_protected_results/{archive.name}"
    assert response.headers["Content-Type"] == "application/zip"
    assert response.headers["Cache-Control"] == "private, no-store"
    assert response.headers["Content-Disposition"].startswith("attachment;")
    assert head_response.status_code == 200
    assert head_response.data == b""
    assert head_response.headers["X-Accel-Redirect"] == f"/_protected_results/{archive.name}"


def test_download_does_not_pack_missing_archive_in_request(monkeypatch, tmp_path):
    module = _load_pssm_module(
        monkeypatch,
        tmp_path,
        extra_env={"RUNNER_UID": "1234", "RUNNER_GID": "5678"},
    )
    client = module.app.test_client()
    auth_header = _test_client_auth(module)

    md5sum = uuid.uuid4().hex
    result_dir = tmp_path / "missing_archive"
    result_dir.mkdir(parents=True)
    upload_file = result_dir / "input.fasta"
    upload_file.write_text(">x\nACDE\n", encoding="utf-8")
    _upsert_task_for_user(
        module,
        md5sum,
        filename="input.fasta",
        file_path=upload_file,
        result_dir=result_dir,
        username="tester",
        status="finished",
    )

    response = client.get(f"/compute/api/download/{md5sum}", headers=auth_header)

    assert response.status_code == 409
    assert response.json["message"] == "Request the optional archive first"
    assert not list(Path(module.app.config["RESULTS_FOLDER"]).glob("*.zip"))


def test_failed_task_archive_is_downloadable(monkeypatch, tmp_path):
    module = _load_pssm_module(
        monkeypatch,
        tmp_path,
        extra_env={
            "RUNNER_UID": "1234",
            "RUNNER_GID": "5678",
        },
    )
    client = module.app.test_client()
    auth_header = _test_client_auth(module)

    md5sum = uuid.uuid4().hex
    result_dir = tmp_path / "failed_download"
    result_dir.mkdir(parents=True, exist_ok=True)
    upload_file = tmp_path / "failed.fasta"
    upload_file.write_text(">x\nACDE\n", encoding="utf-8")
    zip_path = Path(module.app.config["RESULTS_FOLDER"]) / f"{md5sum}_results.zip"
    with zipfile.ZipFile(zip_path, "w") as archive:
        archive.writestr("task_failed.txt", "runner failed\n")

    _upsert_task_for_user(
        module,
        md5sum,
        filename="failed.fasta",
        file_path=upload_file,
        result_dir=result_dir,
        username="tester",
        status="failed",
    )
    module.task_store.update_task(md5sum, error="runner failed")

    response = client.get(f"/compute/api/download/{md5sum}", headers=auth_header)
    assert response.status_code == 200
    disposition = response.headers.get("Content-Disposition", "")
    assert "attachment" in disposition
    assert response.data


# ==================================================================
# Admin user control helpers
