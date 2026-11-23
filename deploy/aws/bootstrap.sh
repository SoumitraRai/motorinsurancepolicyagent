#!/usr/bin/env bash
# First-time setup of an Ubuntu 24.04 EC2 host: Docker, a 2 GB swap file (headroom for OCR peaks),
# and the repo at /opt/rater/app. Safe to re-run: it updates the checkout instead of re-cloning.
set -euo pipefail
REPO=https://github.com/SoumitraRai/motorinsurancepolicyagent.git
BRANCH=${BRANCH:-main}

sudo apt-get update
sudo apt-get install -y docker.io docker-compose-v2 docker-buildx git
sudo systemctl enable --now docker

if ! swapon --show | grep -q /swapfile; then
  sudo fallocate -l 2G /swapfile
  sudo chmod 600 /swapfile
  sudo mkswap /swapfile
  sudo swapon /swapfile
  echo '/swapfile none swap sw 0 0' | sudo tee -a /etc/fstab
fi

sudo mkdir -p /opt/rater
if [ -d /opt/rater/app/.git ]; then
  sudo git -C /opt/rater/app fetch origin "$BRANCH"
  sudo git -C /opt/rater/app checkout -B "$BRANCH" "origin/$BRANCH"
else
  sudo git clone --branch "$BRANCH" "$REPO" /opt/rater/app
fi
echo "Next: create /opt/rater/rater.env from deploy/aws/env.template, then run deploy/aws/deploy.sh"
