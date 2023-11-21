#!/bin/bash

# Replace these variables with your actual values
FLASK_APP_DIR="/repo/RosettaWorkshop/2._Working/0._IntergatedProtocol/REvoDesign/server/pssm_gremlin"
CONDA_ENV_NAME="REvoDesign"
DOMAIN_NAME="ts.a100.yaoyy.moe"
GUNICORN_WORKERS=2  # Number of Gunicorn worker processes

WORK_DIR="/mnt/data/yinying/server/"

# Activate the Conda environment
source activate $CONDA_ENV_NAME

# Change to the Flask app directory
cd $FLASK_APP_DIR

#celery multi stopwait worker -A  pssm_gremlin.celery -l INFO  --pidfile="/mnt/data/yinying/server/run/celery/pid/%n.pid" --logfile="/mnt/data/yinying/server/logs/celery/%n%I.log" 

celery multi restart worker -A  pssm_gremlin.celery -l INFO  --pidfile="/mnt/data/yinying/server/run/celery/pid/%n.pid" --logfile="/mnt/data/yinying/server/logs/celery/%n%I.log" --concurrency=2

# Kill all previously running processes
pkill -f "gunicorn.*$DOMAIN_NAME"

# Run your Flask app using Gunicorn
gunicorn -w $GUNICORN_WORKERS -b 0.0.0.0:8080 pssm_gremlin:app --log-level=info --error-logfile $WORK_DIR/logs/gunicorn_errors.log --access-logfile $WORK_DIR/logs/gunicorn_access.log 2>&1 &

# Provide instructions to the user
echo "Deployment completed."
echo "Your Flask app is now running at http://$DOMAIN_NAME"
