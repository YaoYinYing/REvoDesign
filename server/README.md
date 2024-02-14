# PSSM GREMLIN Flask Application

This README provides an overview and documentation for the PSSM GREMLIN Flask application. This application is designed to facilitate the submission and management of tasks for the GREMLIN_PSSM protocol within the context of protein design and analysis. Users can upload FASTA files, which are processed in the background using Celery tasks, and the results can be downloaded when the tasks are completed.

![Server Design](./image/server.svg)

## Installation

1. Clone the repository to your server and fetch the runner docker image:

   ```shell
   git clone https://github.com/YaoYinYing/REvoDesign.git
   docker pull yaoyinying/revodesign-pssm-gremlin:latest
   ```

2. Navigate to the project directory and create GREMLIN and Flask server Conda environment:

   ```shell
   cd REvoDesign
   conda env create -f server/env/REvoDesign.yml
   conda activate REvoDesign
   pip install -U "celery[redis]"
   ```
3. Prepare the sequence databases required by the run script. :

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

   ```
   **Note** that for `psiblast`, the `uniref90` database should be formated using the `makeblastdb` tool from BLAST+. this can be done by whether the `run_docker.py` (see bellow) or call your own `makeblastdb` command`.

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

4. After that, you should test this with `server/docker/run_docker.py`:
   ```bash
   python /path/to/REvoDesign/server/docker/run_docker.py --fasta /path/to/REvoDesign/tests/testdata/1SUO_A.fasta --output ./test --uniref90_db ${DOWNLOAD_DIR}/uniref90/uniref90 --make_uniref90_db --uniref30_db ${DOWNLOAD_DIR}/uniref30/UniRef30_2023_02
   ```
   `--make_uniref90_db` is called to mount the uniref90 db and format it with `makeblastdb` tool.

   alternatively, you can call the installed `makeblastdb` tool on machine:
   
   ```bash
   makeblastdb -in uniref90.fasta -dbtype prot -parse_seqids -out uniref90
   ```
5. Install and start the Redis server (`root` required):

   ```shell
   sudo apt-get install redis-server
   sudo service redis-server start
   ```
6. Modify the following configuration:
- `server/pssm_gremlin/pssm_gremlin.py`: 
  - `SERVER_DIR`: Directory where the uploaded files will be stored and processed
- `server/run/restart_pssm_flask.sh`: 
  - `WORK_DIR`: Directory where the uploaded files will be stored and processed
  - `DOMAIN_NAME`: domain name the REvoDesign server uses to communicate.
7. (Re)Start the REvoDesign server:
   
   By default REvoDesign uses `8080`. You can check if port `8080` is occupied by other process.
   ```shell
   lsof -i :8080
   ```
   If `8080` is not ocuppied, this command returns nothing, otherwise the process name and PID will be shown. If so, you need to manually alter `PORT` configuration in `server/run/restart_pssm_flask.sh` and `server/pssm_gremlin/pssm_gremlin.py`, respectively.

   Now we start `Gunicorn` and `Flask` via port `8080`:
   ```shell
   bash /path/to/REvoDesign/server/run/restart_pssm_flask.sh
   ```
8. Optional: Install `NGINX` as a production server:
   
   ```shell
   sudo apt-get install nginx
   sudo service nginx start
   ```

   Setup NGINX proxy to REvoDesign server:
   ```
   NGINX_CONFIG_FILE="/etc/nginx/sites-available/REvoDesign_PSSM_GREMLIN.app"
   cd REvoDesign
   cp server/nginx_sites/REvoDesign_PSSM_GREMLIN.app $NGINX_CONFIG_FILE
   sudo ln -s $NGINX_CONFIG_FILE /etc/nginx/sites-enabled/$(basename $NGINX_CONFIG_FILE)
   ```
   
   **IMPORTANT**: SSL certificate for HTTPS is recommended for security purposes.
   ```
   # SSL certificate for https. Here we use lego and Cloudflare DNS
   # lego: https://go-acme.github.io/lego/
   CLOUDFLARE_EMAIL=your.cloudflare_account@email.address CLOUDFLARE_API_KEY=YOUR-CLOUDFLARE-API-KEY lego --email your@email.address  -a --key-type rsa4096 --dns cloudflare --domains 'revodesign.your-domain.name' --path /path/to/certificates/ run
   
   openssl dhparam -out /path/to/certificates/dhparam.pem 2048
   ```

   To schedule certificate renew task, use `crontab -e` to create a monthly renew task:
   ```crontab
   0 5 1 * * CLOUDFLARE_EMAIL=your.cloudflare_account@email.address CLOUDFLARE_API_KEY=YOUR-CLOUDFLARE-API-KEY lego --email your@email.address  -a --key-type rsa4096 --dns cloudflare --domains 'revodesign.your-domain.name' --path /path/to/certificates/ renew
   ```
   

   **IMPORTANT**: Create a http user for basic authentication from accessing the server
   ```shell
   htpasswd -c /etc/apache2/.htpasswd revodesign_users
   ```

   **IMPORTANT**: replace server domain name/port, certificate and basic authentication. 
   ```shell
   vim /etc/nginx/sites-available/REvoDesign_PSSM_GREMLIN.app
   ```

   after the configuration is done, restart NGINX to apply these changes.
   ```shell
   systemctl restart nginx
   ```

   Now, a production server with basic authentication and SSL encrypt is ready to use.


## Usage

### Submit FASTA Files via REvoDesign

To submit tasks for GREMLIN_PSSM analysis, follow these steps:

1. Start the PyMOL application and launch REvoDesign plugin.

2. Load a session/structure. Navigate to REvoDesign's menubar, click `REvoDesign` -> `Import PyMOL session` to load the protein info to REvoDesign. 

3. Select a target molecule and chain id, click `Client` tab.
   - Setup correct server URL, username and password(if the server requires `base_auth`).
   - Click the "Submit" button to submit the task.
   - If you wish to cancel in-queue or kill in-running tasks, click "Cancel"
   - After the task is done, click "Download" to fetch the zipped results.

### Submit FASTA Files via commandline tools
Use the following cURL command to batch submit FASTA files:

```shell
for i in *.fasta; do
    curl -X POST -F "file=@$i" 'http://your-server-ip:8080/PSSM_GREMLIN/api/post'
done
```

### Batch Canceling with cURL (macOS)

Use the following cURL command to batch cancel tasks based on MD5sum:

```shell
for i in *.fasta; do
    curl -X POST "http://your-server-ip:8080/PSSM_GREMLIN/api/cancel/$(md5 -q $i)"
done
```

### Dashboard

The dashboard provides an overview of task statuses and processing times. It includes the following information for each task:

- FASTA file name
- MD5sum
- Submitted At (time of submission)
- Finished At (time of completion)
- Wall Time (processing time)
- Status (queued, running, finished, failed, or cancelled)
- Download Link (for completed tasks)

Once a task is completed, you can download the results from this dashboard by clicking the "Download" link next to the task.

### Accessing the Dashboard

Access the dashboard to monitor tasks and download result files:

`http://your-server-ip:8080/PSSM_GREMLIN/dashboard` or
`https://revodesign.your-domain.name:8443/PSSM_GREMLIN/dashboard`


## Starting or restarting the Application

To restart the Flask application completely, use
```shell
bash /path/to/REvoDesign/server/run/restart_pssm_flask.sh
```

If you need a restart for apply code change without task interrupting(hot-fix), you can use the provided example:
```shell
bash /path/to/REvoDesign/server/run/hot_fix.sh
```
This script ensures that background Celery tasks continue running while the application is restarted. 


## Contributing

Contributions to this project are welcome. You can contribute by submitting bug reports, feature requests, or code improvements. Fork the repository, make your changes, and create a pull request.

## License

This project is licensed under the MIT License. See the [LICENSE](LICENSE) file for details.
