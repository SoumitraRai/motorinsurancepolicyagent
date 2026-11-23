#!/usr/bin/env bash
# Build and (re)start the app on the EC2 host. Run after bootstrap.sh, and again after each update.
set -euo pipefail
ENV_FILE=/opt/rater/rater.env
[ -f "$ENV_FILE" ] || { echo "Missing $ENV_FILE (see deploy/aws/env.template)"; exit 1; }
cd /opt/rater/app
sudo docker compose --env-file "$ENV_FILE" -f deploy/aws/compose.yml up -d --build
sudo docker compose --env-file "$ENV_FILE" -f deploy/aws/compose.yml ps
