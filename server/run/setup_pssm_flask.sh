#!/bin/bash

# Replace these variables with your actual values
FLASK_APP_DIR="/repo/RosettaWorkshop/2._Working/0._IntergatedProtocol/REvoDesign/server/pssm_gremlin"
CONDA_ENV_NAME="REvoDesign"
DOMAIN_NAME="ts.a100.yaoyy.moe"
NGINX_CONFIG_FILE="/etc/nginx/sites-available/REvoDesign_PSSM_GREMLIN.app"
#CELERY_WORKER_COUNT=2  # Number of Celery worker instances

WORK_DIR="/mnt/data/yinying/server/"



# Configure Nginx for your Flask app
echo "Configuring Nginx..."
sudo tee $NGINX_CONFIG_FILE > /dev/null <<EOL
server {
    listen 80;
    server_name $DOMAIN_NAME;

    location / {
        proxy_pass http://localhost:8080;
        proxy_set_header Host \$host;
        proxy_set_header X-Real-IP \$remote_addr;
    }
}
EOL

# Create a symbolic link to enable the Nginx config
sudo ln -s $NGINX_CONFIG_FILE /etc/nginx/sites-enabled/$(basename $NGINX_CONFIG_FILE)

# Restart Nginx
sudo service nginx restart
