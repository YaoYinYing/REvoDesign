#! /mnt/data/envs/conda_env/envs/REvoDesign/bin/python

import os
import subprocess
import hashlib
import shutil
import glob


from flask import Flask, request, jsonify, redirect, send_from_directory
from flask import render_template

from celery import Celery
from celery.result import AsyncResult

app = Flask(__name__, template_folder='./templates')

# Celery configurations
celery = Celery(
    app.name,
    broker='redis://localhost:6379/0',
    backend='redis://localhost:6379/0',
)

# Directory for server to save uploaded input and processed results.
SERVER_DIR = '/path/to/PSSM_GREMLIN/run/dir/'
PORT=8080



# number of processors for a run
os.environ['GREMLIN_CALC_CPU_NUM'] = '16'

RUN_SCRIPT_PATH = os.path.dirname(os.path.abspath(__file__))

# Define a directory for storing temporary files
UPLOAD_FOLDER = f'{SERVER_DIR}/upload'
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

# Define a directory for storing the results
RESULTS_FOLDER = f'{SERVER_DIR}/results'
app.config['RESULTS_FOLDER'] = RESULTS_FOLDER

# Define a directory for storing state marker files
STATE_FOLDER = f'{SERVER_DIR}/state'
app.config['STATE_FOLDER'] = STATE_FOLDER

import os
from datetime import datetime


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


def get_task_walltime(submitted_time, finished_time):
    if submitted_time and finished_time:
        return finished_time - submitted_time
    else:
        return '-'


def format_times(timestamp):
    if timestamp:
        return datetime.fromtimestamp(timestamp).strftime('%Y-%m-%d %H:%M:%S')
    else:
        return None


@celery.task
def run_gremlin_task(md5sum, filename):
    output_dir = os.path.join(app.config['RESULTS_FOLDER'], md5sum)
    uploaded_file = os.path.join(output_dir, filename)
    with open(
        os.path.join(app.config['STATE_FOLDER'], md5sum + '.state'), 'r'
    ) as f:
        status = f.read().strip()

    # early return if not in queue or in processing
    if status not in ['queued', 'running']:
        return

    with open(
        os.path.join(app.config['STATE_FOLDER'], md5sum + '.state'), 'w'
    ) as f:
        f.write('running')

    cmd = f'bash {os.path.join(RUN_SCRIPT_PATH, "..")}/REvoDesign_PSSM_GREMLIN.sh -i {uploaded_file} -o {output_dir} -j 16 > {os.path.join(app.config["RESULTS_FOLDER"],md5sum,filename.replace("fasta", "log"))} '

    try:
        runner = subprocess.Popen(
            cmd, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE
        )
        runner.wait()  # Wait for the process to complete
        if runner.returncode == 0:
            with open(
                os.path.join(app.config['STATE_FOLDER'], md5sum + '.state'),
                'w',
            ) as f:
                f.write('finished')
                return
        else:
            with open(
                os.path.join(app.config['STATE_FOLDER'], md5sum + '.state'),
                'w',
            ) as f:
                f.write('failed')
                return
    except Exception as e:
        with open(
            os.path.join(app.config['STATE_FOLDER'], md5sum + '.state'), 'w'
        ) as f:
            f.write('failed')
        return


@app.route('/PSSM_GREMLIN/api/post', methods=['POST'])
def upload_file():
    if 'file' not in request.files:
        return jsonify({'error': 'No file part'}), 400

    file = request.files['file']
    if file.filename == '':
        return jsonify({'error': 'No selected file'}), 400

    if file:
        # Save the uploaded file with its original name
        filename = os.path.join(app.config['UPLOAD_FOLDER'], file.filename)

        # Ensure the uploaded file has the correct extension
        if not filename.endswith('.fasta'):
            return (
                jsonify(
                    {'error': 'Uploaded file must have the .fasta extension'}
                ),
                400,
            )

        file.save(filename)

        # Calculate MD5sum for the uploaded file
        md5sum = hashlib.md5(open(filename, 'rb').read()).hexdigest()

        # Create a directory for the results using the MD5sum as the directory name
        result_dir = os.path.join(app.config['RESULTS_FOLDER'], md5sum)

        state_file = os.path.join(
            app.config['STATE_FOLDER'], md5sum + '.state'
        )

        # early return for finished tasks
        if os.path.exists(os.path.join(result_dir, 'log', 'task_finished')):
            return redirect(f'/PSSM_GREMLIN/api/results/{md5sum}', code=302)

        # early return for running tasks
        if (
            os.path.exists(state_file)
            and open(state_file, 'r').read().strip() == 'running'
        ):
            return (
                jsonify(
                    {
                        'status': 'still running, ingore repetative task',
                        'md5sum': md5sum,
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

        with open(
            os.path.join(app.config['STATE_FOLDER'], md5sum + '.state'), 'w'
        ) as f:
            f.write('queued')

        # Enqueue the task to run GREMLIN_PSSM
        run_gremlin_task.apply_async(args=[md5sum, os.path.basename(filename)])

        # Redirect to the running endpoint with the MD5sum and result directory
        return redirect(f'/PSSM_GREMLIN/api/running/{md5sum}', code=302)


@app.route('/PSSM_GREMLIN/api/running/<md5sum>', methods=['GET'])
def run_gremlin(md5sum):
    output_dir = os.path.join(app.config['RESULTS_FOLDER'], md5sum)
    state_file = os.path.join(app.config['STATE_FOLDER'], md5sum + '.state')

    # connect pipeline state marker to the server state
    if os.path.exists(os.path.join(output_dir, 'log', 'task_finished')):
        with open(state_file, 'w') as f:
            f.write('finished')

    # Check the status in the state marker file
    if os.path.exists(state_file):
        with open(state_file, 'r') as f:
            status = f.read().strip()
        # early return if the status is not running
        if status == 'finished':
            return redirect(f'/PSSM_GREMLIN/api/results/{md5sum}', code=302)
        elif status == 'failed':
            return redirect(f'/PSSM_GREMLIN/api/error/{md5sum}', code=302)
        elif status == 'running':
            return jsonify({'status': 'still running', 'md5sum': md5sum}), 202
        elif status == 'queued':
            return jsonify({'status': 'still in queue', 'md5sum': md5sum}), 202
        else:
            return (
                jsonify({'status': 'unknow task state', 'md5sum': md5sum}),
                500,
            )

    else:
        return jsonify({'status': 'internal error', 'md5sum': md5sum}), 500


@app.route('/PSSM_GREMLIN/api/results/<md5sum>', methods=['GET'])
def get_results(md5sum):
    result_dir = os.path.join(app.config['RESULTS_FOLDER'], md5sum)
    state_file = os.path.join(app.config['STATE_FOLDER'], md5sum + '.state')
    fasta_fn = os.path.basename(glob.glob(f'{result_dir}/*.fasta')[0])

    # connect pipeline state marker to the server state
    if os.path.exists(os.path.join(result_dir, 'log', 'task_finished')):
        with open(state_file, 'w') as f:
            f.write('finished')

    # Check if the task has finished
    if os.path.exists(state_file):
        with open(state_file, 'r') as f:
            status = f.read().strip()

        # Create a zip file with all the result files
        zip_filename = os.path.join(
            app.config['RESULTS_FOLDER'],
            f'{fasta_fn.replace(".fasta","")}_PSSM_GREMLIN_results.zip',
        )
        if status == 'finished':
            if not os.path.exists(zip_filename):
                shutil.make_archive(
                    os.path.splitext(zip_filename)[0], 'zip', result_dir
                )
                # Provide a link to download the zip file
            return redirect(f'/PSSM_GREMLIN/api/download/{md5sum}', code=302)

        else:
            # If the task is not finished, return a waiting response
            return redirect(f'/PSSM_GREMLIN/api/running/{md5sum}', code=302)
    else:
        # If the task is not finished, return a waiting response
        return redirect(f'/PSSM_GREMLIN/api/running/{md5sum}', code=302)


@app.route('/PSSM_GREMLIN/api/download/<md5sum>', methods=['GET'])
def download_results(md5sum):
    result_dir = os.path.join(app.config['RESULTS_FOLDER'], md5sum)
    fasta_fn = os.path.basename(glob.glob(f'{result_dir}/*.fasta')[0])
    zip_filename = os.path.join(
        app.config['RESULTS_FOLDER'],
        f'{fasta_fn.replace(".fasta","")}_PSSM_GREMLIN_results.zip',
    )

    # Check if the zip file exists
    if os.path.exists(zip_filename):
        # Send the zip file as an attachment
        return send_from_directory(
            app.config['RESULTS_FOLDER'],
            f'{fasta_fn.replace(".fasta","")}_PSSM_GREMLIN_results.zip',
            as_attachment=True,
        )

    # If the zip file doesn't exist, return an error response
    return (
        jsonify(
            {
                'status': 'error',
                'md5sum': md5sum,
                'message': 'result file not found',
            }
        ),
        404,
    )


@app.route('/PSSM_GREMLIN/api/cancel/<md5sum>', methods=['POST'])
def cancel_task(md5sum):
    # Check if the task with the specified MD5sum exists and is not finished
    state_file = os.path.join(STATE_FOLDER, f'{md5sum}.state')

    if os.path.exists(state_file):
        with open(state_file, 'r') as f:
            status = f.read().strip()

        if status in ['queued', 'running']:
            # Get the Celery task ID based on the MD5sum
            task_id = f'run_gremlin_task-{md5sum}'

            try:
                # Remove the task from the Celery queue
                result = AsyncResult(task_id)
                result.revoke(terminate=True)  # Terminate and remove the task

                if status == 'queued':
                    # After cancelling the task, update the task's status to 'cancelled'
                    with open(state_file, 'w') as f:
                        f.write('cancelled')
                    return (
                        jsonify({'status': 'cancelled', 'md5sum': md5sum}),
                        200,
                    )

                if status == 'running':
                    try:
                        cmd = f'ps aux | grep {md5sum} | awk \'{{system("kill "$2)}}\''
                        subprocess.run(cmd, shell=True)
                        # After cancelling the task, update the task's status to 'cancelled'
                        with open(state_file, 'w') as f:
                            f.write('cancelled')
                        return (
                            jsonify({'status': 'killed', 'md5sum': md5sum}),
                            200,
                        )
                    except:
                        return (
                            jsonify(
                                {
                                    'status': 'Failed to kill running task',
                                    'md5sum': md5sum,
                                }
                            ),
                            200,
                        )

            except Exception as e:
                return jsonify({'error': 'Failed to cancel the task'}), 500
        else:
            return (
                jsonify(
                    {
                        'error': 'Task cannot be cancelled as it is not in the queue or running'
                    }
                ),
                400,
            )
    else:
        return jsonify({'error': 'Task not found'}), 404


@app.route('/PSSM_GREMLIN/dashboard', methods=['GET'])
def task_dashboard():
    # Query state marker files to gather task status information
    state_folder = app.config['STATE_FOLDER']
    results_folder = app.config['RESULTS_FOLDER']
    task_statuses = {}

    task_summary = {
        'total_tasks': 0,
        'finished_tasks': 0,
        'processing_tasks': 0,
        'pending_tasks': 0,
        'failed_tasks': 0,
        'cancelled_tasks': 0,
    }

    for filename in os.listdir(state_folder):
        if filename.endswith('.state'):
            md5sum = filename.replace('.state', '')
            with open(os.path.join(state_folder, filename), 'r') as f:
                status = f.read().strip()
            fasta_fp = glob.glob(f'{results_folder}/{md5sum}/*.fasta')[0]
            fasta_fn = os.path.basename(fasta_fp)
            submitted_time = get_file_time(fasta_fp)
            finished_time = get_file_time(
                os.path.join(state_folder, filename), modified=True
            )
            walltime = get_task_walltime(
                submitted_time=submitted_time, finished_time=finished_time
            )

            task_statuses[md5sum] = {
                'status': status,
                'fasta_fn': fasta_fn,
                'submitted_time': format_times(submitted_time),
                'finished_time': format_times(finished_time),
                'walltime': int(walltime),
                'submitted_timestamp': submitted_time,
            }
            # Update task summary based on status
            task_summary['total_tasks'] += 1
            if status == 'finished':
                task_summary['finished_tasks'] += 1
            elif status == 'running':
                task_summary['processing_tasks'] += 1
            elif status == 'queued':
                task_summary['pending_tasks'] += 1
            elif status == 'failed':
                task_summary['failed_tasks'] += 1
            elif status == 'cancelled':
                task_summary['cancelled_tasks'] += 1

    # Sort the task_statuses dictionary by submitted_time (ascending order)
    sorted_task_statuses = dict(
        sorted(
            task_statuses.items(),
            key=lambda x: x[1]['submitted_timestamp'],
            reverse=True,
        )
    )

    # Render the HTML template with sorted task status information
    return render_template(
        'pssm_gremlin_dashboard.html',
        task_statuses=sorted_task_statuses,
        task_summary=task_summary,
    )

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=PORT)
