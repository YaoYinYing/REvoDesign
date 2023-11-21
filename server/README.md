# PSSM GREMLIN Flask Application

This README provides an overview and documentation for the PSSM GREMLIN Flask application. This application is designed to facilitate the submission and management of tasks for the GREMLIN_PSSM protocol within the context of protein design and analysis. Users can upload FASTA files, which are processed in the background using Celery tasks, and the results can be downloaded when the tasks are completed.

## Table of Contents
- [PSSM GREMLIN Flask Application](#pssm-gremlin-flask-application)
  - [Table of Contents](#table-of-contents)
  - [Prerequisites](#prerequisites)
  - [Installation](#installation)
  - [Usage](#usage)
    - [Uploading FASTA Files](#uploading-fasta-files)
    - [Checking Task Status](#checking-task-status)
    - [Downloading Results](#downloading-results)
    - [Canceling Tasks](#canceling-tasks)
    - [Dashboard](#dashboard)
  - [Managing Tasks](#managing-tasks)
  - [Restarting the Application](#restarting-the-application)
  - [Contributing](#contributing)
  - [License](#license)
  - [Using cURL and Requests](#using-curl-and-requests)
    - [Batch Submitting with cURL](#batch-submitting-with-curl)
    - [Batch Canceling with cURL (on macOS)](#batch-canceling-with-curl-on-macos)
    - [Accessing the Dashboard](#accessing-the-dashboard)

## Prerequisites

Before using the PSSM GREMLIN Flask application, ensure that you have the following prerequisites installed:

1. **hh-suite and NCBI BLAST+:** Install the programs required for MSA searching, including hh-suite and NCBI BLAST+. These are necessary for the proper functioning of the run script.

2. **Sequence Databases:** Prepare the sequence databases required by the run script. Note that for psiblast, the uniref90 database should be processed using the `makeblastdb` tool from BLAST+:

**UniRef90**
```shell
# stole from alphafold, DeepMind
ROOT_DIR="${DOWNLOAD_DIR}/uniref90"
SOURCE_URL="https://ftp.ebi.ac.uk/pub/databases/uniprot/uniref/uniref90/uniref90.fasta.gz"
BASENAME=$(basename "${SOURCE_URL}")

mkdir --parents "${ROOT_DIR}"
aria2c "${SOURCE_URL}" --dir="${ROOT_DIR}"
pushd "${ROOT_DIR}"
gunzip "${ROOT_DIR}/${BASENAME}"
popd

cd /path/to/uniref/database
makeblastdb -in uniref90.fasta -dbtype prot -parse_seqids -out uniref90
```
**UniRef30**
```shell
# stole from alphafold, DeepMind
ROOT_DIR="${DOWNLOAD_DIR}/uniref30"
SOURCE_URL="https://wwwuser.gwdg.de/~compbiol/uniclust/2023_02/UniRef30_2023_02_hhsuite.tar.gz"
BASENAME=$(basename "${SOURCE_URL}")

mkdir --parents "${ROOT_DIR}"
aria2c "${SOURCE_URL}" --dir="${ROOT_DIR}"
tar --extract --verbose --file="${ROOT_DIR}/${BASENAME}" \
  --directory="${ROOT_DIR}"
rm "${ROOT_DIR}/${BASENAME}"
```

3. **Core Run Conda Environment:** Create a Conda environment named `GREMLIN` for the core run script. This environment should include TensorFlow version 1.13.1 and other required tools.

4. **Server Conda Environment:** Create a Conda environment `REvoDesign` for the Flask application, Celery (Redis distribution), and Gunicorn.

5. **Redis:** Install and configure Redis as the message broker and result backend for Celery.

6. **Nginx:** Set up Nginx to serve as a reverse proxy for the Flask application. You can use the `/repo/RosettaWorkshop/2._Working/0._IntergatedProtocol/REvoDesign/server/run/setup_pssm_flask.sh` script for this purpose.

## Installation

1. Clone the repository to your server:

   ```bash
   git clone https://github.com/yourusername/pssm-gremlin-flask.git
   ```

2. Navigate to the project directory:

   ```bash
   cd pssm-gremlin-flask
   ```

3. Create and activate your Conda environment for the Flask application:

   ```bash
   conda create --name PSSMGremlinFlask python=3.6
   conda activate PSSMGremlinFlask
   ```

4. Install the required Python packages:

   ```bash
   pip install -r requirements.txt
   ```

5. Start the Redis server:

   ```bash
   redis-server
   ```

## Usage

### Uploading FASTA Files

To submit tasks for GREMLIN_PSSM analysis, follow these steps:

1. Start the Flask application:

   ```bash
   python app.py
   ```

   The application will be available at `http://your-server-ip:8080`.

2. Access the web interface in a browser.

3. Use the submission panel to upload FASTA files:
   - Click on the "Choose File" button.
   - Select a valid FASTA file (must have the `.fasta` extension).
   - Click the "Submit" button.

4. The uploaded file will be processed in the background using Celery tasks. Task status can be monitored on the dashboard.

### Checking Task Status

You can check the status of submitted tasks using the following methods:

- **Dashboard:** Visit the dashboard at `http://your-server-ip:8080/PSSM_GREMLIN/dashboard` to view a summary of task statuses.

- **API:** Use the `/PSSM_GREMLIN/api/running/<md5sum>` endpoint to check the status of a specific task. Replace `<md5sum>` with the MD5 hash of the submitted FASTA file.

### Downloading Results

Once a task is completed, you can download the results:

1. Access the web interface or the dashboard.

2. If the task status is "finished," click the "Download" link next to the task on the dashboard.

### Canceling Tasks

You can cancel tasks that are either in the queue or running:

1. Access the web interface or the dashboard.

2. If the task status is "queued" or "running," you can click the "Cancel Task" button to stop the task.

### Dashboard

The dashboard provides an overview of task statuses and processing times. It includes the following information for each task:

- FASTA file name
- MD5sum
- Submitted At (time of submission)
- Finished At (time of completion)
- Wall Time (processing time)
- Status (queued, running, finished, failed, or cancelled)
- Download Link (for completed tasks)

## Managing Tasks

You can use the dashboard to manage tasks effectively:

- Sort tasks by submitted time (descending order) to see the most recent submissions first.
- Track the progress of tasks with their statuses.
- Download results for completed tasks.
- Cancel queued or running tasks if needed.

## Restarting the Application

To restart the Flask application without interrupting the task queue, you can use a script similar to the provided example. This script ensures that background Celery tasks continue running while the application is restarted. Adjust the script variables and paths as needed for your environment.

```bash
./restart_app.sh
```

## Contributing

Contributions to this project are welcome. You can contribute by submitting bug reports, feature requests, or code improvements. Fork the repository, make your changes, and create a pull request.

## License

This project is licensed under the MIT License. See the [LICENSE](LICENSE) file for details.

## Using cURL and Requests

Basic control of the PSSM GREMLIN Flask application can be achieved using cURL or the Python `requests` library. Here are some examples:

### Batch Submitting with cURL

Use the following cURL command to batch submit FASTA files:

```bash
for i in *.fasta; do
    curl -X POST -F "file=@$i" 'http://your-server-ip:8080/PSSM_GREMLIN/api/post'
done
```

### Batch Canceling with cURL (on macOS)

Use the following cURL command to batch cancel tasks based on MD5sum:

```bash
for i in *.fasta; do
    curl -X POST "http://your-server-ip:8080/PSSM_GREMLIN/api/cancel/$(md5 -q $i)"
done
```

### Accessing the Dashboard

Access the dashboard to monitor tasks and download result files:

`http://your-server-ip:8080/PSSM_GREMLIN/dashboard`

Please note that you may need to replace `your-server-ip` with the actual IP address or domain name of your server.

These commands and URLs can be used for automation or control of the application from the command line or in scripts.