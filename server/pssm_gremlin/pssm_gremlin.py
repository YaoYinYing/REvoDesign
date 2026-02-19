# Copyright (c) 2026 The REvoDesign Developers.
# Distributed under the terms of the GNU General Public License v3.0.
# SPDX-License-Identifier: GPL-3.0-only


#! /mnt/data/envs/conda_env/envs/REvoDesign/bin/python


import glob
import hashlib
import os
import shutil
import signal
import subprocess
from datetime import datetime

import docker
from absl import app, logging
from celery import Celery
from celery.result import AsyncResult
from docker import types
from flask import Flask, jsonify, redirect, render_template, request, send_from_directory
from flask_httpauth import HTTPBasicAuth
from werkzeug.security import check_password_hash, generate_password_hash

THIS_FILE = os.path.abspath(__file__)
THIS_DIR = os.path.dirname(THIS_FILE)

app = Flask(__name__, template_folder="./templates")
auth = HTTPBasicAuth()

# TODO: 
# currently the server uses files and md5sums to manage tasks. its not as convinient as databases like sqlite. 
# refactor the server file to use sqlite instead.
# sqlite are expected to record
# 1. upload file: path and md5sum
# 2. validate the file: text or binary(like Microsoft Office Word docx?)? if binary mark it as negative
# 3. times that: uploaded, start to process, end of processing, walltime (end - start)
# 4. task status: pending(in queue), processing (running), success (finished) or failed (error)
# 5. task source: submission IP (for cloudflare tunnel, it should be `CF-Connecting-IP` or `CF-Connecting-IPv6` at header), user-agent, user basic auth info, 
# handle security issues and guard the server from dangers like injections or xss attacks
# reduce the complicity of code structures
# 


def _env_path(var_name: str, default: str) -> str:
    value = os.environ.get(var_name)
    if value:
        return os.path.abspath(os.path.expanduser(value))
    return os.path.abspath(default)


def _env_int(var_name: str, default: int) -> int:
    raw = os.environ.get(var_name)
    if raw is None or raw == "":
        return default
    try:
        return int(raw)
    except ValueError as exc:
        raise ValueError(f"Environment variable {var_name} must be an integer, got {raw!r}") from exc


def _resolve_docker_user() -> str:
    env_user = os.environ.get("PSSM_GREMLIN_RUNNER_USER")
    env_uid = os.environ.get("PSSM_GREMLIN_RUNNER_UID")
    env_gid = os.environ.get("PSSM_GREMLIN_RUNNER_GID")

    if env_user:
        return env_user

    if env_uid and env_gid:
        return f"{env_uid}:{env_gid}"

    if env_uid:
        return env_uid

    try:
        return f"{os.geteuid()}:{os.getegid()}"
    except AttributeError:
        return "0:0"


def _ensure_directories(*paths: str) -> None:
    for path in paths:
        os.makedirs(path, exist_ok=True)


user_file = os.environ.get("PSSM_GREMLIN_USERS_FILE", os.path.join(THIS_DIR, "users.txt"))
user_file = os.path.abspath(user_file)

if not os.path.exists(user_file):
    raise FileNotFoundError(
        f"Unable to start GREMLIN server without user credentials. Expected file at {user_file}"
    )

# A dictionary of users and their hashed passwords
users = {}

with open(user_file) as f:
    for line in f:
        if line.strip() == "":
            continue
        if line.strip().startswith(("#", ";")):
            continue
        username, password = line.strip().split(":")
        users[username] = generate_password_hash(password)


# Celery configurations
redis_url = os.environ.get("PSSM_GREMLIN_REDIS_URL", "redis://localhost:6379/0")
celery_backend = os.environ.get("PSSM_GREMLIN_RESULT_BACKEND", redis_url)
celery_broker = os.environ.get("PSSM_GREMLIN_BROKER_URL", redis_url)
celery = Celery(
    app.name,
    broker=celery_broker,
    backend=celery_backend,
)

# Directory for server to save uploaded input and processed results.
SERVER_DIR = _env_path("PSSM_GREMLIN_SERVER_DIR", "/mnt/data/yinying/server/")
PORT = _env_int("PSSM_GREMLIN_PORT", 8080)

DOCKER_IMAGE = os.environ.get("PSSM_GREMLIN_RUNNER_IMAGE", "revodesign-pssm-gremlin")
DOCKER_USER = _resolve_docker_user()

# DBs
UNIREF_30_DB = _env_path(
    "PSSM_GREMLIN_DB_UNIREF30",
    "/mnt/db/uniref30_uc30/UniRef30_2022_02/UniRef30_2022_02",
)
UNIREF_90_DB = _env_path("PSSM_GREMLIN_DB_UNIREF90", "/mnt/db/uniref90/uniref90")

# CPUS per job
NPROC = _env_int("PSSM_GREMLIN_NPROC", 16)

# number of processors for a run
os.environ["GREMLIN_CALC_CPU_NUM"] = f"{NPROC}"

# Define a directory for storing temporary files
UPLOAD_FOLDER = f"{SERVER_DIR}/upload"
app.config["UPLOAD_FOLDER"] = UPLOAD_FOLDER

# Define a directory for storing the results
RESULTS_FOLDER = f"{SERVER_DIR}/results"
app.config["RESULTS_FOLDER"] = RESULTS_FOLDER

# Define a directory for storing state marker files
STATE_FOLDER = f"{SERVER_DIR}/state"
app.config["STATE_FOLDER"] = STATE_FOLDER

_ensure_directories(UPLOAD_FOLDER, RESULTS_FOLDER, STATE_FOLDER)

try:
    _ROOT_MOUNT_DIRECTORY = f"/home/{os.getlogin()}"
except BaseException:
    _ROOT_MOUNT_DIRECTORY = os.path.abspath("/tmp/")
    os.makedirs(_ROOT_MOUNT_DIRECTORY, exist_ok=True)


@auth.verify_password
def verify_password(username, password):
    if username in users and check_password_hash(users.get(username), password):
        return username
    return None


def _create_mount(mount_name: str, path: str, read_only=True) -> tuple[types.Mount, str]:
    """Create a mount point for each file and directory used by the model."""
    path = os.path.abspath(path)
    target_path = os.path.join(_ROOT_MOUNT_DIRECTORY, mount_name)

    if not read_only:
        logging.warning(f"{mount_name} is not read-only!")

    if os.path.isdir(path):
        source_path = path
        mounted_path = target_path
    else:
        source_path = os.path.dirname(path)
        mounted_path = os.path.join(target_path, os.path.basename(path))
    if not os.path.exists(source_path):
        os.makedirs(source_path)
    logging.info("Mounting %s -> %s", source_path, target_path)
    mount = types.Mount(
        target=str(target_path),
        source=str(source_path),
        type="bind",
        read_only=read_only,
    )
    return mount, str(mounted_path)


def get_file_time(file_path, modified=False):
    if os.path.exists(file_path):
        try:
            if modified:
                return os.path.getmtime(file_path)
            else:
                return os.path.getctime(file_path)
        except OSError:
            return None  # Handle file not found or other errors
    else:
        return None


def run_pssm_gremlin_in_docker(fasta_path, output_dir, docker_client=None):
    mounts = []
    command_args = []

    if os.path.exists(fasta_path):
        fasta = os.path.abspath(fasta_path)
        mount_fasta, mounted_fasta = _create_mount(mount_name="fasta", path=fasta, read_only=True)
        mounts.append(mount_fasta)
        command_args.append(f"-i {mounted_fasta}")

    os.makedirs(output_dir, exist_ok=True)
    output = os.path.abspath(output_dir)
    mount_output, mounted_output = _create_mount(mount_name="output", path=output, read_only=False)
    mounts.append(mount_output)
    command_args.append(f"-o {mounted_output}")

    uniref30_db = os.path.abspath(UNIREF_30_DB)
    mount_uniref30_db, mounted_uniref30_db = _create_mount(mount_name="uniref30_db", path=uniref30_db, read_only=True)
    mounts.append(mount_uniref30_db)
    command_args.append(f"-U {mounted_uniref30_db}")

    uniref90_db = os.path.abspath(UNIREF_90_DB)
    mount_uniref90_db, mounted_uniref90_db = _create_mount(mount_name="uniref90_db", path=uniref90_db, read_only=True)
    mounts.append(mount_uniref90_db)
    command_args.append(f"-u {mounted_uniref90_db}")

    command_args.append(f"-j {NPROC}")

    logging.info(command_args)

    client = docker_client or docker.from_env()

    container = client.containers.run(
        image=DOCKER_IMAGE,
        command=command_args,
        remove=True,
        detach=True,
        mounts=mounts,
        user=DOCKER_USER,
        stdout=True,
        stderr=True,
    )

    # Add signal handler to ensure CTRL+C also stops the running container.
    signal.signal(signal.SIGINT, lambda unused_sig, unused_frame: container.kill())

    for line in container.logs(stream=True):
        logging.info(line.strip().decode("utf-8"))

    return


def get_task_walltime(submitted_time, finished_time):
    if submitted_time and finished_time:
        return finished_time - submitted_time
    else:
        return "-"


def format_times(timestamp):
    if timestamp:
        return datetime.fromtimestamp(timestamp).strftime("%Y-%m-%d %H:%M:%S")
    else:
        return None


@celery.task
def run_gremlin_task(md5sum, filename):
    output_dir = os.path.join(app.config["RESULTS_FOLDER"], md5sum)
    state_file = os.path.join(app.config["STATE_FOLDER"], md5sum + ".state")
    uploaded_file = os.path.join(output_dir, filename)
    with open(state_file) as f:
        status = f.read().strip()

    # early return if not in queue or in processing
    if status not in ["queued", "running"]:
        return

    with open(state_file, "w") as f:
        f.write("running")

    try:
        run_pssm_gremlin_in_docker(
            fasta_path=uploaded_file,
            output_dir=output_dir,
        )

        with open(
            state_file,
            "w",
        ) as f:
            f.write("finished")
            return
    except docker.errors.ContainerError as e:
        print(e)
        with open(
            state_file,
            "w",
        ) as f:
            f.write("failed: in docker")
            return
    except Exception as e:
        with open(state_file, "w") as f:
            f.write(f"failed: {e}")
        return


@app.route("/PSSM_GREMLIN/create_task", methods=["GET"])
@auth.login_required
def create_task():
    return render_template("create_task.html")


@app.route("/PSSM_GREMLIN/api/post", methods=["POST"])
@auth.login_required
def upload_file():
    if "file" not in request.files:
        return jsonify({"error": "No file part"}), 400

    file = request.files["file"]
    if file.filename == "":
        return jsonify({"error": "No selected file"}), 400

    if file:
        # Save the uploaded file with its original name
        filename = os.path.join(app.config["UPLOAD_FOLDER"], file.filename)

        # Ensure the uploaded file has the correct extension
        if not filename.endswith(".fasta"):
            return (
                jsonify({"error": "Uploaded file must have the .fasta extension"}),
                400,
            )

        file.save(filename)

        # Calculate MD5sum for the uploaded file
        md5sum = hashlib.md5(open(filename, "rb").read()).hexdigest()

        # Create a directory for the results using the MD5sum as the directory name
        result_dir = os.path.join(app.config["RESULTS_FOLDER"], md5sum)

        state_file = os.path.join(app.config["STATE_FOLDER"], md5sum + ".state")

        # early return for finished tasks
        if os.path.exists(os.path.join(result_dir, "log", "task_finished")):
            return redirect(f"/PSSM_GREMLIN/api/running/{md5sum}", code=302)

        # early return for running tasks
        if os.path.exists(state_file) and (
            (job_state := open(state_file).read().strip()) == "running" or job_state == "queued"
        ):
            return (
                jsonify(
                    {
                        "status": "still running, ingore repetative task",
                        "md5sum": md5sum,
                    }
                ),
                202,
            )

        # Check if the directory already exists
        if os.path.exists(result_dir):
            shutil.rmtree(result_dir)

        # Create the result directory
        os.makedirs(result_dir)
        shutil.copy(filename, result_dir)

        with open(state_file, "w") as f:
            f.write("queued")

        # Enqueue the task to run GREMLIN_PSSM
        run_gremlin_task.apply_async(args=[md5sum, os.path.basename(filename)])

        # Redirect to the running endpoint with the MD5sum and result directory
        return redirect(f"/PSSM_GREMLIN/api/running/{md5sum}", code=302)


@app.route("/PSSM_GREMLIN/api/running/<md5sum>", methods=["GET"])
@auth.login_required
def run_gremlin(md5sum):
    output_dir = os.path.join(app.config["RESULTS_FOLDER"], md5sum)
    state_file = os.path.join(app.config["STATE_FOLDER"], md5sum + ".state")

    # connect pipeline state marker to the server state
    if os.path.exists(os.path.join(output_dir, "log", "task_finished")):
        with open(state_file, "w") as f:
            f.write("finished")

    # Check the status in the state marker file
    if os.path.exists(state_file):
        with open(state_file) as f:
            status = f.read().strip()
        # early return if the status is not running
        if status == "finished":
            return jsonify({"status": status, "md5sum": md5sum}), 200
        elif status.startswith("failed"):
            return jsonify({"status": status, "md5sum": md5sum}), 404
        elif status == "running":
            return jsonify({"status": "still running", "md5sum": md5sum}), 202
        elif status == "queued":
            return jsonify({"status": "still in queue", "md5sum": md5sum}), 202
        else:
            return (
                jsonify({"status": "unknow task state", "md5sum": md5sum}),
                500,
            )

    else:
        return jsonify({"status": "internal error", "md5sum": md5sum}), 500


@app.route("/PSSM_GREMLIN/api/results/<md5sum>", methods=["GET"])
@auth.login_required
def get_results(md5sum):
    result_dir = os.path.join(app.config["RESULTS_FOLDER"], md5sum)
    state_file = os.path.join(app.config["STATE_FOLDER"], md5sum + ".state")
    fasta_fn = os.path.basename(glob.glob(f"{result_dir}/*.fasta")[0])

    # connect pipeline state marker to the server state
    if os.path.exists(os.path.join(result_dir, "log", "task_finished")):
        with open(state_file, "w") as f:
            f.write("finished")

    # Check if the task has finished
    if os.path.exists(state_file):
        with open(state_file) as f:
            status = f.read().strip()

        # Create a zip file with all the result files
        zip_filename = os.path.join(
            app.config["RESULTS_FOLDER"],
            f'{fasta_fn.replace(".fasta", "")}_PSSM_GREMLIN_results.zip',
        )
        if status == "finished":
            if not os.path.exists(zip_filename):
                shutil.make_archive(os.path.splitext(zip_filename)[0], "zip", result_dir)
                # Provide a link to download the zip file
            return redirect(f"/PSSM_GREMLIN/api/download/{md5sum}", code=302)

        else:
            # If the task is not finished, return a waiting response
            return redirect(f"/PSSM_GREMLIN/api/running/{md5sum}", code=302)
    else:
        # If the task is not finished, return a waiting response
        return redirect(f"/PSSM_GREMLIN/api/running/{md5sum}", code=302)


@app.route("/PSSM_GREMLIN/api/download/<md5sum>", methods=["GET"])
@auth.login_required
def download_results(md5sum):
    result_dir = os.path.join(app.config["RESULTS_FOLDER"], md5sum)
    fasta_fn = os.path.basename(glob.glob(f"{result_dir}/*.fasta")[0])
    zip_filename = os.path.join(
        app.config["RESULTS_FOLDER"],
        f'{fasta_fn.replace(".fasta", "")}_PSSM_GREMLIN_results.zip',
    )

    # Check if the zip file exists
    if os.path.exists(zip_filename):
        # Send the zip file as an attachment
        return send_from_directory(
            app.config["RESULTS_FOLDER"],
            f'{fasta_fn.replace(".fasta", "")}_PSSM_GREMLIN_results.zip',
            as_attachment=True,
        )

    # If the zip file doesn't exist, return an error response
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


@app.route("/PSSM_GREMLIN/api/cancel/<md5sum>", methods=["POST", "GET"])
@auth.login_required
def cancel_task(md5sum):
    # Check if the task with the specified MD5sum exists and is not finished
    state_file = os.path.join(STATE_FOLDER, f"{md5sum}.state")

    if os.path.exists(state_file):
        with open(state_file) as f:
            status = f.read().strip()

        if status in ["queued", "running"]:
            # Get the Celery task ID based on the MD5sum
            task_id = f"run_gremlin_task-{md5sum}"

            try:
                # Remove the task from the Celery queue
                result = AsyncResult(task_id)
                result.revoke(terminate=True)  # Terminate and remove the task

                if status == "queued":
                    # After cancelling the task, update the task's status to 'cancelled'
                    with open(state_file, "w") as f:
                        f.write("cancelled")
                    return (
                        jsonify({"status": "cancelled", "md5sum": md5sum}),
                        200,
                    )

                if status == "running":
                    try:
                        cmd = f"ps aux | grep {md5sum} | awk '{{system(\"kill \"$2)}}'"
                        subprocess.run(cmd, shell=True)
                        # After cancelling the task, update the task's status to 'cancelled'
                        with open(state_file, "w") as f:
                            f.write("cancelled")
                        return (
                            jsonify({"status": "killed", "md5sum": md5sum}),
                            200,
                        )
                    except BaseException:
                        return (
                            jsonify(
                                {
                                    "status": "Failed to kill running task",
                                    "md5sum": md5sum,
                                }
                            ),
                            200,
                        )

            except Exception:
                return jsonify({"error": "Failed to cancel the task"}), 500
        else:
            return (
                jsonify({"error": "Task cannot be cancelled as it is not in the queue or running"}),
                400,
            )
    else:
        return jsonify({"error": "Task not found"}), 404


@app.route("/PSSM_GREMLIN/dashboard", methods=["GET"])
@auth.login_required
def task_dashboard():
    # Query state marker files to gather task status information
    state_folder = app.config["STATE_FOLDER"]
    results_folder = app.config["RESULTS_FOLDER"]
    task_statuses = []
    i = 0

    for filename in os.listdir(state_folder):
        if filename.endswith(".state"):
            md5sum = filename.replace(".state", "")
            with open(os.path.join(state_folder, filename)) as f:
                status = f.read().strip()
            fasta_fp = glob.glob(f"{results_folder}/{md5sum}/*.fasta")[0]
            fasta_fn = os.path.basename(fasta_fp)
            submitted_time = get_file_time(fasta_fp)
            finished_time = get_file_time(os.path.join(state_folder, filename), modified=True)
            walltime = get_task_walltime(submitted_time=submitted_time, finished_time=finished_time)
            with open(os.path.join(UPLOAD_FOLDER, fasta_fn)) as f:
                try:
                    fasta_seq = f.read().strip()
                except UnicodeDecodeError as e:
                    fasta_seq = f"Unable to decode sequence: {e}"

            task_statuses.append(
                {
                    "id": i,
                    "md5": md5sum,
                    "status": status,
                    "fasta_fn": fasta_fn,
                    "submitted_time": format_times(submitted_time),
                    "finished_time": format_times(finished_time) if status == "finished" else "-",
                    "walltime": int(walltime) if status == "finished" else "-",
                    "submitted_timestamp": submitted_time,
                    "sequence": fasta_seq,
                }
            )
            i += 1

    # Sort the task_statuses dictionary by submitted_time (ascending order)
    sorted_task_statuses = list(
        sorted(
            task_statuses,
            key=lambda x: x["submitted_timestamp"],
            reverse=True,
        )
    )

    # return jsonify(sorted_task_statuses)

    # Render the HTML template with sorted task status information
    return render_template(
        "pssm_gremlin_dashboard.html",
        sorted_task_statuses=sorted_task_statuses,
    )


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=PORT)
