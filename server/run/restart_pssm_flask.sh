#!/bin/bash

RUN_DIR=$(dirname "$0")

# Replace these variables with your actual values
FLASK_APP_DIR="${RUN_DIR}/../pssm_gremlin"
CONDA_ENV_NAME="REvoDesign"
DOMAIN_NAME="revodesign.your-domain.name"
GUNICORN_WORKERS=2  # Number of Gunicorn worker processes
CONCURRENCY=2
PORT=8080

# Directory where the uploaded files will be stored and processed
WORK_DIR="/path/to/PSSM_GREMLIN/run/dir/"

# Activate the Conda environment
source activate $CONDA_ENV_NAME

# Change to the Flask app directory
cd $FLASK_APP_DIR

echo 'Restarting celery'
ps auxww | grep 'celery worker' | awk '{print $2}' | xargs kill -9
# start celery
celery multi restart worker -A  pssm_gremlin.celery -l INFO  --pidfile="$WORK_DIR/run/celery/pid/%n.pid" --logfile="$WORK_DIR/logs/celery/%n%I.log" --concurrency=$CONCURRENCY


echo 'Kill all running processes'
# Kill all previously running processes
pkill -f ${CONDA_ENV_NAME}.*gunicorn

echo 'Restarting gunicorn'
# Run your Flask app using Gunicorn
gunicorn -w $GUNICORN_WORKERS -b 0.0.0.0:${PORT} pssm_gremlin:app --log-level=info --error-logfile ${WORK_DIR}/logs/gunicorn_errors.log --access-logfile ${WORK_DIR}/logs/gunicorn_access.log 2>&1 &

# Provide instructions to the user
echo "Deployment completed."
echo "Your Flask app is now running at http://${DOMAIN_NAME}:${PORT}"
