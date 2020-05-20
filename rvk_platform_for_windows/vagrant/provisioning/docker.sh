#!/usr/bin/env bash

echo "==============================================================="
echo "====================INSTALLING DOCKER=========================="
echo "==============================================================="

sudo apt-get update
sudo apt-get install -y docker.io docker-compose
sudo usermod -a -G docker vagrant